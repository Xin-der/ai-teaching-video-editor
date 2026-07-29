# 导出链路验证 — 交接文档

> 2026-07-29 | Claude Code 工作会话

---

## 完成的工作

### 1. 导出器重写：MoviePy → ffmpeg CLI + ASS 字幕

**文件**: `engine/exporter.py`

- 彻底移除 MoviePy 依赖，改用 ffmpeg CLI 直接渲染
- 所有文字叠加层（标题卡、字幕、关键词弹窗、知识卡片、结尾卡）统一用 **ASS 字幕格式** 生成
- 视频处理：ffmpeg 原生 crop/scale/drawbox 滤镜
- 编码端：自动检测 NVENC，不可用时降级 libx264（当前环境使用 libx264，RTX 5060 应能用 NVENC）
- 封面图生成：ffmpeg 抽首帧 + Pillow 叠加文字

**关键修复**：
- 字体检测：`_detect_chinese_font()` 改为路径验证 + 名称返回（ASS 需要字体名）
- 编码器探测：`_detect_encoder()` 自动选择最优编码器
- Windows 路径兼容：ASS 滤镜中路径用正斜杠，冒号转义

### 2. 创建验证测试脚本

**文件**: `test_export_pipeline.py`

10 项测试覆盖：模块导入 / 评分引擎 / 模板加载 / 导出器基础 / ASS 生成 / ffmpeg 检测 / 导出流程 / 文案生成 / 知识库 / Pipeline

运行：`py -3.12 test_export_pipeline.py`

### 3. 一键启动脚本

**文件**: `RUN.bat` — 双击即跑全流程

### 4. 配置文件

**文件**: `.env.example` — 环境配置模板

### 5. 实际导出验证

对 `input/PNIK4383.MOV`（1920x1080 HEVC, 5.7min）进行了三平台导出：

| 平台 | 分辨率 | 文件 | 状态 |
|------|--------|------|------|
| 抖音 | 1080x1920 (9:16) | output/倒车入库/douyin.mp4 | ✅ |
| B站 | 1920x1080 (16:9) | output/倒车入库/bilibili.mp4 | ✅ |
| 小红书 | 1080x1080 (1:1) | output/倒车入库/xiaohongshu.mp4 | ✅ |
| 封面 | 1080x1080 | output/倒车入库/cover.jpg | ✅ |
| 文案 | - | output/倒车入库/copy.md | ✅ |

---

## 环境状态

### 当前机器

| 项目 | 详情 |
|------|------|
| OS | Windows 11 Home China |
| GPU | NVIDIA RTX 5060 Laptop (8GB) — NVENC 可用 |
| Python | 3.12.10 (`py -3.12`) 和 3.14.0 (`py`) |
| ffmpeg | 8.1.2-full_build @ `D:/Tools/ffmpeg/ffmpeg-8.1.2-full_build/` |
| 依赖 | 全部已安装（torch, funasr, modelscope, etc.） |
| API Key | DashScope 已配置在 `.env` |
| 测试视频 | `input/PNIK4383.MOV`（1080p HEVC, 515MB, 5.7min） |

### .env 关键配置

```
DASHSCOPE_API_KEY=sk-xxx
MODEL=qwen3.7-plus
FFMPEG=D:/Tools/ffmpeg/ffmpeg-8.1.2-full_build/ffmpeg-8.1.2-full_build/bin/ffmpeg.exe
FFPROBE=D:/Tools/ffmpeg/ffmpeg-8.1.2-full_build/ffmpeg-8.1.2-full_build/bin/ffprobe.exe
```

---

## 未完成 / 待解决

### ⚠️ 阻塞：ASR（Windows AppLocker）

**现象**: `OSError: [WinError 4551] 应用程序控制策略已阻止此文件`

torchaudio 的 `_torchaudio.pyd` 被 Windows Smart App Control / AppLocker 阻止加载。

**解决方案（三选一）**：

