# AI 教学视频剪辑 · 完整实操流程 v2

> **v2 核心改动**：最终输出直接是 mp4 视频文件（MoviePy 渲染），不再需要打开剪映。
> 适用人：用手机剪映做教学视频的老师，想把"按风格出片"自动化。
> 创建时间：2026-07-26

---

## 0. 你的三个核心问题（先回答）

### Q1：第一段"分析风格"，我需要提供什么？

| 你必须提供 | 为什么需要 | 怎么获取 |
|---|---|---|
| **一段你做好的成品视频**（mp4） | 这是"金标准"，AI 从这里面学你的剪辑风格 | 你已经在剪映里手动剪好的那版 |
| **图片叠加素材**（PNG/JPG） | 高亮框、"问"卡片、Logo 等可复用素材 | 从剪映的 `materials/` 目录拷贝出来 |
| ⭐ **剪映工程文件** `draft_content.json`（强烈推荐） | 精确提取关键帧参数、文字样式、转场类型，比 AI 猜画面准十倍 | PC 剪映云草稿同步 → 工程目录下 |

> **如果你不给工程文件会怎样？** 也能做，但 AI 只能靠 VLM"看"视频反推特效参数（比如缩放从 1.0→? 只能估算），精度会下降。

### Q2：最终能直接出完整视频，不用再打开剪映吗？

**可以。这是 v2 方案的设计目标。**

最终执行层用 **MoviePy（Python 视频编辑库）** 渲染成 mp4。整个流程是：
```
新视频输入 → AI 分析 → 匹配风格 → MoviePy 渲染 → 直接出 mp4 成品
```
你不需要打开任何软件，拿到的是一个可以直接上传/分发的视频文件。

**但要诚实说**：MoviePy 渲染的效果精度不如剪映原生引擎。如果你的剪辑风格包含非常精细的关键帧缓动曲线（贝塞尔曲线）、复杂的文字渐变/描边/阴影效果，MoviePy 做不到 100% 还原。不过对于教学视频最常见的操作——**缓慢推进缩放、图片叠加/淡入淡出、字幕烧录、片段拼接**——MoviePy 完全够用。

### Q3：能做成一个 Skill 吗？

**可以。** 整个流程可以封装成一个 WorkBuddy/Claude Code 的 Skill（`SKILL.md`）。

做成 Skill 后你每次只需要：
1. 把新拍的原始视频放到 `input/` 文件夹
2. 对 AI 说一句："**按我的教学模板剪辑这段**"
3. 等待 AI 跑完管线 → 去 `output/` 拿成品

Skill 内部固化了你第一段学会的"剪辑风格说明书"，不需要每次重写。

---

## 1. 修正后的完整架构（一图看清）

```
【第一段 · 一次性"学风格"】
你提供：成品.mp4 + 素材PNG + (可选)draft_content.json
                │
    ┌───────────┼───────────┐
    ▼           ▼           ▼
  FunClip    PySceneDetect  ffmpeg抽关键帧
  (ASR+说话人) (镜头切换)    (每段起止双帧)
    │           │           │
    └───────────┼───────────┘
                ▼
        qwen-vl-plus × 2
        （看双帧对比 → 结构化标签）
                │
                ▼
         DeepSeek（风格翻译）
        工程参数 + 语义标签 → "风格说明书"
                │
                ▼
    ┌───────────────────────┐
    │  skill_style.md       │  ← 剪辑风格说明书（固化的）
    │  style_labels.json    │  ← 结构化标签-特效映射
    │  assets/              │  ← 可复用图片素材
    └───────────────────────┘
         ▲ 以后不再重复 ▲


【第二段 · 每次"出片"】
你提供：新视频.mp4 + (可选)一句话brief
                │
    ┌───────────┼───────────┐
    ▼           ▼           ▼
  FunClip    PySceneDetect  ffmpeg抽关键帧
    │           │           │
    └───────────┼───────────┘
                ▼
        qwen-vl-plus × 2
        （看双帧 → 结构化标签）
                │
                ▼
    ┌──────────────────────────┐
    │  确定性标签匹配引擎       │  ← 不再是 LLM！
    │  "writing_on_board" →    │
    │  命中风格规则#3 →         │
    │  zoom + highlight_box    │
    └──────────────────────────┘
                │
                ▼
          EDIT 操作 JSON
                │
                ▼
    ┌──────────────────────────┐
    │  MoviePy 渲染引擎        │  ← 输出 mp4
    │  - zoom 关键帧           │
    │  - 图片叠加 + 淡入淡出   │
    │  - 字幕烧录              │
    │  - 片段拼接 + 转场       │
    │  - 音频混合 (BGM)        │
    └──────────────────────────┘
                │
                ▼
         output/成片.mp4  ← 最终产物
```

