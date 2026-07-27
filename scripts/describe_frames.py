"""VLM 描述关键帧 — 用 qwen3.7-plus 为每段画面生成结构化语义标签"""
import json, os, base64, time, sys
from dotenv import load_dotenv
load_dotenv()

import dashscope

API_KEY = os.getenv("DASHSCOPE_API_KEY")
MODEL = os.getenv("MODEL", "qwen3.7-plus")
SCENES_FILE = "work/scenes.json"
FRAMES_DIR = "work/frames"
OUTPUT = "work/frame_descriptions.json"

# ── 标签体系（驾考教学场景） ──
PROMPT = """你是一名驾考教学视频分析员。我会给你同一段视频的【开始帧】和【中间帧】两张画面，请你分析这段视频的内容。

请严格按以下 JSON 格式输出（只输出 JSON，不要其他文字）：

{
  "location": "车内 | 车外道路 | 考场场地 | 驾校场地 | 其他",
  "who_visible": ["教练" | "学员" | "无人物"],
  "activity": "讲解灯光 | 讲解规则 | 实操演示 | 路线介绍 | 考试模拟 | 起步操作 | 转向操作 | 停车操作 | 其他",
  "camera_angle": "车内前拍 | 车外前拍 | 侧面拍摄 | 正面拍摄 | 俯拍 | 其他",
  "visible_elements": ["仪表盘", "方向盘", "中控台", "道路标线", "交通信号灯", "文字叠加", "图示标注", "后视镜", "档位", "手刹", "其他"],
  "lighting": "白天 | 夜间 | 黄昏 | 室内",
  "summary": "用一句话描述这段视频的内容"
}

注意事项：
1. location 从给出的选项中选择一个最匹配的
2. who_visible 是数组，可以包含多个值
3. activity 选择最主要的一个活动类型
4. visible_elements 列出画面中能看到的元素，可多选
5. 只输出 JSON，不要任何解释文字"""


def encode_image(path):
    """读取图片并转为 base64 data URI"""
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode()
    return f"data:image/jpeg;base64,{b64}"


def describe_segment(seg_id, frame_start, frame_mid):
    """调用 VLM 描述一个分段的 start+mid 双帧"""
    img_start = encode_image(frame_start)
    img_mid = encode_image(frame_mid)

    messages = [{
        "role": "user",
        "content": [
            {"image": img_start},
            {"image": img_mid},
            {"text": f"上面是第{seg_id+1}段视频的开始帧和中间帧。{PROMPT}"}
        ]
    }]

    max_retries = 3
    for attempt in range(max_retries):
        try:
            resp = dashscope.MultiModalConversation.call(
                model=MODEL,
                messages=messages,
                api_key=API_KEY
            )
            if resp.status_code == 200:
                content_list = resp.output["choices"][0]["message"]["content"]
                # 提取文本部分
                for item in content_list:
                    if isinstance(item, dict) and "text" in item:
                        text = item["text"].strip()
                        # 尝试从 markdown 代码块中提取 JSON
                        if text.startswith("```"):
                            lines = text.split("\n")
                            text = "\n".join(lines[1:]) if lines[0].startswith("```") else text
                            if text.endswith("```"):
                                text = text[:-3]
                        return json.loads(text)
                return None
            elif resp.status_code == 429:
                wait = (attempt + 1) * 3
                print(f"  ⚠ 限流，等待 {wait}s...")
                time.sleep(wait)
            else:
                print(f"  ⚠ API 错误: {resp.status_code} {resp.message}")
                if attempt < max_retries - 1:
                    time.sleep(2)
        except json.JSONDecodeError as e:
            print(f"  ⚠ JSON 解析失败 (attempt {attempt+1}): {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
        except Exception as e:
            print(f"  ⚠ 调用异常 (attempt {attempt+1}): {type(e).__name__}: {e}")
            if attempt < max_retries - 1:
                time.sleep(3)

    return None


def main():
    # 加载分段信息
    with open(SCENES_FILE, encoding="utf-8") as f:
        scenes = json.load(f)["scenes"]

    print(f"=== VLM 描述关键帧 ===\n")
    print(f"模型: {MODEL}")
    print(f"分段数: {len(scenes)}")
    print(f"帧目录: {FRAMES_DIR}")
    print(f"API Key: {API_KEY[:12]}...")
    print()

    # 检查是否有已有进度（支持断点续传）
    results = []
    if os.path.exists(OUTPUT):
        with open(OUTPUT, encoding="utf-8") as f:
            existing = json.load(f)
            results = existing.get("segments", [])
        print(f"📂 加载已有进度: {len(results)} 段已完成\n")

    # 逐段处理
    total_cost = 0
    for seg in scenes:
        seg_id = seg["id"]

        # 跳过已完成的分段
        if any(r.get("segment_id") == seg_id for r in results):
            continue

        start_frame = os.path.join(FRAMES_DIR, f"seg{seg_id:03d}_start.jpg")
        mid_frame = os.path.join(FRAMES_DIR, f"seg{seg_id:03d}_mid.jpg")

        if not os.path.exists(start_frame) or not os.path.exists(mid_frame):
            print(f"  seg{seg_id:03d}: ⚠ 帧文件缺失，跳过")
            continue

        print(f"  seg{seg_id:03d} [track{seg['track']}] "
              f"{seg['start']:.0f}s-{seg['end']:.0f}s ({seg['duration']:.0f}s)...",
              end=" ", flush=True)

        t0 = time.time()
        desc = describe_segment(seg_id, start_frame, mid_frame)
        elapsed = time.time() - t0

        if desc:
            desc["segment_id"] = seg_id
            desc["t_start"] = seg["start"]
            desc["t_end"] = seg["end"]
            desc["duration"] = seg["duration"]
            desc["track"] = seg["track"]
            results.append(desc)
            cost_est = 0.002  # ~¥0.002 per multimodal call
            total_cost += cost_est
            print(f"✓ ({elapsed:.1f}s) {desc.get('summary', '')[:50]}")
        else:
            print(f"✗ 失败 ({elapsed:.1f}s)")
            # 保存失败标记
            results.append({
                "segment_id": seg_id,
                "t_start": seg["start"],
                "t_end": seg["end"],
                "duration": seg["duration"],
                "track": seg["track"],
                "error": "VLM call failed after retries"
            })

        # 每段完成后保存（断点续传）
        with open(OUTPUT, "w", encoding="utf-8") as f:
            json.dump({
                "segments": results,
                "total": len(results),
                "model": MODEL,
                "description": "每段 start+mid 双帧的结构化语义标签"
            }, f, ensure_ascii=False, indent=2)

        # 避免请求过快
        time.sleep(0.8)

    # 最终统计
    success = sum(1 for r in results if "error" not in r)
    fail = sum(1 for r in results if "error" in r)
    print(f"\n=== 完成 ===")
    print(f"成功: {success}/{len(results)} 段")
    print(f"失败: {fail}/{len(results)} 段")
    print(f"预估费用: ¥{total_cost:.2f}")
    print(f"输出: {OUTPUT}")


if __name__ == "__main__":
    main()