1. **关掉 Smart App Control**：Windows 安全中心 → 应用和浏览器控制 → 智能应用控制 → 关闭
2. **用 conda 装 Python**（推荐）：`conda create -n video python=3.12`，conda 装的包签名没问题
3. **手动卸载重装 Python 到 `C:\Python312\`**（不用 winget 装到 AppData）

验证修复：`py -3.12 -c "import torchaudio; print('OK')"`

### ⚠️ 待完成：完整管线

ASR 解决后运行：
```bash
py -3.12 run.py input/PNIK4383.MOV --export
```

这会执行全部 7 步，包括场景检测（PySceneDetect）和 VLM 关键帧描述（DashScope API）。

### ⚠️ 待优化：视频效果

用户反馈视频效果不理想，可能需要调整：

1. **ASS 样式** — 字幕字体大小、位置、颜色在 `engine/exporter.py` 的 `_ass_header()` 中配置
2. **平台模板** — `templates/douyin.json` 等文件中的 `layout` 参数
3. **NVENC 编码** — 当前用 libx264，确认 `h264_nvenc` 检测是否正常（理论上 RTX 5060 应该支持）
4. **字幕时间轴** — 依赖 ASR 结果质量
5. **进度条动画** — 当前是静态条，可改为动态 `geq` 滤镜

---

## 关键代码路径

| 功能 | 文件 | 关键部分 |
|------|------|---------|
| 导出入口 | `engine/exporter.py` | `VideoExporter.export()` |
| ffmpeg 渲染 | `engine/exporter.py` | `_render_ffmpeg()` |
| ASS 字幕生成 | `engine/exporter.py` | `_write_ass_file()` |
| ASS 样式定义 | `engine/exporter.py` | `_ass_header()` |
| 视频滤镜链 | `engine/exporter.py` | `_build_video_filters()` |
| 评分引擎 | `engine/scorer.py` | `SegmentScorer.score()` |
| 核心管线 | `engine/pipeline.py` | `Pipeline.run()` |
| 平台模板 | `templates/*.json` | 分辨率/布局/文案配置 |
| 知识库 | `knowledge/driving_exam.json` | 话题/关键词/扣分点 |

---

---

## 视频效果调优指南（给下次会话）

### 可调参数速查表

#### A. ASS 字幕样式 — `engine/exporter.py` → `_ass_header()`

| 参数 | 当前值 | 说明 | 调整方向 |
|------|--------|------|---------|
| Title 字体大小 | `out_h * 0.06` | 标题卡文字 | 太小改大 ratio |
| Subtitle 字体大小 | `out_h * 0.045` | 底部字幕 | 抖音竖屏可能需要更大 |
| Subtitle 位置 Y | `out_h * 0.80` | 字幕垂直位置 | 0.85 更低, 0.75 更高 |
| Popup 字体大小 | `out_h * 0.05` | 关键词弹窗 | 抖音需要醒目 |
| Popup 位置 Y | `out_h * 0.50` | 弹窗垂直位置 | 0.45 偏上, 0.55 偏下 |
| 所有颜色 | `&H00FFFFFF` 等 | ASS ABGR 格式 | 参考模板 JSON 里的 color 字段 |
| 描边宽度 | `Outline` 列 | 当前 3-4 | 越大描边越粗 |

#### B. 平台模板 — `templates/*.json`

| 参数 | 文件 | 当前值 | 说明 |
|------|------|--------|------|
| 输出分辨率 | `video.output_resolution` | 1080x1920 / 1920x1080 / 1080x1080 | 抖音可改 720x1280 减小文件 |
| 码率 | `video.bitrate` | 8M / 12M / 6M | 越大质量越好文件越大 |
| 标题卡时长 | `layout.title_card.duration_seconds` | 2.0s / 3.0s | 抖音应更短 |
| 结尾卡文字 | `layout.ending_card.text` | 各平台不同 | 自定义互动引导语 |
| 关键词触发词 | `layout.keyword_popup.trigger_keywords` | 10个词 | 增减触发词 |
| 弹窗时长 | `layout.keyword_popup.duration_seconds` | 1.5s | 太快看不清改 2.0s |
| 知识卡片时长 | `layout.knowledge_card.show_duration_seconds` | 5.0s | B站 |
| 进度条高度 | `layout.progress_bar.height_px` | 4px | 太细改 6-8px |
| 字幕每行字数 | `layout.subtitle.max_chars_per_line` | 18 douyin / 30 bilibili | 抖音竖屏应更少 |

#### C. 编码质量 — `engine/exporter.py` → `_detect_encoder()`

| 编码器 | 参数 | 当前值 | 说明 |
|--------|------|--------|------|
| NVENC | `cq` | 23 | 越小质量越好 (18-28) |
| NVENC | `preset` | p4 | p1最快 p7最慢质量最好 |
| libx264 | `crf` | 23 | 越小质量越好 (18-28) |
| libx264 | `preset` | fast | medium/slow 质量更好但慢 |

#### D. 视频裁切 — `engine/exporter.py` → `_build_video_filters()`

当前逻辑：中心裁切。如果关键内容不在画面中心，需要改裁切位置。
- 抖音 9:16：从 16:9 左右裁掉 60%，保留中间 40%
- 小红书 1:1：裁掉左右 25%

#### E. 评分权重 — `engine/scorer.py` → `__init__()`

如果选出的"最佳片段"不理想，调整权重：
```python
self.weights = {
    "keywords": 0.30,       # 关键词密度
    "knowledge_match": 0.25, # 知识库匹配
    "duration_ratio": 0.20,  # 时长占比
    "visual_emphasis": 0.15, # 画面信号
    "repetition": 0.10,      # 重复强调
}
```

### 常见效果问题排查

| 问题 | 可能原因 | 调整位置 |
|------|---------|---------|
| 字幕太小看不清 | 字体大小 ratio 不够 | `_ass_header()` Subtitle 样式 |
| 标题卡一闪而过 | duration 太短 | 模板 `title_card.duration_seconds` |
| 竖屏裁掉了人脸 | 中心裁切不适用 | `_build_video_filters()` crop 参数 |
| 视频文件太大 | 码率太高 | 模板 `video.bitrate` |
| 关键内容没字幕 | ASR 漏识别/时间轴偏移 | ASR 模型或后处理 |
| 弹窗太多/太少 | 触发词太宽泛/太严格 | 模板 `trigger_keywords` |
| 进度条看不到 | 颜色太淡/太细 | 模板 `progress_bar` 参数 |
| 导出太慢 | 没用 NVENC | 检查 `_detect_encoder()` 输出 |

---

## 下次会话启动语

```
请先读 HANDOFF.md、HANDOFF_导出链路验证完成.md 了解当前状态。
请帮我继续优化视频导出效果。
```
