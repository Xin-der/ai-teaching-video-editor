"""
LLM 内容分析器 — 基于 qwen3.7-plus 文本理解 transcript + VLM 摘要

功能:
  1. 从 ASR transcript 提取核心教学知识点
  2. 识别操作步骤、重点警告、教练强调时刻
  3. 评估每个片段对多平台的适配度
  4. 生成各平台文案（标题 + 简介 + 标签）

模型: qwen3.7-plus (DashScope OpenAI-compatible, TEXT-only mode)
成本: 文本模式远低于多模态 VLM (~1/10)
"""

import json
import os
import re
from typing import Optional

from dotenv import load_dotenv

load_dotenv()

DASHSCOPE_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
MODEL = os.environ.get("MODEL", "qwen3.7-plus")
DASHSCOPE_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"


class ContentAnalyzer:
    """LLM-based content analyzer for teaching video understanding."""

    def __init__(self, knowledge_path: Optional[str] = None):
        self._client = None
        # 延迟加载 knowledge
        if knowledge_path is None:
            from pathlib import Path
            knowledge_path = str(
                Path(__file__).parent.parent / "knowledge" / "driving_exam.json"
            )
        with open(knowledge_path, "r", encoding="utf-8") as f:
            self.knowledge = json.load(f)

    @property
    def client(self):
        if self._client is None:
            if not DASHSCOPE_API_KEY:
                raise RuntimeError("未设置 DASHSCOPE_API_KEY")
            from openai import OpenAI
            self._client = OpenAI(
                api_key=DASHSCOPE_API_KEY,
                base_url=DASHSCOPE_BASE_URL,
            )
        return self._client

    # ------------------------------------------------------------------
    # 主入口
    # ------------------------------------------------------------------

    def analyze(self, asr_transcript: str, vlm_summary: dict,
                video_duration: float) -> dict:
        """分析完整教学视频内容

        Args:
            asr_transcript: 完整 ASR 文字记录
            vlm_summary: VLM 帧描述摘要 {topics, locations, ...}
            video_duration: 视频总时长(秒)

        Returns:
            {
                "knowledge_points": [...],     # 知识点列表
                "segments_analysis": [...],    # 每段分析
                "overall_style": {...},        # 整体风格建议
            }
        """
        prompt = self._build_analysis_prompt(asr_transcript, vlm_summary, video_duration)
        result = self._call_llm(prompt)
        return result

    def score_segment(self, segment: dict, knowledge_points: list,
                      video_duration: float) -> dict:
        """LLM 基于知识点对单个片段打分

        Returns:
            {score, reason, best_platform, highlight_moments, suggested_title}
        """
        prompt = self._build_scoring_prompt(segment, knowledge_points, video_duration)
        result = self._call_llm(prompt)
        return result

    def generate_copy(self, segment: dict, platform: str,
                      knowledge_points: list) -> dict:
        """为指定片段 + 平台生成文案

        Returns:
            {title, description, hashtags, engagement_hook}
        """
        prompt = self._build_copy_prompt(segment, platform, knowledge_points)
        result = self._call_llm(prompt)
        return result

    def analyze_style(self, reference_video_description: str) -> dict:
        """从参考视频描述中提取剪辑风格

        Args:
            reference_video_description: 对参考视频的文字描述
                (可以是人工描述，也可以来自 VLM 摘要)

        Returns:
            风格配置 dict，可直接用于模板
        """
        prompt = self._build_style_prompt(reference_video_description)
        result = self._call_llm(prompt)
        return result

    def generate_optimization_plan(self, transcript: str,
                                   vlm_summary: dict,
                                   city: str = "",
                                   platform: str = "douyin") -> dict:
        """生成 5 块《内容优化方案》。LLM 失败自动重试一次。"""
        prompt = self._build_plan_prompt(transcript, vlm_summary, city, platform)
        result = self._call_llm(prompt)
        if result.get("_error") or result.get("_parse_error"):
            result = self._call_llm(prompt)
        if result.get("_error") or result.get("_parse_error"):
            return result  # 交给上层报错
        return self._validate_plan(result)

    # ------------------------------------------------------------------
    # 内部方法
    # ------------------------------------------------------------------

    def _call_llm(self, prompt: str) -> dict:
        """调用 qwen3.7-plus 文本模式"""
        try:
            response = self.client.chat.completions.create(
                model=MODEL,
                messages=[{
                    "role": "system",
                    "content": (
                        "你是一个专业的短视频内容优化助手，擅长驾考等教学领域。"
                        "你的任务是从视频转录中提取实际内容，并输出结构化的内容优化方案。"
                        "内容可能是任何主题：教学类内容做到专业深度，非教学类按实际主题处理。"
                        "请始终返回合法的 JSON，不要添加任何解释文字。"
                    ),
                }, {
                    "role": "user",
                    "content": prompt,
                }],
                max_tokens=2000,
                temperature=0.3,
            )
            content = response.choices[0].message.content
            # 提取 JSON
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                return json.loads(json_match.group())
            return {"_parse_error": True, "raw": content[:500]}
        except Exception as e:
            return {"_error": str(e)}

    def _build_plan_prompt(self, transcript: str, vlm_summary: dict,
                           city: str = "", platform: str = "douyin") -> str:
        """构建《内容优化方案》prompt"""
        transcript = transcript[:4000] if len(transcript) > 4000 else transcript

        # 领域知识注入（高频话题 + 扣分点）
        kb_lines = []
        for t in self.knowledge.get("high_frequency_topics", [])[:8]:
            kp = " / ".join(t.get("deduction_points", [])[:3])
            kb_lines.append(f"- {t['topic']}: {kp}")
        kb_text = "\n".join(kb_lines) or "- (无)"

        topics = vlm_summary.get("topics", [])
        visuals = vlm_summary.get("visuals", [])
        visuals_text = "\n".join(f"- {v}" for v in visuals[:6]) if visuals else "(无画面信息)"
        city_text = city or "未指定（不要虚构城市）"

        prompt = f"""你是一个深耕内容运营的短视频运营专家，特别擅长驾考教学领域。观众刷视频不是看"教学"，是看"怎么过、去哪学"。请把这段视频的原始内容，改写成观众会看完、会互动、会转化的一整套优化方案。

【驾考领域知识（仅供驾考/教学类内容参考；如果内容不是驾考，请忽略此知识库，按实际主题处理）】
{kb_text}

【视频内容 transcript】
{transcript}

【画面信息】
画面主题: {', '.join(topics) if topics else '未知'}
画面细节:
{visuals_text}

【所在城市（用于同城关键词）】{city_text}
【目标平台】{platform}

请只返回如下 JSON，不要输出任何其他文字：

{{
  "diagnosis": {{
    "summary": "这条视频为什么没人看，3句话以内，基于实际内容",
    "issues": ["3-5个具体问题，如：开头没钩子/没痛点/没同城词/没引导"],
    "strengths": ["1-3个优点"]
  }},
  "script_rewrite": {{
    "hook": "开头3秒文案，直击学员痛点",
    "body": "干货主体，保留教练原话但重组得更紧凑、更有条理",
    "proof": "证明/案例（学员通过、资质、对比）",
    "cta": "引导话术（关注/评论扣1/私信/留资）"
  }},
  "packaging": {{
    "title": "标题，≤30字",
    "cover_text": "封面大字，≤12字",
    "description": "简介，≤100字"
  }},
  "conversion": {{
    "pinned_comment": "置顶评论文案",
    "profile_bio": "主页简介文案",
    "dm_opening": "私信开场白，自然不推销"
  }},
  "next_topics": [
    {{"title": "选题1", "why": "学员为什么在搜它"}},
    {{"title": "选题2", "why": "学员为什么在搜它"}},
    {{"title": "选题3", "why": "学员为什么在搜它"}}
  ]
}}

规则：
1. 一切内容必须严格基于 transcript 的实际内容，禁止虚构、禁止套话。
2. 如果内容是驾考/教学类：面向学员视角（"我怎么过、去哪学"），调用驾考领域知识做专业深度。
3. 如果内容不是驾考教学（如生活记录、搞笑、闲聊、美食、其他领域等）：忽略驾考知识库，按该内容的实际主题输出同样的 5 块方案（诊断/改写/包装/转化/下期选题），语言风格与平台匹配。
4. 若指定了城市且与内容相关，标题带上城市名与关键词；不相关则不强行加。
5. next_topics 必须 3 个。"""
        return prompt

    def _validate_plan(self, plan: dict) -> dict:
        """确保 5 块结构完整，缺失字段补默认值"""
        defaults = {
            "diagnosis": {"summary": "", "issues": [], "strengths": []},
            "script_rewrite": {"hook": "", "body": "", "proof": "", "cta": ""},
            "packaging": {"title": "", "cover_text": "", "description": ""},
            "conversion": {"pinned_comment": "", "profile_bio": "", "dm_opening": ""},
            "next_topics": [],
        }
        for key, dflt in defaults.items():
            if key == "next_topics":
                if key not in plan or not isinstance(plan[key], list):
                    plan[key] = []
            elif key not in plan or not isinstance(plan[key], dict):
                plan[key] = dict(dflt)
            else:
                for sub, val in dflt.items():
                    plan[key].setdefault(sub, val)
        return plan

    def _build_analysis_prompt(self, transcript: str, vlm_summary: dict,
                                duration: float) -> str:
        """构建分析提示词"""
        # 截断过长的 transcript
        transcript_snippet = transcript[:4000] if len(transcript) > 4000 else transcript

        topics = vlm_summary.get("topics", [])
        prompt = f"""请分析以下驾考教学视频的语音转录内容，提取结构化信息。

视频总时长: {duration:.0f}秒
识别到的教学主题: {', '.join(topics) if topics else '未知'}

语音转录:
---
{transcript_snippet}
---

请返回以下 JSON 结构：

{{
  "knowledge_points": [
    {{
      "name": "知识点名称",
      "time_range": "大致时间范围（如 30s-60s）",
      "importance": "高/中/低",
      "key_steps": ["操作步骤1", "操作步骤2"],
      "warnings": ["扣分警告1"],
      "keywords_from_speech": ["教练强调的关键词"]
    }}
  ],
  "teaching_style": {{
    "pace": "快节奏/中等/慢节奏",
    "emphasis_method": "教练如何强调重点（重复/手势/反面举例/口诀）",
    "target_audience": "初学者/考前复习/补考学员",
    "energy_level": "高/中/低（视频整体活力程度）"
  }},
  "platform_recommendations": {{
    "douyin": {{"suitable_topics": ["适合抖音的话题"], "reason": "原因"}},
    "bilibili": {{"suitable_topics": ["适合B站的话题"], "reason": "原因"}},
    "xiaohongshu": {{"suitable_topics": ["适合小红书的话题"], "reason": "原因"}}
  }}
}}

只返回 JSON，不要加其他文字。"""
        return prompt

    def _build_scoring_prompt(self, segment: dict, knowledge_points: list,
                               total_duration: float) -> str:
        """构建评分提示词"""
        seg_dur = segment.get("duration", 0)
        transcript = segment.get("transcript", "")[:1500]
        topic = segment.get("topic", "")

        kp_summary = "\n".join(
            f"- {kp['name']} (重要性: {kp.get('importance', '?')})"
            for kp in knowledge_points[:8]
        )

        prompt = f"""评估这个教学视频片段的内容价值，用于多平台分发。

片段信息:
- 主题: {topic}
- 时长: {seg_dur:.0f}秒（总视频 {total_duration:.0f}秒）
- 占比: {seg_dur/total_duration*100:.0f}%

片段 transcript:
---
{transcript}
---

识别到的知识点:
{kp_summary}

请返回 JSON:

{{
  "score": 0.0-1.0,
  "reason": "评分理由（一句话）",
  "best_platform": "douyin/bilibili/xiaohongshu",
  "platform_scores": {{"douyin": 0.0, "bilibili": 0.0, "xiaohongshu": 0.0}},
  "highlight_moments": [
    {{"time_offset": "秒数", "description": "关键时刻描述"}}
  ],
  "suggested_title": "推荐的短视频标题",
  "has_clear_structure": true/false,
  "engagement_potential": "高/中/低"
}}

只返回 JSON。"""
        return prompt

    def _build_copy_prompt(self, segment: dict, platform: str,
                            knowledge_points: list) -> str:
        """构建文案生成提示词"""
        topic = segment.get("topic", "驾考教学")
        transcript = segment.get("transcript", "")[:800]

        platform_guides = {
            "douyin": "竖屏短视频，强调快节奏、醒目大字、互动引导。标题限制30字以内。",
            "bilibili": "横屏中长视频，强调知识深度、章节标记、技术细节。标题可较长。",
            "xiaohongshu": "1:1方形视频，强调要点清单、收藏价值、精美封面。标题用emoji点缀。",
        }
        guide = platform_guides.get(platform, "")

        kp_names = [kp["name"] for kp in knowledge_points[:5]]

        prompt = f"""为驾考教学视频的{platform}版本撰写发布文案。

教学内容: {topic}
涉及知识点: {', '.join(kp_names) if kp_names else topic}
平台调性: {guide}

片段文字摘要:
---
{transcript}
---

请返回 JSON:

{{
  "title": "视频标题",
  "description": "视频简介（100字以内）",
  "hashtags": ["#标签1", "#标签2", "#标签3", "#标签4", "#标签5"],
  "engagement_hook": "互动引导语（评论区提问或收藏转发引导）"
}}

只返回 JSON。"""
        return prompt

    def _build_style_prompt(self, reference_description: str) -> str:
        """构建风格分析提示词"""
        prompt = f"""分析以下教学视频的剪辑风格，提取可用于自动剪辑的参数。

参考视频描述:
---
{reference_description}
---

请返回 JSON 风格配置:

{{
  "subtitle_style": {{
    "font_size_ratio": 0.04,
    "color": "#FFFFFF",
    "stroke_color": "#000000",
    "stroke_width": 3,
    "position": "bottom",
    "animation": "fade_in/typewriter/bounce/none"
  }},
  "pace": {{
    "avg_segment_duration": 30,
    "transition_type": "cut/dissolve/zoom/none",
    "silence_handling": "speedup/cut/keep"
  }},
  "effects": {{
    "use_title_card": true,
    "use_progress_bar": true,
    "use_highlight_overlay": false,
    "color_grading": "warm/cool/none",
    "bgm_style": "upbeat/calm/none"
  }},
  "engagement": {{
    "opening_hook_style": "question/statement/surprise",
    "ending_style": "subscribe/like/comment/next_preview",
    "use_keyword_popups": true
  }}
}}

只返回 JSON。"""
        return prompt


# ------------------------------------------------------------------
# 快速测试
# ------------------------------------------------------------------
if __name__ == "__main__":
    analyzer = ContentAnalyzer()

    # 测试内容分析
    test_transcript = """
    记住啊，夜间灯光考试一定要先关闭所有灯光。
    重点是千万别抢答，考试的时候每次语音播报完再操作。
    远近光切换的时候往上推到底，等三秒再松手。
    这个最容易挂科，很多人一紧张就忘。
    """

    result = analyzer.analyze(
        asr_transcript=test_transcript,
        vlm_summary={"topics": ["夜间灯光操作"]},
        video_duration=300,
    )
    print("=== 内容分析结果 ===")
    print(json.dumps(result, ensure_ascii=False, indent=2))
