"""
行业配置接口（轻量抽象，YAGNI）

内容教练工作台方向为"行业可配置、驾考先行"。本模块是唯一的行业配置入口：
get_industry_config(industry) 返回该行业的知识库路径 / 选题库路径 / 行业名 / prompt 提示语。

当前仅实现 driving_exam 一份；**不迁移**现有 knowledge/driving_exam.json，
有第二个行业时再抽目录化（knowledge/<industry>/）。未配置的行业回退到默认驾考配置。
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

DEFAULT_INDUSTRY = "driving_exam"

_INDUSTRY_CONFIGS = {
    "driving_exam": {
        "id": "driving_exam",
        "name": "驾考教学",
        "knowledge_path": str(ROOT / "knowledge" / "driving_exam.json"),
        "topics_path": str(ROOT / "knowledge" / "driving_exam_topics.json"),
        "system_prompt": (
            "你是一个深耕内容运营的短视频运营专家，特别擅长驾考教学领域。"
        ),
        "topic_prompt_hint": (
            "驾考学员在短视频平台搜的是'怎么过、去哪学'，选题要贴合学员痛点、"
            "考试节点（考试季/招生季/新规）与本地信息。"
        ),
    },
}


def get_industry_config(industry: str = DEFAULT_INDUSTRY) -> dict:
    """返回行业配置 dict。未知/未实现行业回退到默认驾考配置。"""
    industry = (industry or "").strip().lower()
    cfg = _INDUSTRY_CONFIGS.get(industry)
    if cfg is None:
        cfg = _INDUSTRY_CONFIGS[DEFAULT_INDUSTRY]
    return cfg


def supported_industries() -> list:
    """返回已实现的行业 id 列表（当前仅 driving_exam）。"""
    return list(_INDUSTRY_CONFIGS.keys())
