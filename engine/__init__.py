"""
驾校内容优化工具 — 核心引擎

模块:
  pipeline       — 管线（音频→ASR→场景→VLM），供内容顾问复用理解栈
  analyzer       — LLM 内容分析器（知识点提取 + 内容优化方案生成）
  advisor        — 内容顾问（上传视频/文字 → 5 块《内容优化方案》）
  scorer         — 片段评分引擎（遗留，仅旧切片流程使用）
  exporter       — 多平台视频导出器（遗留，仅旧切片流程使用）

注: scorer/exporter 为旧"多平台切片工具"遗留模块，新方向"内容优化工具"
    的调用链不涉及它们，保留以兼容旧流程。
"""

from .pipeline import Pipeline
from .scorer import SegmentScorer
from .exporter import VideoExporter
from .analyzer import ContentAnalyzer
from .advisor import ContentAdvisor

__all__ = ["Pipeline", "SegmentScorer", "VideoExporter", "ContentAnalyzer", "ContentAdvisor"]