---

## 2. 你现在需要做的事（分三步）

### 第一步：准备"学风格"的材料（你来做，一次性）

把所有东西放到一个文件夹：

```
D:\video-edit-agent\
├─ ref\                        # ← 你把参考材料放这里
│   ├─ 成品.mp4                #   你手动剪好的一段教学视频
│   ├─ draft_content.json      #   (推荐) 剪映云同步 → 复制过来
│   └─ materials\              #   从剪映工程目录拷出来的
│       ├─ highlight.png       #   高亮框
│       ├─ ask_card.png        #   "问"卡片
│       └─ logo.png            #   Logo
├─ assets\                     #   AI 会帮你整理到这里的复用素材
├─ input\                      #   以后每次新视频放这里
├─ work\                       #   中间文件（自动生成）
├─ output\                     #   成品输出（自动生成）
└─ scripts\                    #   Python 脚本
```

**具体操作**：
1. 把你手机剪映里的成品视频导出为 mp4，放到 `ref/`
2. 在 PC 上装剪映，登录同一账号 → 云草稿同步 → 找到那个成品草稿
3. 关闭剪映，去 `C:\Users\X360\AppData\Local\JianyingPro\User Data\Projects\com.lanying.editor.draft\<草稿ID>\` 目录
4. 把 `draft_content.json` 和 `materials/` 文件夹都复制到 `ref/`
5. 把你用到的贴纸/图片素材挑出来，放到 `ref/materials/`

> 如果你不方便同步到 PC 剪映、拿不到工程文件，也没关系——跳到后面的「方案 A（无工程文件）」即可。

### 第二步：AI 分析 + 生成风格模板（AI 来做）

AI 会执行以下操作：
1. 用 FunClip 对参考视频做中文语音识别 + 说话人分离
2. 用 PySceneDetect 检测镜头切换，把视频切成语义段落
3. 每段抽开头帧 + 结尾帧，送 qwen-vl-plus 对比理解（"这段发生了什么事"）
4. （如有工程文件）解析 `draft_content.json` 拿到精确的关键帧参数、文字样式
5. 把"什么语义 + 什么特效参数"对齐，生成结构化的风格规则
6. 产出 `skill_style.md`（给人看和给 AI 看）+ `style_labels.json`（给匹配引擎用）

### 第三步：验证 + 出新片（你 + AI）

1. 拿一段**新的原始教学视频**放到 `input/`
2. 对 AI 说"按模板剪"
3. AI 跑完 → 去 `output/` 看成片
4. 你检查效果，告诉 AI 哪里需要微调
5. AI 更新风格规则
6. 重复直到满意 → 固化为 Skill

---

## 3. 完整技术方案细节

### 3.1 工具清单（都装在 D 盘）

| 工具 | 类型 | 安装方式 | 用途 |
|---|---|---|---|
| **Python 3.10** | 运行时 | 已有 ✅ | 一切的基础 |
| **ffmpeg** | 可执行文件 | scoop / 官网下载 | 抽帧 + 音频处理 + 容器操作 |
| **FunClip** | Python 包 | `pip install git+https://...` | 中文语音识别 + 说话人分离 |
| **PySceneDetect** | Python 包 | `pip install scenedetect[opencv]` | 镜头/场景切换检测 |
| **MoviePy** | Python 包 | `pip install moviepy` | 视频合成 + 特效渲染（替代裸 ffmpeg） |
| **dashscope** | Python 包 | `pip install dashscope` | 调用 qwen-vl-plus（看画面） |
| **openai** | Python 包 | `pip install openai` | 调用 DeepSeek（LLM 大脑） |

