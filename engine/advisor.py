"""
内容顾问 — 上传视频/文字 → 生成《内容优化方案》

流程:
  有视频 → 复用 Pipeline 的 ASR 转录 + 可选 VLM 看帧
  有文字 → 直接用文字
  两者皆无 → 报错
  调 analyzer.generate_optimization_plan() 生成 5 块方案
"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# 少于该字数的转录视为"内容过短"，不足以生成 5 块完整方案
MIN_TRANSCRIPT_CHARS = 10


def write_plan_markdown(plan: dict, out_path: str) -> str:
    """把 5 块方案写成 markdown 文件，返回路径"""
    d = plan.get("diagnosis", {})
    s = plan.get("script_rewrite", {})
    p = plan.get("packaging", {})
    c = plan.get("conversion", {})

    issues = "；".join(d.get("issues", [])) if d.get("issues") else "（无）"
    strengths = "；".join(d.get("strengths", [])) if d.get("strengths") else "（无）"

    lines = [
        "# 内容优化方案", "",
        "## ① 诊断",
        d.get("summary", "") or "（无）",
        f"**问题**：{issues}",
        f"**优点**：{strengths}",
        "", "## ② 脚本改写",
        "**开头3秒**：" + s.get("hook", ""),
        "**主体**：" + s.get("body", ""),
        "**证明**：" + s.get("proof", ""),
        "**引导**：" + s.get("cta", ""),
        "", "## ③ 包装",
        "**标题**：" + p.get("title", ""),
        "**封面文字**：" + p.get("cover_text", ""),
        "**简介**：" + p.get("description", ""),
        "", "## ④ 转化话术",
        "**置顶评论**：" + c.get("pinned_comment", ""),
        "**主页简介**：" + c.get("profile_bio", ""),
        "**私信开场白**：" + c.get("dm_opening", ""),
        "", "## ⑤ 下期选题",
    ]
    for t in plan.get("next_topics", []):
        lines.append(f"- **{t.get('title', '')}** — {t.get('why', '')}")

    text = "\n".join(lines)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
    return out_path


class ContentAdvisor:
    """内容顾问：输入视频/文字 → 5 块《内容优化方案》"""

    def __init__(self, work_dir: str = "work"):
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def build_plan(self, *, video_path=None, text=None,
                   city: str = "", platform: str = "douyin") -> dict:
        """主入口。video_path 和 text 至少提供一个，text 优先。"""
        transcript = ""
        vlm_summary = {}

        if text and text.strip():
            transcript = text.strip()
        elif video_path:
            if not os.path.exists(video_path):
                return {"error": f"视频文件不存在: {video_path}"}
            transcript, vlm_summary = self._analyze_video(video_path)
        else:
            return {"error": "请上传视频或粘贴文字"}

        transcript = transcript.strip()
        if not transcript:
            return {"error": (
                "没有检测到说话内容。请换一段有讲解的教学视频（5-15 分钟最佳），"
                "或直接粘贴文字脚本。"
            )}

        if len(transcript) < MIN_TRANSCRIPT_CHARS:
            return {"error": (
                f"这段内容太短（仅约 {len(transcript)} 个字），AI 还不足以生成完整方案。\n\n"
                "请上传一段有完整讲解的教学视频，或粘贴更完整的文字脚本。"
            )}

        from engine.analyzer import ContentAnalyzer
        analyzer = ContentAnalyzer()
        plan = analyzer.generate_optimization_plan(
            transcript, vlm_summary, city, platform,
        )
        if plan.get("_error"):
            return {"error": f"方案生成失败: {plan.get('_error')}"}
        if plan.get("_parse_error"):
            return {"error": "方案解析失败，请重试"}
        return plan

    def _analyze_video(self, video_path: str) -> tuple:
        """复用 Pipeline 的 ASR + VLM。返回 (transcript_str, vlm_summary_dict)。"""
        from engine.pipeline import Pipeline

        # 每次分析用独立工作目录。Pipeline 的中间产物（audio.wav /
        # asr_result.json / scenes.json / frame_descriptions.json）都是固定文件名，
        # 若共用 work_dir，下一个视频会直接命中上一个视频的缓存而永不真正转写。
        run_dir = self.work_dir / (
            f"run_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
        )
        run_dir.mkdir(parents=True, exist_ok=True)

        p = Pipeline(video_path, work_dir=str(run_dir))
        p._probe_video()
        segs = p.extract_transcript()
        transcript = " ".join(s.get("text", "") for s in segs)

        vlm_summary = {"topics": [], "visuals": []}
        try:
            frames = p.extract_visuals()
            topics = list(dict.fromkeys(
                fd.get("topic", "") for fd in frames if fd.get("topic")
            ))
            visuals = [fd.get("detail", "") for fd in frames if fd.get("detail")]
            vlm_summary = {"topics": topics, "visuals": visuals, "frame_count": len(frames)}
        except Exception as e:
            print(f"  ⚠ VLM 描述失败（非阻塞，跳过）: {e}")
        return transcript, vlm_summary
