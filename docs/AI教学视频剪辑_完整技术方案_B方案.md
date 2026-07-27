# AI 教学视频智能剪辑 · 完整技术方案（套餐 B + 有剪映工程文件）

> 适用前提：你用**手机版剪映**做出成品，且能通过「剪映云草稿」同步到 **PC 剪映**，拿到工程文件 `draft_content.json`（最准）；运行模式为 **套餐 B = 本地预处理 + 云端大模型**。
> 目标：发一段新的教学视频 → AI 理解内容 → 按你成品的剪辑风格自动套用关键帧 + 图片叠加 → 出片。

---

## 0. 方案一句话

- **视频文件、所有剪辑执行（ffmpeg）、场景检测、中文语音识别** → 永远在你电脑**本地**跑，不联网、不要 key。
- **"看懂画面"（VLM）+"翻译指令"（LLM）** → 走**云端 API**（阿里通义 `qwen-vl-plus` + `DeepSeek` / `qwen-plus`），只传压缩小图和 JSON，原片不出本机。
- **有工程文件** → 第一段"造风格模板"用**解析工程文件**拿到零误差参数，比让 AI 猜画面准十倍。

---

## 1. 技术栈总表（每个环节用什么、跑在哪、怎么调）

| 环节 | 工具 / 项目（GitHub 或官方） | 本地 / 云端 | 用途 | 怎么调用 |
|---|---|---|---|---|
| ① 解析工程文件 | 剪映 `draft_content.json` + 自写 Python 解析脚本 | 本地 | 提取关键帧/转场/字幕/图片叠加的**精确参数 + 素材** | 直接 `json.load` 读文件 |
| ② 中文语音+说话人 | **FunClip**（`github.com/modelscope/FunClip`，阿里通义语音实验室/达摩院背景，GitHub） | 本地 | ASR 转写 + 说话人分离（老师/学生） | 命令行 `python funclip/launch.py` 或 `python funclip/videoclipper.py` |
| ③ 场景/镜头检测 | **PySceneDetect**（GitHub） | 本地 | 切镜头，抽代表帧 | 命令行 `scenedetect` |
| ④ 看画面理解 | **qwen-vl-plus**（阿里 DashScope，云端） | 云端 API | 描述每帧"谁在做什么/有无板书" | DashScope SDK |
| ⑤ 翻译指令（大脑） | **DeepSeek** `deepseek-chat` / **qwen-plus**（云端） | 云端 API | 风格说明书 + 内容地图 → EDIT 操作 JSON | OpenAI 兼容 SDK |
| ⑥ 抽帧 | **ffmpeg** | 本地 | 按场景抽关键帧图 | 命令行 `ffmpeg` |
| ⑦ 套特效出片 | **ffmpeg**（`zoompan` / `overlay`） | 本地 | 关键帧缩放 + 图片叠加，确定性执行 | 命令行 `ffmpeg -filter_complex` |

**GitHub 工具的本质**：FunClip / PySceneDetect / ffmpeg 都是**代码**，你 `clone` / `pip install` 后在**自己电脑本地运行**。它们不是云服务；只有第 ④⑤ 步你主动去调模型 API 时才碰云端，且这步可换成本地 ollama（套餐 A）。

### 1.1 已核实的 GitHub 仓库地址（2026-07-26 逐个数确认）

下面这些仓库都已核实，可直接 `git clone` / `pip install`。区分**套餐 B 实际用到**（✅）与**备选/参考仓库**（○）：

| 工具 | 仓库地址 | 用途 | 套餐 B 是否用 |
|---|---|---|---|
| **FunClip**（中文 ASR + 说话人） | `https://github.com/modelscope/FunClip` | 转写 + 按说话人剪辑；v2.x 自带 LLM 智能剪辑（Qwen/GPT） | ✅ 用（旧名 `alibaba-damo-academy/FunClip` 已废弃，勿再用） |
| **PySceneDetect**（场景检测） | `https://github.com/Breakthrough/PySceneDetect` | 镜头/场景切换检测，切语义段 | ✅ 用 |
| **ffmpeg**（抽帧 + 特效执行） | 下载 `https://ffmpeg.org` ／ 源码 `https://github.com/FFmpeg/FFmpeg` | 关键帧（zoompan）+ 图片叠加（overlay）+ 导出 | ✅ 用 |
| **WhisperX**（ASR 备选） | `https://github.com/m-bain/whisperX` | FunClip 的备选 ASR 基座；说话人分离需免费 HF token | ○ 备选（FunClip 已含 ASR+说话人） |
| **PreenCut**（自然语言定位片段） | `https://github.com/cellinlab/PreenCut`（另有 fork `roothch/PreenCut`） | 参考其"WhisperX+LLM 把自然语言转带时间戳片段"范式 | ○ 参考架构 |
| **OpenMontage**（agent 化视频生产） | `https://github.com/mencelot/OpenMontage` | 参考其 skill / 工作流分层架构（偏从零生成，不直接剪你素材） | ○ 参考架构 |
| **Video-Analyzer**（本地 VLM 看画面） | `https://github.com/byjlw/video-analyzer` | 套餐 A 本地"看画面"用（Llama 11B Vision + Whisper，可完全离线） | ○ 仅套餐 A |

