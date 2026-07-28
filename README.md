# AI 教学视频 · 多平台智能切片工具 🎬

> 长教学视频 → AI 理解内容 → 智能切片 → 一键导出抖音/B站/小红书 + 文案

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-green.svg)](https://www.python.org/)

## 💡 解决什么问题

教学视频创作者的真实痛点：

- 拍了一条 15 分钟的科三教学视频
- 想发抖音（要竖屏、大字幕、快节奏）
- 想发 B 站（要横屏、章节标记、知识卡片）
- 想发小红书（要 1:1、要点清单、封面图）
- 每个平台重剪一遍 → **同一个视频剪 3 遍**

这个工具让你**剪一次，全平台发布**。

## 🏗️ 流程

```
长视频 → ASR语音识别 → 场景检测 → VLM画面理解
    → 智能分段(5-8段) → 评分引擎(挑重点)
    → 你确认分段
    → 并行导出:
        ├─ 抖音 (9:16 竖屏 + 大字幕 + 关键词弹窗)
        ├─ B站 (16:9 横屏 + 知识卡片 + 章节)
        ├─ 小红书 (1:1 + 要点清单 + 封面)
        └─ 文案 (全平台标题/简介/标签)
```

详细设计见 [`docs/新方案_多平台切片工具.md`](docs/新方案_多平台切片工具.md)

## 🚀 快速开始（开发中）

```powershell
git clone https://github.com/Xin-der/ai-teaching-video-editor.git
cd ai-teaching-video-editor
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements-lock.txt

# 配置 .env
# DASHSCOPE_API_KEY=你的阿里云百炼key

# 运行（待实现）
python run.py --input "我的教学视频.mp4"
```

## 📖 文档

- [方案设计](docs/新方案_多平台切片工具.md)
- [交接文档](HANDOFF.md)
- [项目进度](PROGRESS.md)
- [原始调研](docs/AI视频剪辑方案调研.md)

## 📄 License

MIT
