# 新机器交接文档

> 2026-07-28 | 从旧机器（4K HEVC 跑不动）→ 新机器（带 4090）

---

## 当前进度总览

### ✅ 已完成

| 模块 | 文件 | 状态 |
|---|---|---|
| 核心管线 | `engine/pipeline.py` | ✅ 完成，逻辑正确 |
| 评分引擎 | `engine/scorer.py` | ✅ 完成，已验证 |
| 导出器 | `engine/exporter.py` | ✅ 完成，但需修复（见下文） |
| 平台模板 | `templates/douyin.json`, `bilibili.json`, `xiaohongshu.json` | ✅ 完成 |
| 驾考知识库 | `knowledge/driving_exam.json` | ✅ 完成 |
| CLI入口 | `run.py` | ✅ 完成 |
| 音频提取 | `work/audio.wav` | ✅ 完成（28MB, 16kHz mono） |
| ASR语音识别 | `work/asr_result.json` | ✅ 完成（272句，可复用） |

### ⚠ 部分完成（卡在 4K HEVC 性能）

| 步骤 | 问题 | 解决方案 |
|---|---|---|
| 场景检测 | PySceneDetect 在 4K HEVC 超时 | 用 1080p 代理视频 |
| VLM 描述 | 依赖场景检测结果 | 场景检测完成后自动继续 |
| 视频导出 | MoviePy 逐帧处理 4K 太慢 | 改用 ffmpeg CLI + NVENC 硬件编码 |

### ✅ 可用产物

```
work/audio.wav              ← 已提取的音频（28MB）
work/asr_result.json        ← 272 句 ASR 结果（可直接用 --skip-asr）
work/segments.json          ← 基于 ASR 话题分段的 8 个片段（含评分）
```

---

## 在新机器上要做的操作

### 1. 环境准备

```bash
# 克隆仓库
git clone <repo-url>
cd ai视频剪辑agent

# 安装依赖
pip install -r requirements-lock.txt

# 安装 ffmpeg（如果没有的话）
# Windows: 下载 ffmpeg 放到 D:\tools\ffmpeg\
# 或用 winget install ffmpeg

# 配置 .env
# DASHSCOPE_API_KEY=你的key
# MODEL=qwen3.7-plus
# FFMPEG=D:/tools/ffmpeg/.../ffmpeg.exe   # 或直接用 "ffmpeg" （如果在PATH里）
# FFPROBE=D:/tools/ffmpeg/.../ffprobe.exe
```

### 2. 复制 work/ 缓存（跳过已完成的步骤）

把旧机器的这些文件复制到新机器：
```
work/audio.wav              ← 音频（28MB，避免重新提取）
work/asr_result.json        ← ASR 结果（272句）
work/segments.json          ← 分段结果
```

### 3. 用 1080p 代理跑全流程（推荐）

```bash
# 先生成 1080p 代理视频（快很多）
ffmpeg -i input/SGOI6715.MOV -vf scale=1920:1080 -c:v libx264 -preset fast -crf 18 -c:a copy -y input/proxy_1080p.mp4

# 用代理跑管线
python run.py input/proxy_1080p.mp4 --skip-asr
```

### 4. 或者直接用 ffmpeg 命令导出（绕过 MoviePy）

MoviePy 在 4K 下太慢。对于抖音导出，可以直接用 ffmpeg：

```bash
# 抖音 9:16 导出示例（片段0：夜间灯光操作 3.4s-31.4s）
ffmpeg -ss 3.4 -t 28.0 -i input/SGOI6715.MOV \
  -vf "crop=ih*9/16:ih:(iw-ih*9/16)/2:0,scale=1080:1920" \
  -c:v h264_nvenc -preset fast -cq 23 \
  -c:a aac -b:a 192k \
  -y output/夜间灯光操作/douyin.mp4
```

### 5. 需要修复的已知问题

1. **exporter.py 字体检测** — Pillow 找不到 SimHei，需要用完整路径 `C:/Windows/Fonts/simhei.ttf`（已修复）
2. **exporter.py write_videofile** — MoviePy 2.2.1 的 API 兼容（已修复 verbose→logger）
3. **exporter.py 整体** — 建议整块用 ffmpeg CLI 重写，不要用 MoviePy（太慢）
4. **pipeline.py **_detect_scenes** — 对 4K 源需先 downscale，或对代理运行

---

## 新机器优势

| 对比项 | 旧机器 | 新机器 (4090) |
|---|---|---|
| HEVC 解码 | CPU 软解，慢 | CPU 软解（4090 不加速解码） |
| H.264 编码 | CPU x264，慢 | NVENC 硬件编码，**快 10-50x** |
| 场景检测 | CPU 4K 超时 | 建议先转 1080p 代理，秒级完成 |
| ASR | FunASR CPU | 如有 CUDA torch，可 GPU 加速 |

**关键建议：始终对 1080p 代理操作，不要直接处理 4K。** 最终导出时再引用原始 4K 源。

---

## 临时脚本说明

| 文件 | 用途 |
|---|---|
| `_run_quick_pipeline.py` | 基于 ASR 话题分段（绕过视觉场景检测） |
| `_filter_top.py` | 筛选 Top N 片段 |
| `_test_export.py` | 测试单片段导出 |
| `_run_pipeline.py` | 完整管线（跳过音频+ASR） |
| `_run_asr.py` | 单独跑 ASR |
| `_convert_descriptions.py` | 转换旧 VLM 描述格式 |

这些临时脚本在流程稳定后可以删除。

---

## 联系人 / 仓库

- Git 用户: Xin-der
- 仓库: https://github.com/Xin-der/ai----agent