**云端模型（无 GitHub 仓库，只有 API key，套餐 B 调这两个）**：
- VLM 看画面：`qwen-vl-plus`（阿里云百炼 DashScope）
- LLM 大脑：`deepseek-chat`（DeepSeek）/ `qwen-plus`（DashScope）

> 一句话区分：GitHub 上的都是**本地跑的代码**；`qwen-vl-plus` 与 `deepseek-chat` 是**云端 API**，靠 key 调用，没有仓库可 clone。

---

## 2. 环境准备（你要在电脑上做的操作）

### 2.1 装基础软件
```bash
# 1) 装 ffmpeg（Windows 用 scoop 或官网压缩包，放到 PATH）
scoop install ffmpeg        # 或去 https://ffmpeg.org 下载，解压后把 bin 加入 PATH

# 2) 装 Python 3.10+（已有可跳过），并建虚拟环境
python -m venv venv
venv\Scripts\activate

# 3) 装依赖
pip install git+https://github.com/modelscope/FunClip.git
pip install scenedetect[opencv]
pip install openai dashscope
```

### 2.2 准备工程文件
- 手机剪映与 PC 剪映登录**同一账号** → 云草稿同步。
- 在 PC 剪映打开那个成品草稿，关闭剪映。
- 工程文件路径形如：
  ```
  C:\Users\X360\AppData\Local\JianyingPro\User Data\Projects\com.lanying.editor.draft\<草稿ID>\draft_content.json
  ```
- 同目录的 `materials/` 里放着你的**图片叠加素材**（高亮框、问卡片、Logo 等 PNG），后面要复用。

### 2.3 配置云端 key（套餐 B 必需）
- **DashScope（通义）API key**：注册阿里云百炼控制台 → 拿到 key，用于 `qwen-vl-plus`（看画面）和 `qwen-plus`（大脑备选）。
- **DeepSeek API key**：平台申请，用于 `deepseek-chat`（大脑）。
- 把 key 写进环境变量（**不要写死在脚本/ Skill 里**）：
  ```bash
  setx DASHSCOPE_API_KEY "你的key"
  setx DEEPSEEK_API_KEY "你的key"
  ```

### 2.4 建项目目录
```
D:\video-edit-agent\
├─ ref/                 # 参考成品视频 + 工程文件
├─ assets/              # 从工程文件 materials 拷出来的图片叠加素材
├─ input/               # 每次新视频放这里
├─ work/                # 中间产物（frames/、content_map.json、style_spec.json）
├─ output/              # 成片
├─ scripts/             # 解析/预处理/生成脚本
└─ skill_style.md       # 第一段产出的"剪辑风格说明书"
```

---

## 3. 第一段：一次性反推"剪辑风格模板"（有工程文件，最准）

> 这一段**只做一次**。产出两件东西：`skill_style.md`（给 LLM 看的风格说明书）+ `assets/`（可复用的图片素材）。

### 3.1 解析工程文件 → 拿到精确特效参数
`draft_content.json` 是剪映完整工程，记录轨道、每段素材、动画关键帧、文字样式、转场、画布。字段名随版本略有差异，核心思路是：
- `tracks`：视频轨 / 音频轨 / 文本轨。
- 视频轨 `clips` 的 `animations`：含 `in`（入场）、`out`（出场）、`body`（关键帧列表，如 `scale` 1.0→1.15）。
- 文本轨 `clips`：字幕字体、字号、颜色、描边、动画。
- `materials`：引用的图片/视频素材 id，对应 `materials/` 目录里的实际文件。

