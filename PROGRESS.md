# AI 教学视频剪辑 · 项目进度与交接文档

> 创建时间：2026-07-27 | 当前阶段：第一段「学风格」- 本地处理完成，待 VLM + LLM

---

## 1. 项目概述

**目标**：驾考教学视频 AI 自动剪辑——发一段新视频，AI 按已有剪辑风格自动出 mp4。

**核心架构**：三阶段混合管道
```
新视频 → [内容理解: ASR + 场景 + VLM] → [风格匹配: 标签引擎] → [渲染: MoviePy → mp4]
```

---

## 2. 当前进度

### 已完成 ✅

| 步骤 | 工具 | 输出 | 状态 |
|---|---|---|---|
| 方案设计 | — | `docs/` 4份MD | ✅ |
| 项目初始化 | Git | `D:\Projects\ai视频剪辑agent\` | ✅ |
| GitHub 仓库 | gh CLI | https://github.com/Xin-der/ai-teaching-video-editor | ✅ |
| 环境安装 | pip/venv | Python 3.10, 全部依赖 | ✅ |
| ffmpeg 安装 | winget | `D:\tools\ffmpeg\ffmpeg-8.1.2-full_build\` | ✅ |
| 工程文件解密 | jy-draftc | `ref/draft_content.json.dec.json` | ✅ |
| 工程文件解析 | parse_draft_deep.py | 17段, 4视频轨, 10贴纸轨 | ✅ |
| 音频提取 | ffmpeg | `work/ref_audio.wav` (28MB, 16kHz mono) | ✅ |
| ASR 语音识别 | FunASR Paraformer | `work/asr_result.json` (**272句**) | ✅ |
| 分段提取 | draft_content 提取 | `work/scenes.json` (17段) | ✅ |
| 关键帧抽取 | ffmpeg | `work/frames/` (**51张 JPG**) | ✅ |

### 进行中 🔄

无。本地处理全部完成。

### 待执行 ⏳

| 步骤 | 说明 | 需要 |
|---|---|---|
| VLM 描述关键帧 | qwen3.7-plus 看每张帧图 → 结构化标签 | DashScope API key (已配) |
| 风格规则对齐 | qwen3.7-plus 把"工程参数 + 语义标签"对齐成风格规则 | DashScope API key |
| 生成风格说明书 | 输出 skill_style.md + style_labels.json | — |
| 第二段验证 | 用新视频跑完整管线，验证效果 | 新视频素材 |

---

## 3. 关键决策记录

### 3.1 为什么选 FunASR 而非 WhisperX
- **中文识别率**：Paraformer 中文 WER 业界最低
- **说话人分离**：内置 CAM++，不需要额外 HuggingFace token
- **本地运行**：不依赖云端，隐私安全
- **代价**：模型 990MB，首次下载慢；15 分钟以上音频需分段处理避免 OOM

### 3.2 为什么用工程文件提取分段而非 PySceneDetect
- 剪映 `draft_content.json` 已包含精确的视频分段（17 段）
- PySceneDetect 对软转场检测不准，且 4GB 视频逐帧检测极慢
- 工程文件分段更准确反映编辑意图

### 3.3 为什么执行层用 MoviePy 而非裸 ffmpeg
- MoviePy 代码可读性高 10 倍，Python 原生操作
- ffmpeg `zoompan` 有 bug，复杂 filter_complex 难以维护
- MoviePy 的局限：复杂缓动曲线不如剪映原生引擎

### 3.4 为什么第二段不用 LLM 做匹配
- VLM 输出**结构化标签**（非自由文本）
- 匹配逻辑变成确定性 Python 集合运算：`required_labels ⊆ segment_labels`
- 快、免费、100% 可复现

### 3.5 工程文件加密问题
- 剪映 6.0+ 加密了 `draft_content.json`
- 解决方案：`jy-draftc` 工具（winget 安装）
- 局限：部分关键帧数值解密后为 None（需 VLM 反推弥补）
- .env 配置：`JY_INSTALL_DIR=D:\jianying\JianyingPro\11.1.0.14287`

---

## 4. 环境配置

### 4.1 Python 虚拟环境
```
位置: D:\Projects\ai视频剪辑agent\venv\
Python: 3.10.11
激活: .\venv\Scripts\activate
```

### 4.2 关键依赖
```
funasr==1.3.29        # 中文 ASR
modelscope==1.38.1    # 模型下载
scenedetect==0.7.1    # 场景检测（备用）
moviepy==2.2.1        # 视频渲染
dashscope==1.26.4     # 阿里云百炼 API
openai==2.48.0        # OpenAI 兼容 SDK（备用）
torch==2.13.0+cpu     # FunASR 推理
opencv-python==5.0.0  # 图像处理
```

完整清单: `requirements-lock.txt`

### 4.3 .env 配置
```
DASHSCOPE_API_KEY=sk-a26bfcd490864f0bb16b8b90974c1f07
MODEL=qwen3.7-plus
```

### 4.4 模型下载路径
```
FunASR Paraformer: C:\Users\X360\.cache\modelscope\models\iic--speech_seaco_paraformer_large_asr_nat-zh-cn-16k-common-vocab8404-pytorch\
```

### 4.5 外部工具
```
ffmpeg:  D:\tools\ffmpeg\ffmpeg-8.1.2-full_build\bin\ffmpeg.exe
ffprobe: D:\tools\ffmpeg\ffmpeg-8.1.2-full_build\bin\ffprobe.exe
jy-draftc: C:\Users\X360\AppData\Local\Microsoft\WinGet\Packages\wenshui330.jy-draftc_...\jy-draftc.exe
gh CLI:  D:\tools\gh\gh.exe
FunClip: D:\tools\FunClip\ (参考用，不直接调用)
```

---

## 5. 输出文件清单

### ref/ — 参考材料（用户提供，不入 git）
```
ref/SGOI6715.MOV                     4.0GB  iPhone拍摄的成品驾考教学视频 (15分18秒)
ref/draft_content.json                3.1MB  剪映加密工程文件
ref/draft_content.json.dec.json       2.4MB  jy-draftc 解密后的工程文件 (纯JSON)
ref/materials/                        3张PNG 剪映贴纸素材
```

### work/ — 中间产物（不入 git）
```
work/ref_audio.wav                   28MB   提取的音频 (16kHz mono PCM)
work/asr_result.json                  272句  FunASR 语音识别结果
work/scenes.json                      17段   从工程文件提取的视频分段
work/style_params_raw.json            关键帧参数原始提取
work/frames/segXXX_{start,mid,end}.jpg  51张  每段起止中间3帧 (4K分辨率，较大)
```

### output/ — 最终输出（不入 git）
```
（空，第二段渲染的成品 mp4 放这里）
```

### assets/ — 可复用素材（入 git）
```
（空，待第一段分析后从 ref/materials 中提取可复用素材）
```

### scripts/ — Python 脚本
```
scripts/run_asr.py           ASR 语音识别（分段处理，跳过静音）
scripts/extract_segments.py  从工程文件提取分段 + 抽关键帧
scripts/parse_draft_deep.py  深度解析工程文件
scripts/deep_analyze.py      深入分析关键帧数值
scripts/check_keyframes.py   检查关键帧值结构
scripts/explore_draft.py     探索工程文件顶层结构
```

### docs/ — 文档
```
docs/AI视频剪辑_完整实操流程_v2.md          用户操作指南
docs/AI视频剪辑技术文档.md                   技术方案完整文档
docs/AI视频剪辑方案调研.md                   原始调研文档
docs/AI教学视频剪辑_完整技术方案_B方案.md      B方案细节
docs/AI教学视频剪辑_对话知识汇总.md          对话知识汇总
```

---

## 6. 剩余任务执行步骤

### Step 1: 确认环境
```powershell
cd "D:\Projects\ai视频剪辑agent"
.\venv\Scripts\activate
# 确认 .env 存在且 DASHSCOPE_API_KEY 有效
```

### Step 2: VLM 描述关键帧（核心任务）
**输入**: `work/frames/` 下的 51 张 JPG（每段 3 张：start/mid/end）
**输出**: `work/frame_descriptions.json` — 每张图的语义标签
**API**: qwen3.7-plus (DashScope)
**费用**: ~¥0.3-0.5

**Prompt 模板**（参考 v2 流程文档）:
```
你是一名教学视频分析员。请看这张画面，用一句话描述：
1) 谁在画面中（教练/学员/只有车内/道路）；
2) 正在发生什么（讲解灯光/起步操作/转向/停车/考试模拟）；
3) 画面里有没有仪表盘、方向盘、道路标线或车内设备。
只输出关键事实，不要发挥。
```

**⏳ 不要只返回文字描述！要返回结构化标签**，参考格式:
```json
{
  "scene_type": "驾驶教学",
  "labels": ["instructor_visible", "explaining_lights", "inside_car", "dashboard_visible"],
  "summary": "教练在车内讲解夜间灯光操作，仪表盘亮着"
}
```

**建议的处理方式**:
- 17 段 × 每段至少看 start 和 mid 帧 (34 次调用)
- end 帧可选，减少调用量
- 同一段的 start/mid 做对比分析，判断"这段发生了什么变化"

### Step 3: 结合 ASR 生成 content_map
把 `work/asr_result.json`（272 句）+ `work/scenes.json`（17 段）+ VLM 标签合并成 `work/content_map.json`:
```json
[
  {
    "segment_id": 0,
    "t_start": 3.4, "t_end": 62.8,
    "speaker": "教练",
    "labels": ["instructor_visible", "explaining_lights", "inside_car"],
    "transcript": "夜间灯光使用的考试请根据...",
    "summary": "车内教练讲解灯光考试操作流程"
  }
]
```

### Step 4: LLM 风格翻译
**输入**: `work/style_params_raw.json` + `work/content_map.json`
**输出**: `skill_style.md` + `style_labels.json`
**API**: qwen3.7-plus
**费用**: ~¥0.01

**Prompt**: 把"工程参数 + 语义标签"对齐成风格规则：
「触发条件（语义标签）→ 应用特效（参数来自工程文件）」

### Step 5: 人工审核
把 `skill_style.md` 给用户确认：
- "教练讲解灯光时 → 圈出仪表盘 + 缩放关键帧" 是否正确
- 纠正语义误判
- 固化规则

### Step 6: 第二段验证（可选，等用户提供新视频）
用新视频跑完整管线验证风格规则，输出成品 mp4。

---

## 7. 注意事项

1. **中文路径**: Git Bash 无法处理 `D:\Projects\ai视频剪辑agent` 的中文路径，**所有 Python/ffmpeg 命令必须用 PowerShell** 执行
2. **API Key**: 在 `.env` 中，脚本通过 `python-dotenv` 读取；`.env` 已在 `.gitignore` 中
3. **视频信息**: 驾考教学视频，15分18秒，iPhone 拍摄 MOV，教练讲解 + 实操演示
4. **关键帧数值丢失**: jy-draftc 解密后关键帧值为 None，需靠 VLM + 用户确认反推
5. **GitHub**: 仓库 https://github.com/Xin-der/ai-teaching-video-editor，用户 Xin-der，不要加 Co-Authored-By
6. **ASR 质量**: Paraformer 输出是空格分隔字序列（无标点），272 句可能偏多，部分短句可合并
7. **上下文长度**: 当前会话已满，此文档即交接，新会话读此文件和 docs/ 目录即可继续
8. **不要用 Git Bash 跑任何命令**，全部用 PowerShell（Windows 原生命令行）
9. **新会话第一步**: 读 `docs/AI视频剪辑_完整实操流程_v2.md` + `docs/AI视频剪辑技术文档.md` + 本文件
