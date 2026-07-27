# AI 智能剪辑（教学视频 · 理解内容后按指令出片）方案调研

> 适用前提：素材已拍完、真实场景 + 人员声音 + 实时画面；目标是让 AI **看懂视频内容**，按你的自然语言指令（而非固定时间码）在对应位置加关键帧 / 特效 / 图片剪辑手法。
> 整理时间：2026-07-26

---

## 0. 先纠正上一个回答的错误（重要）

上一轮我把你的需求当成了"固定时间点的工作流"，结论是"不用 agent、只要 workflow"。**这是错的。**

你的核心诉求是「AI 自己理解视频、按我的 prompt 定位到该处理的地方」——这恰恰**必须**用到 LLM / 视觉模型的理解与定位能力。区别只是：你不需要 AI「自由发挥创意」，但**必须**让它「看懂并定位」。这是"理解型"环节，不是"创意型"环节，但它依然需要模型。

所以正确的说法是：**你的系统里 AI 是必需零件，但它是被约束在"理解 + 定位"这个框里，而不是让它当导演乱发挥。**

---

## 1. 你的需求到底属于哪类问题

- **和 AI 漫剧 / 短剧不同**：那些是"从无到有生成新 footage"（文生视频、图生视频）。你的是**在已有真实素材上做理解 + 编辑**，属于 *real-footage editing / video understanding / retrieval* 这一类，不是 generation 类。
- **学术名字叫 Video Temporal Grounding（VTG，视频时序定位）**：给定一句自然语言，模型在视频里找出对应的起止时间戳。这正是"按 prompt 定位"的底层问题。
- 你的额外难点是**多模态**：既要懂"声音/谁在说话"（ASR + 说话人分离），又要懂"画面里在干嘛"（视觉理解），还要把两者对齐到时间轴。

---

## 2. 正确的系统架构：三阶段混合（哪里要 AI，哪里不要）

```
你发素材 + 一句指令（如"在老师写公式处加放大+高亮框"）
        │
   【阶段1 · 内容理解】── 需要 AI/VLM
   FunASR/WhisperX 转写(词级+说话人) + PySceneDetect 镜头切换
        + VLM 抽关键帧描述画面(板书/公式/老师/学生)
        → 产出 video_content_map.json（时间轴分段，每段带说话人/场景/画面/字幕）
        │
   【阶段2 · 指令映射】── 需要 LLM
   把"你的指令 + content_map"交给 LLM
        → 输出结构化 EDIT 操作列表：
          [{op:zoom_keyframe, target:<匹配"写公式"的段>, params:{...}},
           {op:highlight_box,  target:<...>, params:{...}}]
        │
   【阶段3 · 确定性执行】── 不需要 AI
   用 ffmpeg / MoviePy / 剪映工程文件，逐条套用"编辑原语库"
        → 成片
```

- **阶段 1、2 必须用模型**（理解 + 定位），但都是**有标准答案的约束任务**，可审计、可回退。
- **阶段 3 是纯确定性操作**（缩放关键帧、高亮框、图片叠加、转场、字幕）——只要定位准，执行 100% 稳定。
- 这整套就是「**workflow 为骨架 + 理解型 AI 节点为零件**」，不是"纯 workflow"，也不是"纯 agent"。

---

## 3. 真实可查的项目 / 方法（按阶段分类，附 GitHub）