**解析脚本骨架（`scripts/parse_draft.py`）**：
```python
import json, os, shutil, glob

DRAFT = r"D:\video-edit-agent\ref\draft_content.json"
ASSET_DIR = r"D:\video-edit-agent\ref\materials"
OUT_SPEC = r"D:\video-edit-agent\work\style_spec.json"
OUT_ASSETS = r"D:\video-edit-agent\assets"

with open(DRAFT, encoding="utf-8") as f:
    draft = json.load(f)

spec = {"keyframes": [], "text_style": {}, "transitions": [], "overlays": []}

for track in draft.get("tracks", []):
    for clip in track.get("clips", []):
        ch = clip.get("channel", "")
        # 关键帧：在 animations 里找 scale/position 的变化
        anims = clip.get("animations", {})
        if "body" in anims or "in" in anims or "out" in anims:
            spec["keyframes"].append({
                "start": clip.get("start"), "end": clip.get("end"),
                "animations": anims
            })
        # 文本轨 → 字幕样式
        if ch == "text":
            spec["text_style"] = clip.get("text", {})
        # 图片叠加（贴纸/素材）→ 记录素材并复制文件
        if ch == "sticker" or clip.get("material_type") == "image":
            mid = clip.get("material_id")
            spec["overlays"].append({"material_id": mid, "animations": anims})

# 复制图片素材到 assets，供第二段复用
os.makedirs(OUT_ASSETS, exist_ok=True)
for p in glob.glob(os.path.join(ASSET_DIR, "*")):
    if p.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        shutil.copy(p, OUT_ASSETS)

with open(OUT_SPEC, "w", encoding="utf-8") as f:
    json.dump(spec, f, ensure_ascii=False, indent=2)
print("已导出 style_spec.json 与图片素材")
```
> 注：剪映不同版本字段名不完全一致，运行后看 `style_spec.json` 再按需微调字段路径即可。重点是拿到**关键帧数值、字幕样式、转场类型、图片素材文件名**。

### 3.2 给参考视频也跑"理解层" → 拿到语义触发条件
工程文件告诉你"在哪、加了什么特效"，但没告诉你"为什么加"（因为老师在写公式）。所以要给**同一个参考视频**跑 ②~④，得到每段在做什么，再把特效**对齐**到语义：
```bash
# ② 中文 ASR + 说话人（FunClip 真实命令，详见仓库 README）
#    Web UI: python funclip/launch.py        → 浏览器 localhost:7860 上传视频
#    CLI:    python funclip/videoclipper.py --stage 1 --file <视频> --output_dir work
python funclip/videoclipper.py --stage 1 --file ref\成品.mp4 --output_dir work  > work\ref_asr.log

# ③ 场景检测 + ⑥ 抽代表帧
scenedetect -i ref\成品.mp4 detect-content list-scenes
ffmpeg -i ref\成品.mp4 -vf "select='gt(scene,0.4)',showinfo" -vsync vfr work\frames\ref_%04d.jpg

# ④ 用 qwen-vl-plus 描述每帧（见第 6 节 prompt A）
python scripts/describe_frames.py      # 内部调 DashScope，输出 work\ref_frames_desc.json
```

### 3.3 LLM 把"特效参数 + 语义"翻译成风格说明书
把 `style_spec.json` + `ref_asr.json` + `ref_frames_desc.json` 喂给 DeepSeek，让它产出**自然语言风格说明书** `skill_style.md`（这是后面 Skill 的核心内容）。

**Prompt B（第一段·风格翻译）** 见第 6 节。

输出示例（`skill_style.md` 片段）：
```markdown
## 剪辑风格规则
- 触发"老师在写公式/板书"的段落 → 关键帧: scale 1.0→1.15 缓慢推近(4s)；叠加 assets/highlight.png 高亮框，淡入0.3s
- 触发"学生提问"的段落 → 叠加 assets/ask_card.png（"问"卡片），停留至该段结束
- 字幕: 黑底白字、思源黑体 Bold、字号36、描边10px，统一位置底部居中
- 转场: 统一 0.2s 叠化；片头 3s 模板 + Logo 缩放出现
```

### 3.4 固化
- `skill_style.md` + `assets/` 就是你的"剪辑模板"，以后每次复用，不用重写。
- 若做成 WorkBuddy Skill，把这些内容写进 `SKILL.md` 的"风格规格"段即可（见后续）。

---

## 4. 第二段：每次出新片（理解新视频 + 套风格）

