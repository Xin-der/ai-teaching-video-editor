"""
帧点评：自动挑"最有问题"的 2-3 帧 → VLM 诊断（画质 + 内容表达）→ 标注框 + 建议

数据流（复用 pipeline 已采样 ≤6 关键帧，不新增采样成本）：
  采样帧列表 → 逐帧 VLM"帧诊断" → 按最严重问题 severity 取 top 帧 → 并入方案 JSON

输出 schema（坐标归一化 [x1,y1,x2,y2]，0-1）：
  {"frames": [
      { "index": 0, "time": 12.3, "image_b64": "...", "problems": [
          {"category": "lighting", "label": "逆光", "box": [0.05,0.1,0.45,0.6],
           "severity": 0.85, "advice": "主体过暗，建议朝光源拍摄或用补光灯"} ] } ] }

降级原则（关键）：
  - VLM 诊断失败 / 无 API Key / 无帧 → 返回空 dict，绝不阻塞主流程（5 块方案照常出）
  - 框坐标缺失 / 越界 → 该问题仅保留文字诊断（box=None）
  - 图片过大 → 降采样 ~720p 再 base64 内嵌
"""
import base64
import json
import os
import re
import subprocess
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
MODEL = os.environ.get("MODEL", "qwen3.7-plus")
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
FFMPEG = os.environ.get("FFMPEG", "ffmpeg")

MAX_DIAGNOSE_FRAMES = 4     # 最多诊断几帧（控制 VLM 成本，从采样帧里取前 N 帧）
MAX_PROBLEMS_PER_FRAME = 4  # 每帧最多保留的问题数
TOP_FRAMES = 3              # 最终挑选"最有问题"的帧数
MAX_SIDE = 720              # 图片降采样边长上限（控制 base64 体积）


DIAGNOSE_PROMPT = """你是一个短视频画质与内容表达诊断专家。仔细观察这张视频帧截图，找出"最容易劝退观众 / 影响传播"的问题，用 JSON 返回。

{
  "problems": [
    {
      "category": "lighting|blur|composition|focus|noise|angle|emphasis|content|visibility|other",
      "label": "简短问题名（如：逆光/画面抖动模糊/主体不突出/重点没圈出）",
      "box": [x1, y1, x2, y2],
      "severity": 0.0-1.0,
      "advice": "一句可执行的改进建议"
    }
  ]
}

要求：
1. 只返回 JSON，不要其他文字。
2. box 是问题区域坐标，归一化 0-1（x1<x2, y1<y2）；没有明确区域时省略 box。
3. 最多返回 4 条问题，按严重度从高到低。
4. 画质问题（亮度/模糊/构图/对焦/噪点）与内容表达问题（重点不突出/画面信息不清）都要找。
5. 没有明显问题时返回 {"problems": []}。"""


def _sanitize_problems(problems: list) -> list:
    """校验 / 规范化问题列表：severity 收敛到 0-1；box 越界 / 缺少数值 → None"""
    out = []
    for p in problems[:MAX_PROBLEMS_PER_FRAME]:
        cat = str(p.get("category", "other")) or "other"
        label = str(p.get("label", "")).strip() or cat
        advice = str(p.get("advice", "")).strip()
        try:
            sev = float(p.get("severity", 0))
        except (TypeError, ValueError):
            sev = 0
        sev = max(0.0, min(1.0, sev))

        box = p.get("box")
        box_ok = None
        if isinstance(box, (list, tuple)) and len(box) == 4:
            try:
                bx = [float(v) for v in box]
            except (TypeError, ValueError):
                bx = None
            if (bx and all(0.0 <= v <= 1.0 for v in bx)
                    and bx[0] < bx[2] and bx[1] < bx[3]):
                box_ok = bx

        out.append({
            "category": cat,
            "label": label,
            "severity": sev,
            "advice": advice,
            "box": box_ok,
        })
    return out


def _call_diagnose(client, img_b64: str) -> list:
    """对单帧调用 VLM 诊断，返回规范化问题列表；失败返回 []"""
    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "image_url",
                     "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
                    {"type": "text", "text": DIAGNOSE_PROMPT},
                ],
            }],
            max_tokens=600,
            temperature=0.3,
        )
        content = response.choices[0].message.content
        m = re.search(r'\{.*\}', content, re.DOTALL)
        if not m:
            return []
        data = json.loads(m.group())
        return _sanitize_problems(data.get("problems", []))
    except Exception:
        return []


def _resize_and_read_b64(frame_path: str, out_dir: str) -> str:
    """降采样到 ≤MAX_SIDE 并读 base64；失败退回原图，仍失败返回空"""
    try:
        out = Path(out_dir) / f"diag_{Path(frame_path).stem}.jpg"
        subprocess.run(
            [FFMPEG, "-y", "-i", str(frame_path),
             "-vf", f"scale='min({MAX_SIDE},iw)':-2", "-q:v", "3", str(out)],
            capture_output=True, check=True, timeout=30,
        )
        if out.exists():
            with open(out, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        pass
    try:
        with open(frame_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        return ""


def diagnose_frames(frame_specs: list, work_dir: str = "work",
                    max_frames: int = MAX_DIAGNOSE_FRAMES) -> dict:
    """对采样帧逐帧诊断，按最严重问题的 severity 取 top 帧。

    Args:
        frame_specs: [{"path": str, "time": float|None}, ...] 已采样关键帧
        work_dir: 降采样输出目录（每个 run 独立）
        max_frames: 最多诊断几帧（控制成本）

    Returns:
        {"frames": [{index, time, image_b64, problems}, ...]}；无帧 / 无 key / 失败 → {}
    """
    if not frame_specs or not DASHSCOPE_API_KEY:
        return {}

    specs = [s for s in frame_specs[:max_frames] if s.get("path") and os.path.exists(s["path"])]
    if not specs:
        return {}

    from openai import OpenAI
    client = OpenAI(api_key=DASHSCOPE_API_KEY, base_url=DASHSCOPE_BASE_URL)

    out_dir = Path(work_dir) / "frames"
    out_dir.mkdir(parents=True, exist_ok=True)

    diagnosed = []
    for idx, spec in enumerate(specs):
        b64 = _resize_and_read_b64(spec["path"], str(out_dir))
        if not b64:
            continue
        # 二次规范化：无论 _call_diagnose 是否已清理，都保证 severity/box 合法
        problems = _sanitize_problems(_call_diagnose(client, b64))
        if not problems:
            continue
        severity = max(p["severity"] for p in problems)
        diagnosed.append({
            "index": idx,
            "time": spec.get("time"),
            "image_b64": b64,
            "problems": problems,
            "_severity": severity,
        })

    if not diagnosed:
        return {}

    diagnosed.sort(key=lambda d: d["_severity"], reverse=True)
    top = diagnosed[:TOP_FRAMES]
    for d in top:
        d.pop("_severity", None)
    return {"frames": top}