全装在 `D:\video-edit-agent\venv\` 虚拟环境里，不污染系统。

### 3.2 云端 API（需要你申请 key）

| 服务 | 用途 | 费用 | 申请地址 |
|---|---|---|---|
| **阿里云百炼 DashScope** | `qwen-vl-plus` 看画面 | 按量付费，很便宜 | https://dashscope.aliyun.com |
| **DeepSeek** | `deepseek-chat` 风格翻译 | 按量付费，极便宜 | https://platform.deepseek.com |

> 两个 key 配成环境变量 `DASHSCOPE_API_KEY` 和 `DEEPSEEK_API_KEY`。

### 3.3 关键改进点（vs 原 B 方案）

| 改进 | 原方案 | v2 方案 | 收益 |
|---|---|---|---|
| VLM 抽帧 | 每段 1 张代表帧 | **每段起止双帧**对比 | 能判断"动作变化"，不止"画面状态" |
| VLM 输出 | 自由文本描述 | **结构化标签** JSON | 匹配引擎不用猜语义 |
| 指令映射 | LLM 做文本匹配 | **确定性 Python 匹配** | 快、免费、100% 可复现 |
| 执行引擎 | ffmpeg 裸命令 | **MoviePy Python 封装** | 可维护、支持复杂组合 |
| 最终产物 | ffmpeg 生成的 mp4 | **MoviePy 渲染的 mp4** | 效果更好、代码更清晰 |
| 音频 | ❌ 缺失 | **增加音频管线** | BGM 混合、音量调节 |

### 3.4 结构化标签体系（核心创新）

VLM 不再输出"老师站在白板前写公式"这种自由文本，而是输出**标准化标签列表**：

```json
{
  "segment_id": 3,
  "t_start": 12.5,
  "t_end": 25.0,
  "speaker": "teacher",
  "labels": [
    "teacher_visible",
    "writing_on_board", 
    "has_formula",
    "board_content_visible",
    "front_facing"
  ],
  "summary": "老师在白板上书写数学公式，面向白板",
  "frame_start": "work/frames/seg03_start.jpg",
  "frame_end": "work/frames/seg03_end.jpg"
}
```

风格规则也是标签匹配：

```json
{
  "rule_id": "highlight_formula",
  "trigger": {
    "required": ["writing_on_board", "has_formula"],
    "optional": ["teacher_visible"]
  },
  "actions": [
    {"op": "zoom_keyframe", "params": {"scale_start": 1.0, "scale_end": 1.15, "duration": 4}},
    {"op": "overlay", "params": {"img": "assets/highlight.png", "fade_in": 0.3, "position": "center"}}
  ],
  "description": "老师在写公式 → 缓慢推进 + 高亮框"
}
```

匹配逻辑变成一行代码：**`required_labels ⊆ segment_labels`**

---

## 4. 第一段详细步骤（你 + AI 协作）

### 步骤 1：你收集材料 → 放到 `ref/`

见上面"第一步"。做好后目录长这样：
```
D:\video-edit-agent\ref\
├─ 成品.mp4
├─ draft_content.json    ← 有最好，没有也行
└─ materials\
    ├─ highlight.png
    ├─ ask_card.png
    └─ logo.png
```

### 步骤 2：AI 跑内容理解管线

AI 依次执行：
```bash
# 2a. 中文语音识别 + 说话人分离
python -m funclip --stage 1 --file "ref/成品.mp4" --output_dir "work/ref"

# 2b. 场景检测
scenedetect -i "ref/成品.mp4" detect-content list-scenes -o "work/ref"

# 2c. 按场景抽关键帧（每段起止双帧）
python scripts/extract_keyframes.py --input "ref/成品.mp4" --scenes "work/ref/scenes.csv" --output "work/ref/frames"