### 4.1 本地预处理 → 产出 content_map.json
```bash
# 把新视频丢进 input/，然后（FunClip 真实命令，详见仓库 README）：
python funclip/videoclipper.py --stage 1 --file input\new.mp4 --output_dir work  > work\asr.log
scenedetect -i input\new.mp4 detect-content list-scenes
ffmpeg -i input\new.mp4 -vf "select='gt(scene,0.4)',showinfo" -vsync vfr work\frames\new_%04d.jpg
python scripts/describe_frames.py      # qwen-vl-plus 描述每帧
# 汇总成 content_map.json：[{t_start,t_end,speaker,scene_desc,frame}]
```
`content_map.json` 样例：
```json
[
  {"t_start":0,  "t_end":12, "speaker":"老师", "scene_desc":"面对镜头讲解概念", "frame":"work/frames/new_0001.jpg"},
  {"t_start":12, "t_end":25, "speaker":"老师", "scene_desc":"在白板写公式",     "frame":"work/frames/new_0002.jpg"},
  {"t_start":25, "t_end":31, "speaker":"学生", "scene_desc":"提问",             "frame":"work/frames/new_0003.jpg"}
]
```

### 4.2 云端 LLM 映射 → EDIT 操作 JSON
把 `skill_style.md` + `content_map.json` 发给 DeepSeek，输出结构化 EDIT 列表。
**Prompt C（第二段·指令映射）** 见第 6 节。

EDIT 操作 schema（约定格式，给 ffmpeg 用）：
```json
[
  {"op":"zoom_keyframe","target":[12,25],"params":{"scale":"1.0->1.15","dur":4}},
  {"op":"overlay","target":[12,25],"params":{"img":"assets/highlight.png","fade":0.3}},
  {"op":"overlay","target":[25,31],"params":{"img":"assets/ask_card.png"}}
]
```

### 4.3 本地 ffmpeg 执行 → 成片
`scripts/build.py` 读取 EDIT JSON，生成 `ffmpeg -filter_complex` 命令：
- **关键帧缩放（zoompan）**：
  ```bash
  ffmpeg -i input\new.mp4 -vf "zoompan=z='min(zoom+0.0015,1.15)':d=120:s=1920x1080:fps=30" -ss 00:00:12 -to 00:00:25 work\seg_zoom.mp4
  ```
- **图片叠加（overlay + 淡入）**：
  ```bash
  ffmpeg -i work\seg_zoom.mp4 -i assets\highlight.png -filter_complex \
    "[1:v]fade=t=in:st=0:d=0.3[ov];[0:v][ov]overlay=0:0" work\seg_ov.mp4
  ```
- 各段处理完用 `ffmpeg concat` 或再统一接转场，输出到 `output/new_edited.mp4`。

> 第 4.3 步是**确定性**的：定位准了就一定出得来，不涉及 AI，所以最稳。

---

## 5. 完整调用顺序（一次性看清）

```
【第一段·一次性】
ref/成品.mp4 + draft_content.json
  ├─ parse_draft.py        → style_spec.json + assets/      [本地]
  ├─ FunClip + scenedetect + qwen-vl-plus → ref 的语义地图  [本地+云端]
  └─ DeepSeek(Prompt B)    → skill_style.md                 [云端]
                        ↓ 固化成模板（以后复用）

【第二段·每次】
input/new.mp4
  ├─ FunClip + scenedetect + qwen-vl-plus → content_map.json [本地+云端]
  ├─ DeepSeek(Prompt C): skill_style.md + content_map → EDIT.json [云端]
  └─ ffmpeg(zoompan/overlay) → output/new_edited.mp4        [本地]
```

---

## 6. 提示词汇总（可直接复制）

### Prompt A — VLM 看画面（qwen-vl-plus，描述每帧）
```
你是一名教学视频分析员。请看这张画面，用一句话描述：
1) 谁在画面中（老师/学生/只有屏幕/白板）；
2) 正在发生什么（讲解/写公式板书/操作软件/展示PPT/提问/答疑）；
3) 画面里有没有板书、公式或屏幕内容。
只输出关键事实，不要发挥。
```