### 阶段1 · 内容理解（中文语音 + 说话人 + 场景 + 画面）
| 项目 | 地址 | 为什么对口 |
|---|---|---|
| **FunClip（阿里达摩院）** | github.com/alibaba-damo-academy/FunClip | **中文 ASR 最强**：FunASR Paraformer + CAM++ 说话人识别，原生支持中文口音；CLI 两阶段（`stage1` 识别 / `stage2` 剪辑）可脚本化。最贴合你"人员声音 + 中文教学"。 |
| **WhisperX** | github.com/m-bain/whisperx | 词级时间戳 + 说话人分离（pyannote），多语言，是研究/工程基座。 |
| **PySceneDetect** | github.com/Breakthrough/PySceneDetect | 镜头/场景切换检测（ContentDetector），把长视频切成语义段，是理解层的"分块"工具。 |
| **Video-Analyzer** | 搜索 "Video-Analyzer Jason BYJL Wong" | 本地运行、隐私安全：Llama-11B 视觉模型 + Whisper，**逐关键帧"看懂"画面**（谁、在做什么、什么场景），直接产出结构化视频描述。适合教学录像批量理解。 |
| **Qwen-VL / GPT-4V** | 通义千问视觉版 / OpenAI | 通用视觉理解，用来给抽出的关键帧打"画面语义标签"，供阶段2定位。 |

### 阶段2 · 指令映射（自然语言 → 定位片段）
| 项目 | 地址 | 为什么对口 |
|---|---|---|
| **PreenCut** | github.com/cellinlab/PreenCut（镜像 github.com/roothch/PreenCut） | **最贴近你的需求**：WhisperX 转写 + DeepSeek/豆包 LLM 语义理解，自然语言一句"找出所有产品 Demo"→ 输出 `(start, end, summary, tags)` 四元组 → ffmpeg 导出。它的"LLM 把指令转成带时间戳片段"就是阶段2范式。还支持换 prompt 二次分析不重跑语音。 |
| **OpenMontage** | github.com/mencelot/OpenMontage | **架构蓝图**（不是拿来直接剪你的素材）：400+ agent skills，把"有什么能力(tools) / 怎么用(skills) / 底层原理"三层分离；自然语言 → 读 manifest → 读 stage skill → 调工具 → 自我审查 → 人工 checkpoint。你做 skill 时直接抄它的分层思路。 |
| **VTG 学术研究**（见第4节） | VTG-LLM / MarkIt / GroundVTS | "自然语言 → 精确时间戳"的算法底座。 |

### 阶段3 · 确定性执行（特效 / 关键帧 / 图片手法）
- **ffmpeg `filter_complex`**：缩放/平移关键帧（`zoompan`）、画中画、叠加图片（`overlay`）、转场、字幕烧入。参数化后完全可复现。
- **MoviePy（Python）**：比裸 ffmpeg 更好写，关键帧动画、clip 合成都方便。
- **剪映工程文件**：导出的 `draft_meta_info` + `content/tracks` 是 JSON，AI 直接改这两个文件即可"套母版 + 加特效"，不用动鼠标（适合你不想碰命令行时）。
- **OpenMontage 的 Remotion / Video Stitch / Video Trimmer**：现成的"组装、交叉淡化、精确裁剪"工具参考。

### 明确不推荐给你的（避免走偏）
- **MovieAgent**（github.com/showlab/MovieAgent）：从剧本**生成**长视频，属于 generation 类，跟你的"编辑已有素材"不是一回事，仅作架构参考，不要直接套。

---

## 4. 学术支撑：Video Temporal Grounding（VTG）

你的"按 prompt 定位"在学术界就是 VTG 任务。近年关键进展（都可在 arXiv 查到）：
- **VTG-LLM**：把时间戳知识注入视频 LLM，提升定位精度。
- **MarkIt（arXiv 2604.25886）**：免训练框架，把查询转成"画面上的语义标记 + 帧序号"，让 Vid-LLM 输出更可靠的时间边界——**特别适合"在写公式的瞬间加特效"这种细粒度定位**。
- **GroundVTS / Grounded-VideoLLM**：查询引导的视觉 token 采样，提升"重点时刻"的定位 mIoU / mAP。

结论：你想要的"理解 + 定位"是**有成熟研究和开源实现支撑**的方向，不是空中楼阁。

---

## 5. 最适合你的落地方法（推荐技术栈 + 步骤）

**推荐栈（中文优先、本地可跑、免费开源）：**
> FunClip（中文 ASR + 说话人） + PySceneDetect（场景） + Qwen-VL / Video-Analyzer（画面理解） + ffmpeg / MoviePy（特效执行）