# 2d. VLM 看每段双帧 → 输出结构化标签
python scripts/describe_segments.py --frames "work/ref/frames" --output "work/ref/content_map.json"
```

产出 `work/ref/content_map.json`：
```json
[
  {
    "segment_id": 0,
    "t_start": 0.0, "t_end": 8.5,
    "speaker": "teacher",
    "labels": ["teacher_visible", "lecturing", "front_facing", "ppt_visible"],
    "summary": "老师面向镜头讲解课程大纲，PPT在画面中"
  },
  {
    "segment_id": 1,
    "t_start": 8.5, "t_end": 22.0,
    "speaker": "teacher",
    "labels": ["teacher_visible", "writing_on_board", "has_formula", "board_visible"],
    "summary": "老师在白板上逐步推导数学公式"
  },
  {
    "segment_id": 2,
    "t_start": 22.0, "t_end": 30.0,
    "speaker": "student",
    "labels": ["student_visible", "asking_question", "front_facing"],
    "summary": "学生面向镜头提问"
  }
]
```

### 步骤 3：（如有工程文件）AI 解析精确参数

```bash
python scripts/parse_draft.py --draft "ref/draft_content.json" --materials "ref/materials" --output "work/ref/style_spec.json"
```

产出精确特效参数：
```json
{
  "zoom_keyframes": [
    {"scale_from": 1.0, "scale_to": 1.15, "duration_frames": 120, "easing": "ease_out"}
  ],
  "text_style": {
    "font": "思源黑体 Bold", "size": 36, "color": "#FFFFFF",
    "stroke_width": 10, "stroke_color": "#000000",
    "position": "bottom_center"
  },
  "transitions": [{"type": "crossfade", "duration": 0.2}]
}
```

### 步骤 4：AI 对齐"语义 + 特效参数" → 生成风格规则

把 `content_map.json` + `style_spec.json`（或仅 `content_map.json` 如果没有工程文件）→ 送给 DeepSeek 做一次性的对齐：

> Prompt: "把以下 A 部分（精确特效参数）和 B 部分（视频内容语义标签）对齐，输出风格规则 JSON。规则格式：{trigger: {required:[标签]}, actions:[{op, params}]}"

产出 `style_labels.json`（给匹配引擎用）和 `skill_style.md`（给人看+给 AI 看）。

### 步骤 5：你审核 + 微调

- 看 `skill_style.md`，确认"写公式→推进+高亮框""学生提问→问卡片"等规则是否正确
- 有不对的地方告诉 AI 修改
- 确认后固化，以后永不重做

---

## 5. 第二段详细步骤（每次出新片）

### 你做的（1 分钟）：
1. 把新拍的原始视频放到 `input/`
2. 对 AI 说："**按我的教学模板剪这段**"（或加一句特殊要求）

### AI 做的（全自动）：
```bash
# 1. 分析新视频（同第一段步骤2）
python -m funclip --stage 1 --file "input/新视频.mp4" --output_dir "work/new"
scenedetect -i "input/新视频.mp4" detect-content list-scenes -o "work/new"
python scripts/extract_keyframes.py --input "input/新视频.mp4" --scenes "work/new/scenes.csv" --output "work/new/frames"
python scripts/describe_segments.py --frames "work/new/frames" --output "work/new/content_map.json"

# 2. 标签匹配引擎（确定性，不调 LLM）
python scripts/match_style.py --content "work/new/content_map.json" --rules "style_labels.json" --output "work/new/edit_ops.json"

