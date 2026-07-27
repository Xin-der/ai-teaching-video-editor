# AI Teaching Video Editor 🎬

> AI 驱动的教学视频自动剪辑工具——发一段视频，AI 理解内容后按你的剪辑风格自动出片。

[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/python-3.10+-green.svg)](https://www.python.org/)

## 💡 这是什么

你拍驾考教学视频，每次都要手动加路线图叠加、红点动画、关键帧缩放、画中画特写……很烦。

这个工具把这些重复操作自动化：
1. **学一次你的风格**（从你做好的一条成品视频 → 生成 `style_labels.json`）
2. **以后每次**，把新视频 + 路线图丢进 `input/` → `python run.py` → 去 `output/` 拿成品 mp4

## 🏗️ 架构

```
新视频 + 路线图(可选)
        │
        ▼
┌──────────────┐
│ 1. ASR 识别   │  FunASR 中文语音转文字
├──────────────┤
│ 2. VLM 分析   │  qwen3.7-plus 看画面 → 语义标签
│               │  自动判断: 有文字？有语音？有路线图？
├──────────────┤
│ 3. 标签匹配   │  确定性引擎 → 4条分支自动选择
│               │  分支A(文字+地图) B(语音+地图) C(纯视觉) D(无地图)
├──────────────┤
│ 4. 渲染出片   │  MoviePy 合成 → mp4
└──────────────┘
        │
        ▼
   output/成片.mp4
```

详见：
- 技术文档：[`docs/AI视频剪辑技术文档.md`](docs/AI视频剪辑技术文档.md)
- 使用流程：[`docs/用户使用流程.md`](docs/用户使用流程.md)
- 风格说明书：[`skill_style.md`](skill_style.md)

## 🚀 快速开始

### 1. 环境准备

```powershell
# 克隆仓库
git clone https://github.com/Xin-der/ai-teaching-video-editor.git
cd ai-teaching-video-editor

# 创建虚拟环境（Windows PowerShell）
python -m venv venv
.\venv\Scripts\activate

# 安装依赖
pip install -r requirements.txt
```

### 2. 配置

复制 `.env.example` 为 `.env`，填入你的阿里云百炼 API Key：

```
DASHSCOPE_API_KEY=你的key
MODEL=qwen3.7-plus
```

申请地址：https://dashscope.aliyun.com

### 3. 安装 ffmpeg

从 https://ffmpeg.org 下载，或 `winget install ffmpeg`。

### 4. 准备素材

```
input/
├── video.mp4          ← 必填：要处理的视频
├── route_map.png      ← 可选：路线图（蓝色路径版）
├── foot_closeup.mp4   ← 可选：脚部操作特写
└── dashboard_closeup.mp4 ← 可选：仪表盘特写
```

### 5. 一键出片

```powershell
python run.py
```

成品在 `output/成片.mp4`。

## 🎨 修改风格

编辑 `style_labels.json` 改参数，不需要写代码：

- 改 zoom 幅度 → `RULE_ZOOM.actions[0].params.scale_end`
- 改路线图位置 → `BRANCH_A.actions[2].params.position`
- 改画中画大小 → `RULE_PIP.actions[0].params` 里的 `scale`

详见 [`docs/用户使用流程.md`](docs/用户使用流程.md) 的"修改风格"章节。

## 📂 项目结构

```
ai-teaching-video-editor/
├── run.py                    ← 一键出片入口
├── style_labels.json         ← 风格规则（可自行修改）
├── skill_style.md            ← 风格说明书
├── scripts/
│   ├── run_asr.py            ← ASR 语音识别
│   ├── describe_frames.py    ← VLM 关键帧描述
│   ├── merge_content_map.py  ← 合并 ASR + VLM
│   ├── match_style.py        ← 标签匹配引擎
│   ├── render.py             ← MoviePy 渲染
│   └── translate_style.py    ← 风格规则生成（第一段用）
├── docs/                     ← 文档
├── input/                    ← 新视频放这里
├── output/                   ← 成品 mp4 输出
├── work/                     ← 中间文件（自动生成）
├── ref/                      ← 参考视频和素材
└── assets/                   ← 公共素材
```

## ⚠️ 说明

- **路线图不固定**：每条路线一张，放 `input/route_map.png` 即可
- **红点精度取决于文字标签**：视频里的文字标签越多，红点走得越准
- **MoviePy 复杂缓动不如剪映原生引擎**：适用于教学视频最常见的 zoom + 叠加 + 字幕场景
- **依赖云端 API**：阿里云 DashScope（qwen3.7-plus），每次出片约 ¥0.3-0.5

## 📖 文档

- [用户使用流程](docs/用户使用流程.md)
- [完整实操流程 v2](docs/AI视频剪辑_完整实操流程_v2.md)
- [项目进度](PROGRESS.md)

## 📄 License

MIT License