### Prompt B — 第一段·风格翻译（DeepSeek，工程文件 → 说明书）
```
你是视频剪辑风格提取器。输入包含两部分：
A) style_spec.json：从剪映工程文件解析出的精确特效参数（关键帧数值、字幕样式、转场、图片素材）。
B) 同一参考视频的语义地图（每段时间戳 + 说话人 + 画面描述）。
请输出一份"剪辑风格规则"说明书（Markdown），规则格式为：
「触发条件（语义）→ 应用特效（参数来自 A，素材文件名来自 assets/）」。
要求：参数必须来自 A 的真实数值；触发条件必须是可判断的语义（如"老师写公式"），不要写死时间码。
```

### Prompt C — 第二段·指令映射（DeepSeek，新视频 → EDIT）
```
你是视频剪辑指令映射器。已知：
1) 剪辑风格规则（skill_style.md）：〔粘贴风格规则〕
2) 新视频内容地图 content_map.json：〔粘贴〕
请按风格规则，把每条语义触发匹配到 content_map 的时间段，输出 EDIT 操作 JSON：
[{"op":"zoom_keyframe"|"overlay"|"transition","target":[start_sec,end_sec],"params":{...}}]
要求：target 用 content_map 的真实时间段；params 严格沿用风格规则里的数值与素材文件名；不要臆造素材。
```

---

## 7. 优点

1. **精确**：有工程文件 → 关键帧/字幕/转场/图片参数零误差提取，不用 AI 猜画面，远超"抽帧让 VLM 反推"。
2. **安全**：视频与所有剪辑执行在本地；云端只收压缩小图 + JSON 文字，原片不出本机。
3. **便宜快速**：重活在本地（ffmpeg），云端只做"看+想"两步，token 消耗小；DeepSeek/qwen 单价很低。
4. **不挑显卡**：推理在云端，你普通电脑即可跑（FunClip ASR 有 GPU 更快但非必须）。
5. **可复用**：第一段产出的 `skill_style.md` 一次写、反复用；之后每次只给新视频，不必重写风格。
6. **可控**：第 4.3 步 ffmpeg 是确定性执行，定位准就必出片，不靠 AI 临场发挥。

## 8. 不足 / 风险

1. **VLM 时间定位不精确**："老师开始写公式的精确瞬间"可能差几秒，导致特效起点偏移 → 建议保留一个"定位预览 + 人工微调"checkpoint（OpenMontage 也这么做）。
2. **工程文件 ≠ 导出 mp4 完全一致**：剪映版本差异、个别特效不落入 JSON、或素材引用丢失 → 解析后需人工核对 `style_spec.json` 与成片是否对得上。
3. **依赖云 API**：需联网 + 付费 key；若厂商限流/涨价/停用会影响可用性；小图+JSON 虽非原片，但仍属数据出本机（涉敏内容需评估）。
4. **说话人分离有上限**：FunClip 的 CAM++ 对中文好，但多人同时说话、重叠语音会标错说话人。
5. **语义误判**：LLM 可能把"写公式"误判成"讲解"，导致该加特效的没加 → 靠 checkpoint + 风格规则写得具体来缓解。
6. **长视频预处理耗时**：15 分钟视频的 ASR + 抽帧是分钟级，属异步任务，需要进度反馈机制（做成产品时要加队列）。
7. **工程文件结构随版本变**：`draft_content.json` 字段可能升级，解析脚本需随剪映版本微调。
8. **有工程文件是前提**：若以后只有 mp4 没有工程（比如别人发的素材），第一段要退回"抽帧+VLM 反推"，精度下降。

## 9. 落地 Checklist

- [ ] 装 ffmpeg / Python 3.10+ / git
- [ ] `pip install` FunClip、PySceneDetect、openai、dashscope
- [ ] 剪映云草稿同步，拿到 `draft_content.json` + `materials/`
- [ ] 配 `DASHSCOPE_API_KEY` + `DEEPSEEK_API_KEY` 环境变量
- [ ] 建 `D:\video-edit-agent\` 目录结构
- [ ] 跑 3.1 解析工程 → 核对 `style_spec.json`
- [ ] 跑 3.2~3.3 → 产出 `skill_style.md` + `assets/`
- [ ] 拿一段新视频跑 4.1~4.3 → 出第一版成片
- [ ] 人工看 checkpoint，微调风格规则 / 解析字段
- [ ] （可选）把 `skill_style.md` + 脚本封装成 WorkBuddy Skill 或 n8n 工作流

---
*本方案基于套餐 B + 有剪映工程文件的前置条件。若后续改为"无工程文件"或"全本地（套餐 A）"，第一段与模型调用方式需相应调整。*