# 3. MoviePy 渲染成片
python scripts/render.py --input "input/新视频.mp4" --edit "work/new/edit_ops.json" --assets "assets/" --output "output/成片.mp4"
```

产出：`output/成片.mp4`，一个可以直接用的视频文件。

---

## 6. Skill 封装（一键调用）

当整个流程稳定后，封装为一个 WorkBuddy Skill（`SKILL.md`）。

你做成的 Skill 内部包含：
```
D:\video-edit-agent\
├─ SKILL.md                  ← Skill 主文件（AI 的操作手册）
├─ style_labels.json         ← 风格规则（标签匹配引擎用）
├─ skill_style.md            ← 风格说明书（给人看）
├─ assets\                   ← 复用素材
├─ scripts\                  ← Python 脚本
│   ├─ extract_keyframes.py
│   ├─ describe_segments.py
│   ├─ parse_draft.py       （仅第一段用）
│   ├─ match_style.py
│   └─ render.py
├─ input\
├─ work\
└─ output\
```

以后你每次只需：
1. 放视频到 `input/`
2. 说："**剪这段教学视频**，按我的模板"
3. 去 `output/` 拿成片

---

## 7. 你现在要做的 Checklist

### 现在立刻可以做（材料准备）

- [ ] **1.** 选一段你做好的成品教学视频（长度 3-15 分钟，最能代表你风格的那条）
- [ ] **2.** 导出为 mp4，放到 `D:\video-edit-agent\ref\`
- [ ] **3.** 把这条视频里用到的图片素材（高亮框、卡片、Logo）整理出来
- [ ] **4.** 决定要不要同步剪映云草稿拿工程文件：
  - ✅ **推荐**：PC 装剪映 → 登录同账号 → 云草稿同步 → 复制 `draft_content.json` 和 `materials/` → 精度最高
  - ⚠️ **跳过**：只有 mp4 + 素材 → AI 也能做，只是特效参数靠"看画面"反推，不够准

### AI 来做（工具安装 + 分析）

- [ ] **5.** 在 D 盘创建项目目录 + Python 虚拟环境
- [ ] **6.** 安装 ffmpeg（Windows）
- [ ] **7.** 安装 FunClip、PySceneDetect、MoviePy、dashscope、openai
- [ ] **8.** 运行内容理解管线，产出 `content_map.json`
- [ ] **9.** （如有工程文件）解析 → `style_spec.json`
- [ ] **10.** 对齐生成风格规则 → `style_labels.json` + `skill_style.md`
- [ ] **11.** 用一段新视频验证 → 输出成品 → 你确认效果

### 后续

- [ ] **12.** 微调规则直到满意
- [ ] **13.** 封装为 Skill
- [ ] **14.** 以后每次拍完新视频 → 一句话出片

---

## 8. 没有工程文件怎么办（备选方案）

如果你不方便拿到 `draft_content.json`：

| 你能得到的 | 缺失的信息 | 补救方法 |
|---|---|---|
| 精确缩放比例（1.0→?） | 不知道具体数值 | VLM 看视频估算（误差 ±10%） |
| 关键帧缓动曲线 | 不知道是 ease-in/ease-out/linear | 默认用 ease-out（最常用） |
| 文字字体/字号/描边 | 不完全精确 | VLM 看字幕截图估算 + 你手动确认 |
| 转场类型和时长 | 不知道具体参数 | 默认 0.2s 叠化（最常用简单转场） |
| 素材文件名 | 不知道 | 你自己命名（highlight.png, ask_card.png 等） |

**结论**：没有工程文件也能做，只是第一段需要你多确认几次参数。建议优先尝试拿工程文件。

---

## 9. 费用预估

| 操作 | 调用方 | 预估费用 |
|---|---|---|
| 学风格（第一段，一次性） | 抽帧描述 ~15 段 × 2 帧 = 30 次 VLM + 1 次 LLM 对齐 | ~¥0.5-1 |
| 出新片（第二段，每次 10 分钟视频） | ~20 段 × 2 帧 = 40 次 VLM + 0 次 LLM（用匹配引擎） | ~¥0.3-0.5 |
| 每月处理 20 条视频 | | ~¥6-10 |

> 以上为估算，实际取决于视频长度和分段数。DashScope 和 DeepSeek 都有免费额度。

---

*本方案基于以下假设：教学视频 3-15 分钟、剪辑手法为关键帧缩放 + 图片叠加 + 字幕 + 转场、使用手机拍摄中文教学场景。如果你的视频有其他特殊需求，方案需相应调整。*
