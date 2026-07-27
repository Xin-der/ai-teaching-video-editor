# AI Teaching Video Editor 🎬

> AI 驱动的教学视频自动剪辑工具——发一段视频，AI 理解内容后按你的剪辑风格自动出片。

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-green.svg)](https://www.python.org/)

## 💡 这是什么

你拍教学视频，每次都要手动在剪映里加关键帧、图片叠加、字幕样式……很烦。

这个工具把这些重复操作自动化：
1. **学一次你的风格**（从一条你做好的成品视频）
2. **以后每次**，把新拍的原始视频丢进去 → AI 自动理解内容 → 在"老师写公式"处自动加放大关键帧 + 高亮框 → 在"学生提问"处自动加"问"卡片 → 输出完整 mp4

## 🏗️ 架构

```
原始视频 → [内容理解: ASR + 场景检测 + VLM 看画面]
         → [风格匹配: 标签引擎命中规则]
         → [渲染出片: MoviePy 合成 mp4]
```

详见 [`docs/AI视频剪辑技术文档.md`](docs/AI视频剪辑技术文档.md)

## 🚀 快速开始

### 1. 环境准备

```bash
# 克隆仓库
git clone https://github.com/Xin-der/ai-teaching-video-editor.git
cd ai-teaching-video-editor

# 创建虚拟环境（Windows）
python -m venv venv
venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置 API Key

```bash
# 阿里云百炼 DashScope（VLM 看画面）
setx DASHSCOPE_API_KEY "你的key"

# DeepSeek（风格翻译，只用一次）
setx DEEPSEEK_API_KEY "你的key"
```

### 3. 安装 ffmpeg

从 https://ffmpeg.org 下载，把 `bin/` 加入系统 PATH。

### 4. 第一段：学习你的剪辑风格

把你的参考成品视频 + 素材放到 `ref/` 目录，然后运行分析管线。

### 5. 第二段：每次出新片

把新视频放到 `input/`，使用 Skill 一句话触发。

## 📂 项目结构

```
ai-teaching-video-editor/
├── scripts/          # Python 脚本
├── assets/           # 复用图片素材
├── input/            # 新视频放这里
├── output/           # 成片输出
├── ref/              # 参考成品视频
├── docs/             # 技术文档
└── SKILL.md          # WorkBuddy Skill 定义
```

## 📖 文档

- [完整实操流程 v2](docs/AI视频剪辑_完整实操流程_v2.md)
- [技术文档（含工具介绍）](docs/AI视频剪辑技术文档.md)
- [方案调研](docs/AI视频剪辑方案调研.md)
- [对话知识汇总](docs/AI教学视频剪辑_对话知识汇总.md)

## ⚠️ 限制

- VLM 时间定位可能差几秒 → 需人工微调
- MoviePy 复杂缓动效果不如剪映原生引擎
- 依赖云端 API（阿里云 DashScope + DeepSeek）

## 📄 License

MIT License - 详见 [LICENSE](LICENSE)
