"""
多平台智能切片工具 — 核心引擎

模块:
  pipeline  — 核心管线（音频→ASR→场景→VLM→分段→评分）
  scorer    — 片段评分引擎（5 维度确定性打分）
  exporter  — 多平台视频导出器（ffmpeg CLI + ASS 字幕 + NVENC 硬件编码）
"""

from .pipeline import Pipeline
from .scorer import SegmentScorer
from .exporter import VideoExporter

__all__ = ["Pipeline", "SegmentScorer", "VideoExporter"]