**最小可用步骤：**
1. **跑内容理解**：FunClip 出词级转写 + 说话人标签；PySceneDetect 切镜头；抽关键帧用 Qwen-VL 打"画面语义"标签。→ 生成 `video_content_map.json`。
2. **写指令映射 prompt（一次写好，反复用）**：给 LLM 的模板 = "根据下面的视频内容地图，执行用户指令，只输出 JSON 操作列表，字段含 op / target(引用 content_map 里的段) / params"。
3. **定义"编辑原语库"（一次写好，反复用）**：zoom_keyframe、highlight_box、slow_motion、insert_image_overlay、transition、subtitle_style 各自的 ffmpeg/MoviePy 参数。
4. **执行**：读阶段2的操作列表，逐条套阶段3原语 → 成片。
5. **人工 checkpoint**：定位不准的 1–2 段手动微调（见第7节为什么需要）。

---

## 6. 回答你最关心的：做成 skill 还是 workflow / agent？

**结论：做成 WorkBuddy 的 Skill，里面用 Workflow 串起"理解型 AI 节点"。三者不冲突，是封装关系。**

Skill 不是"一次性脚本"，而是一份**可复用的方法论 + 触发器**。它把上面第5节的 3 件"一次写好"的资产全部固化：
- 阶段1 的分析 Pipeline（怎么跑 FunClip + PySceneDetect + VLM）
- 阶段2 的**指令映射 prompt 模板**（怎么把你的话转成 EDIT 操作）
- 阶段3 的**编辑原语库**（每种特效的参数）

**关于"每次 prompt 不是都要重写吗？"——不会。** 你每次只给一句**简短的创作 brief**，例如：
> "按我的教学模板：老师写公式处加放大关键帧+高亮框，学生提问处插'问'字卡片，片头统一 3 秒。"

Skill 里的 LLM 会拿**这次刚算好的 `video_content_map`** 去自动定位"写公式的段""学生提问的段"，再套原语库出片。**你重写的是那一句 brief（本来就该你定），而不是整套方法论。** 这正是 skill 的价值：方法论固化一次，创作意图每次一句话。

所以：✅ 适合做 skill；✅ skill 内部用 workflow 串联；✅ 其中阶段1/2 是受约束的 AI 节点（不是自由发挥的 agent）。

---

## 7. 诚实的局限 & 必须保留的人工确认点

- **VLM 时间定位不是 100% 准**：对"写公式的精确瞬间"这类细粒度，可能差几秒。保留一个"定位结果预览 + 人工确认/微调"的 checkpoint（OpenMontage 也是这么做的）。
- **说话人分离**：中文用 FunClip 的 CAM++ 效果好；多人、重叠说话仍可能误判，关键片段人工看一眼。
- **阶段3 特效本身很稳**：一旦定位准，缩放/高亮/叠加都是确定性操作，不会翻车。
- **算力**：WhisperX / VLM 有 GPU 更快，CPU 也能跑（慢）。本地模型（Qwen-VL、Llama-11B-Vision via ollama）可保隐私。
- **版权/隐私**：教学视频若在本地跑，不上传云端最稳妥（Video-Analyzer、FunClip 都支持本地）。

---

## 8. 下一步我可以帮你做什么

1. **直接帮你生成一个 WorkBuddy Skill**（教学视频 AI 剪辑）：把阶段1/2/3 的方法论、prompt 模板、编辑原语库全部写成 `SKILL.md`，以后你说一句"按我的教学模板剪这段"即可调用。
2. **先把"编辑原语库"和"指令映射 prompt"写成可照抄的配置模板**，你填自己的具体数值（缩放比例、高亮色、转场类型）。
3. **帮你本地搭一套最小可用管线**（FunClip + PySceneDetect + ffmpeg 脚本），跑通一条真实视频。

你想从哪一步开始？
