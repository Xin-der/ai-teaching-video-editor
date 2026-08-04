# 项目交接文档

> 最后更新: 2026-08-04 | 状态: v4 P1 前端重设计 + P1.1 核心修复 + P2 帧点评 + P3 选题灵感 全部完成

---

## 一、项目概述

**产品名**: 驾校内容优化工具

**核心目标**: 教练的素材视频/文字 → AI 生成 5 块《内容优化方案》（诊断 / 脚本改写 / 包装 / 转化话术 / 下期选题）→ 照着改、照着发，帮驾校同城获客

**当前阶段**: v4 P1（前端编辑风重设计）+ P1.1 核心修复（缓存隔离 + 输入泛化）+ P2 帧点评（自动挑问题帧 + VLM 诊断 + 标注框）+ **P3 选题灵感**（精选库 + AI 生成更多 + 轻量行业配置）全部完成（2026-08-04）。当前单测 顾问 18/18 + 前端 13/13 + 选题 9/9 + ASR 10/10。此前 v3.2（2026-08-02）ASR 抗噪升级：SenseVoice-Small + fsmn-vad + 驾考热词替换 paraformer，车内噪音场景转录从"碎片化不可读"提升到"成句可读、考试播报干净"；CPU 推理 ~38× 实时，完整 optimize 流程端到端验证通过。

---

## 二、v4（内容教练工作台方向）

**方向（2026-08-03 与用户确认）**: 从"单次优化工具"演进为**模块化功能 + 统一"AI 内容教练"叙事**。品牌叙事：*选题 → 拍摄 → 优化 → 发布，把你的视频变成学员*。按用户此刻意图组织入口（优化视频 / 选题灵感），解决"功能关联性不强"的观感——靠叙事与信息架构，不靠强制工作流。

**关键决策**:
- **行业可配置，驾考先行**: 架构参数化知识库/热词/prompt（`engine/industry_config.py` 待建），驾考仍是最先落地行业，保留护城河；不现在就泛化
- **P2 帧点评**: 自动挑 2-3 个"最有问题"帧 → VLM 诊断（画质 + 内容表达）→ 图上标注框 + 文字建议
- **P3 选题灵感**: 精选选题库（静态）+ AI 生成更多（结合行业知识库 + 城市 + 季节 + 热点半自动）
- **P4 部署**: 试用阶段 CF Tunnel 免费方案（本机跑 + 公网隧道），价值验证后云服务器（阿里/腾讯轻量）+ Caddy；两套运维手册

**设计文档**: `docs/superpowers/specs/2026-08-02-v4-content-coach-design.md`（完整含 P1-P4 设计）

### v4 P1 完成（2026-08-04）: 前端编辑风重设计

把 v3.1 浅蓝卡片风前端整体切换为**极简编辑风**（墨黑 `--ink` + 暖橙 `--accent` + 发丝边框 + 超大排版 + 胶囊按钮 + 滚动渐显），设计语言来自用户参考页 `example_html/index-min.html`（**本地参考，不入库**）。

- **页面结构（营销前置）**: Nav → 整屏 Hero（meta条：5块/3分钟/0上传/同城）→ 五块拼图 → 三步 → 对比（改之前/改之后）→ ★核心工具区（Tab1 优化视频 / Tab2 选题灵感占位 + 历史方案）→ CTA → Footer
- **工具直达**: 导航"开始使用"/Hero"立即体验"一键滚动到工具区，双 Tab 直接可用
- **文件**: `web/templates/optimize.html` 重写；`web/static/css/style.css` 重写 token+组件；`web/static/js/app.js` 保留核心逻辑 + `switchTab`（双 Tab）+ 编辑编号行结果渲染 + IntersectionObserver 滚动渐显
- **测试**: `tests/test_frontend.py` 升级 11 项（新 token + 营销前置结构 + 双 Tab 断言）；前端 11/11 + 顾问 10/10 + ASR 10/10；后端 `web/app.py` 零改动
- **实施计划**: `docs/superpowers/plans/2026-08-04-p1-frontend-editorial-redesign.md`
- **过程**: 子代理驱动 5 任务 + 每任务审查 + 最终整分支审查（opus）通过；修复波次（文档一致性 + switchTab 防御 + 触控目标）
- **Deferred**: Tab 键盘方向键导航（增强，后续可做）；`em.em` 类名（参考页同款）；`--ink-3` 对比度按用户裁定保持参考页原值

### v4 P1.1 核心修复与输入泛化（2026-08-04 晚）

**① 修复"上传新视频却生成旧内容"（缓存隔离）**
- **根因**: 每次 optimize 都共用 `work/` 目录 + Pipeline 固定文件名缓存（`audio.wav`/`asr_result.json`/`scenes.json`/`frame_descriptions.json`），且"缓存存在即跳过"从不校验是否属于当前视频 → 新视频从未被真正转写，喂给 LLM 的一直是上一个视频的转录。
- **修复**: `engine/advisor.py` 每次视频分析用独立工作目录 `work/run_{时间戳}_{uuid}/`，CLI 与 Web 同源修复。
- **验证**: 新回归测试 `test_build_plan_video_isolated_workdir`（先红后绿）+ 真实转写新视频确认产物为实际内容。

**② 输入泛化（任意内容都能出方案）**
- `engine/analyzer.py` 方案 prompt 泛化：非驾考内容（生活/搞笑/闲聊等）忽略驾考知识库、按实际主题输出同样 5 块方案；驾考/教学内容仍用领域知识做专业深度。系统 prompt 同步泛化。
- `engine/advisor.py` 过短/无声内容不再硬报错：无说话内容 → 友好提示换视频或贴文字；转录 <10 字 → 提示"内容太短"，避免拿 1-2 字残句喂 LLM 生成垃圾。
- 新增测试：`test_plan_prompt_supports_generic_content`、`test_build_plan_insufficient_transcript_clear_error`。

**测试**: 顾问 13/13 + 前端 11/11 + ASR 10/10。

### v4 P2 帧点评（完成，2026-08-04 晚）

自动挑"最有问题"的帧 → VLM 诊断（画质 + 内容表达）→ 图上标注框 + 文字建议，直观告诉教练"哪里有问题、怎么改"。设计详见 v4 spec 第四章。

- **新模块** `engine/frame_diagnose.py`: 逐帧 VLM"帧诊断"（问题列表 + 严重度 + 标注框 + 建议），按最严重问题 severity 取 top 3 帧；坐标归一化校验（越界/缺失 → 仅文字诊断）、severity 收敛 0-1、图片降采样 ≤720p 后 base64 内嵌（4K → ~72KB）
- **编排**: `advisor._analyze_video` 复用 pipeline 已采样关键帧（不新增采样成本）→ 方案 JSON 附加 `frames` 字段；`web/app.py` 零改动（plan 透传）
- **前端**: `app.js` 渲染 ⑥ 帧点评卡片（图片 + 橙色标注框 + 文字行 + 复制诊断）；历史 localStorage 只存文字不存 base64 防撑爆
- **保底关键帧**: `pipeline._detect_scenes` 无场景切换时（单镜头/手机随手拍）按时长等分合成 ≤4 段伪场景，保证 VLM 描述与帧点评都有帧可分析
- **降级**: VLM 诊断失败 / 无 key / 无帧 → 返回空，5 块方案照常出，绝不阻塞主流程
- **真实验证**: 对 `work/uploads/IMG_6898.mov`（4K 单镜头）端到端跑通，诊断出 4 条问题（前景遮挡 sev0.95 / 背景杂乱 sev0.85 / 暗部噪点 sev0.60 / 主体僵硬 sev0.50），box 缺失自动降级为纯文字
- **测试**: 顾问 18/18 + 前端 11/11 + ASR 10/10（新增：帧诊断挑选/规范化/降级、方案携带 frames、markdown 仅文字诊断、合成场景 4 项）
- **成本提醒**: 每次视频 optimize 新增 ≤4 次 VLM 帧诊断调用；后续可与 `_describe_frames` 的调用合并（一次返回描述+诊断）省约一半 VLM 成本

### v4 P3 选题灵感（完成，2026-08-04 晚）

给内容教练工作台补齐"不知道该拍什么"的入口：Tab2【选题灵感】= 精选选题库（秒开零成本）+ AI 生成更多（城市/季节/热点半自动）。设计见 v4 spec 第五章。

- **精选选题库** `knowledge/driving_exam_topics.json`: 16 条驾考选题，`{id,title,description,category,tags,difficulty}`，覆盖挂科点/考试季/新规/招生/技巧/学员故事（从 `driving_exam.json` 高频话题+学员搜索意图撰写）
- **轻量行业配置** `engine/industry_config.py`: `get_industry_config(industry)` 返回知识库/选题库路径+行业名+prompt 提示语，未知行业回退默认；仅实现 `driving_exam`，未迁移现有知识库（有第二行业再抽目录化）
- **AI 生成更多** `analyzer.generate_topics()`: 注入行业知识库+城市+季节/节点+热点 → LLM 生成 `[{title,description,why_now,shooting_idea}]`；失败自动重试一次；`_validate_topics` 补全字段/过滤非法项
- **API** `web/app.py`: `GET /api/topics`（静态选题库，`?industry=` 可选）+ `POST /api/topics/generate`（后台线程 + `/status` 轮询，与 optimize 同模式，count 收敛 1-10）。修复：同步路由需先 `sys.path.insert(0, ROOT)` 再 import engine（脚本运行 sys.path[0]=web/）
- **前端** Tab2 占位替换为真实 UI：精选库卡片（分类/难度/标签/复制）+ 生成表单（城市 + 季节下拉 + 热点输入）+ 结果卡片（编号/为什么现在发/拍摄思路/复制）；`app.js` 新增 loadTopics/renderTopicList/generateTopics/pollTopicsStatus/copyTopic 等
- **真实验证**: HTTP 冒烟——GET /api/topics 返回 16 条；真实 LLM 生成 5 条选题（城市=长沙/季节=暑期/热点=电子考官）约 30s 完成、格式正确
- **测试**: 新增 `tests/test_topics.py` 9 项（选题库 schema、行业配置与回退、prompt 注入、_validate_topics、generate_topics 重试、/api/topics、后台线程流转、409 并发拒绝）；前端新增 2 项 Tab2 断言。当前单测 顾问 18/18 + 前端 13/13 + 选题 9/9 + ASR 10/10

### v4 后续（P4）

- [x] **P2 帧点评** → 完成（2026-08-04 晚）
- [x] **P3 选题灵感** → 完成（2026-08-04 晚）
- [ ] **P4 部署 + 运维手册**：跨平台改造（ffmpeg 路径/pathlib/启动脚本）+ waitress + CF Tunnel / 云服务器 + 运维手册（P1-P3 完成后做）

---

## 三、v3 新增（内容优化工具）

**v3.1 前端重构（2026-08-02）**: 前端从暗色单页工具重构为**浅色商务风单页 MVP 产品站**（Hero 价值主张 → 三步怎么用 → 核心工具 → 历史方案 → 五块说明 → Footer），面向驾校老板/运营（非技术人群），简约大气、讲究留白。样式拆至 `web/static/css/style.css`（设计 token + 组件 + 响应式 + 无障碍），逻辑拆至 `web/static/js/app.js`（真实调 `/api/optimize` + `/api/optimize/status`）；新增本地历史方案（localStorage 上限 20，可回看/复制/删除）。`web/app.py` 零改动。设计文档/实施计划见 `docs/superpowers/specs/` 与 `docs/superpowers/plans/`。框架决策：暂不上 SPA（单页纯静态足够；产品放大/多用户时再上 Vue/React）。

**v3.2 ASR 抗噪升级（2026-08-02）**: ASR 引擎从 paraformer（seaco 增强版）换为 **SenseVoice-Small + fsmn-vad + 驾考热词**。新增 `engine/asr.py`（`load_hotwords` + `SenseVoiceASR` 进程级模型单例），`pipeline._run_asr()` 改调用之；删除 60s chunk 循环 + 字级时间戳解析，精简 `_postprocess_asr`；输出 schema 不变，下游零改动。无回退、无云端抽象。真实样本验证：车内噪音+考试播报音频转录成句可读、播报干净（如"考试结束，成绩合格，请把车开回起点"），CPU 推理 ~38× 实时（343s 音频 9s），完整 `--optimize` 出的 5 块方案质量显著提升（LLM 正确提炼出"雨刮器找点法"）。设计文档 `docs/superpowers/specs/2026-08-02-asr-sensevoice-upgrade-design.md`。

**核心链路**: 上传视频（或粘贴文字，可选填城市）→ ASR 转录 + 可选 VLM 看帧 → LLM 生成 5 块《内容优化方案》→ Web 页展示 + markdown 文件，每块可一键复制。

**新文件**:
- `engine/advisor.py` — 内容顾问（编排 + `write_plan_markdown`）
- `web/templates/optimize.html` — 新前端页面（上传/粘贴 → 生成 → 复制）
- `tests/test_advisor.py` — 10 个单元测试

**改动**: `engine/analyzer.py` 新增 `generate_optimization_plan()`；`engine/pipeline.py` 新增公开 `extract_transcript()/extract_visuals()`；`web/app.py` 新增 `/api/optimize` + `/api/optimize/status`；`run.py` 新增 `--optimize`。

**已删除**: `engine/style_manager.py`（旧风格学习，无引用）、`web/templates/index.html`（旧切片首页，已被 optimize.html 取代）。

**遗留（保留但不再进入新调用链）**: `engine/exporter.py`、`engine/scorer.py`、`templates/`、`assets/bgm/` 均为旧"多平台切片/导出"方向遗留，仅旧流程 `--export` 使用；新方向不涉及。

---

## 四、用户需求（原始 + 演进）

### 原始需求
1. 驾考教练拍摄的教学长视频（5-15分钟）
2. AI 自动理解教学内容，切出重点片段
3. 一键导出适配抖音(9:16)、B站(16:9)、小红书(1:1)三个平台的视频
4. 自动生成发布文案

### 演进中的需求
1. **视频效果**: 需要字幕动画、进度条、背景音乐（不是简单的静态叠加）
2. **内容理解**: 需要 AI 真正理解"这个知识点为什么重要"，而不只是关键词匹配
3. **风格学习**: 希望能上传参考视频，让 AI 学习其剪辑风格再应用到新视频
4. **Web 平台**: 最终形态应该是 Web 应用——用户上传视频→自动切片→预览确认→导出
5. **模板自定义**: 用户可以创建、修改、保存自己的导出模板

---

## 五、当前代码状态

### 项目结构
```
ai-teaching-video-editor/
├── engine/                        ← 核心引擎
│   ├── advisor.py                 ← 内容顾问（编排 + write_plan_markdown）
│   ├── asr.py                     ← SenseVoice ASR（抗噪转录 + 驾考热词 + 模型单例）
│   ├── pipeline.py                ← 7步管线（音频→ASR→场景→VLM→LLM→分段→评分）
│   ├── analyzer.py                ← LLM 内容分析器（方案 5 块 / 选题生成 / 文案 / 风格分析）
│   ├── frame_diagnose.py          ← 帧诊断（VLM 诊断 + 挑最严重 top3 + 标注框）v4 P2
│   ├── industry_config.py         ← 行业配置接口（轻量，驾考先行）v4 P3
│   ├── scorer.py                  ← 5维度规则评分（旧流程遗留，新方向不调用）
│   └── exporter.py                ← ffmpeg CLI 导出（旧流程遗留，新方向不调用）
├── templates/                     ← 平台模板
│   ├── douyin.json                ← 9:16竖屏 | 字幕0.038h | 位置78% | BGM音量45%
│   ├── bilibili.json              ← 16:9横屏 | 知识卡片 | 无BGM
│   ├── xiaohongshu.json           ← 1:1方形 | KeyPoints要点 | BGM音量40%
│   └── custom/                    ← 用户自定义模板目录
├── knowledge/
│   ├── driving_exam.json          ← 驾考知识库（12个话题+扣分点+关键词+文案模板）
│   └── driving_exam_topics.json   ← 驾考精选选题库（16条，Tab2 选题灵感）v4 P3
├── assets/
│   └── bgm/default_bgm.m4a        ← 默认BGM（C大调和弦进行，16s循环）
├── web/                           ← Web 产品站（Flask）
│   ├── app.py                     ← API服务（optimize/status/topics 选题/静态托管/旧导出接口）
│   ├── templates/optimize.html    ← 编辑风营销前置骨架（Nav/Hero/五块/三步/对比/双Tab工具区/CTA/Footer）
│   └── static/
│       ├── css/style.css          ← 设计系统（编辑风：墨黑+暖橙 token + 发丝边框 + 组件 + 响应式）
│       └── js/app.js              ← 交互逻辑（优化生成 / 选题灵感 / 轮询 / 渲染 / 复制 / 历史 / 双Tab）
├── run.py                         ← CLI 入口
├── RUN.bat / RUN_WEB.bat          ← Windows 一键启动
├── tests/test_export.py           ← 导出测试
├── tests/test_topics.py           ← 选题灵感测试（v4 P3，9 项）
└── PROGRESS.md                    ← 详细进度记录
```

### 管线流程
```
视频 → ffprobe探测 → ffmpeg音频提取(16kHz mono)
  → SenseVoice-Small + fsmn-vad(38句/5.7min, 带句子级时间戳, 驾考热词纠错)
  → PySceneDetect(19场景, ContentDetector threshold=30)
  → VLM qwen3.7-plus关键帧描述(≤6帧采样, topic/location/activity)
  → LLM qwen3.7-plus文本分析(知识点提取, 4个知识点/5.7min)
  → 规则合并(topic相同+短场景吸附+10s最小片段)
  → 5维度规则评分
  → ffmpeg导出(BGM混音 + ASS字幕 + eq画质增强)
```

### 关键技术参数

| 参数 | 值 |
|------|-----|
| ASR模型 | FunASR SenseVoice-Small + fsmn-vad（抗噪，CPU ~38× 实时，驾考热词） |
| VLM/LLM模型 | qwen3.7-plus (DashScope OpenAI兼容) |
| API端点 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| 编码器 | libx264 (NVENC在RTX 5060不可用，已自动降级) |
| 预设 | `preset=medium, crf=21` |
| Python | 3.12.10 |
| ffmpeg | 8.1.2 @ `D:/Tools/ffmpeg/ffmpeg-8.1.2-full_build/` |

---

## 六、已完成的重大修复（2026-07-29 ~ 08-01）

### Bug修复
1. **ASS字幕三平台混淆** — `subtitles.ass` 改为 `subtitles_{platform}.ass`，每平台独立PlayRes
2. **字幕溢出** — 最终采用 `\clip(左,上,右,下)` 硬裁剪 + `\3c`半透明黑底 + `\bord12`描边
3. **字幕重叠** — 标题卡结束后字幕才开始 + 单句最长5秒
4. **小红书KeyPoints/Subtitle冲突** — KeyPoints缩小到顶部金色3条，Subtitle独立底部
5. **BGM听不到** — 从纯sine波改为谐波丰富和弦进行，音量从0.15提升至0.45
6. **Unicode编码** — 添加 `sys.stdout.reconfigure(encoding='utf-8')` 解决Windows GBK错误
7. **同名片段覆盖** — 输出目录改为 `{编号}_{话题}` (如 `00_倒车入库`)
8. **ASR后处理过激合并** — 修复 `_postprocess_asr()` 合并逻辑
9. **NVENC假阳性** — 添加实际编码测试，RTX 5060正确降级libx264

### 新增功能
1. LLM内容分析器 (`engine/analyzer.py`) — 知识点提取、内容评分、文案生成、风格学习
2. 风格管理器 (`engine/style_manager.py`) — 自定义模板CRUD
3. Web预览界面 (`web/`) — Flask本地服务，片段预览+平台选择+一键导出+文案编辑
4. BGM混音 — ffmpeg `filter_complex` 实现 `amix` 混音
5. 画质增强 — `eq=contrast=1.08:brightness=0.02:saturation=1.05`
6. 字幕动画 — 标题滑入 `\t(0,500,\pos)` + 关键词弹跳 `\fscx150\t(0,250,\fscx100)`
7. VLM调用优化 — 19帧→≤6帧采样，减少API成本

### 已修复但效果仍不理想的
- **ASR质量（v3.2 已大幅改善）**: 换 SenseVoice-Small + fsmn-vad 后，车内噪音+考试播报场景转录成句可读、播报干净（旧 paraformer："休息休息试准准请问试没问题题是考试" → 新："考试结束，成绩合格，请把车开回起点"）。**残余**：教练快速/密集说话仍会碎、个别同音字错误
- **字幕效果**: 虽有 `\clip` 防止溢出，但整体视觉效果仍远不如剪映/CapCut
- **BGM**: ffmpeg生成的sine波和弦，无法与真实音乐库相比

---

## 七、产品方向（已定：内容优化工具）

**方向已定（2026-08-01）**: 放弃"切片/导出工具"，转向"内容优化工具"。

**决策依据**: 与真实教练/驾校老板对话——他们不缺内容（自己拍、会发抖音），真正痛的是**视频没人看 + 找不到学员 + 引导转化差**。根因是供给需求错位（教练拍教学自嗨，学员搜痛点/本地信息）。因此产品从"帮教练产出内容"转为"帮已有内容获得更多曝光和转化"（同城获客）。用户是驾校老板/运营，不是老教练；界面原则"选视频→点生成→复制粘贴"。

以下是早先调研的三个候选方向的原始记录：

### 方向 A: 教学视频知识切片提取器（做减法）
- **做什么**: 只做AI内容理解——提取知识点+时间戳+推荐文案
- **不做什么**: 视频渲染、字幕、特效、BGM（交给剪映/必剪）
- **差异化**: 深度领域知识（驾考扣分点/考试流程），通用工具不懂这些
- **竞品**: 无直接竞品（通用工具如Opus Clip面向泛娱乐）

### 方向 B: 多平台智能格式适配器（做减法）
- **做什么**: 输入已剪好的视频→智能裁切+平台字幕格式转换+封面+文案
- **不做什么**: 不替代剪映的剪辑功能，只做"适配+分发"这最后一公里
- **差异化**: 三平台一键适配（剪映有导出但不会自动生成三套文案和封面）
- **竞品**: 剪映导出功能、social-auto-upload

### 方向 C: 驾考内容AI工厂（做加法/垂直深耕）
- **做什么**: 专为驾校教练设计的全流程工具（小程序或极简Web）
- **差异化**: 
  - 仅限驾考领域（全国几十万教练是潜在用户）
  - 内置驾考知识库（扣分标准+考试流程+常见错误）
  - 教练人设模板（严厉型/耐心型/幽默型）
  - 一键导出+发布
- **商业模式**: 教练月付29-49元/驾校年付
- **竞品**: 无直接竞品（通用工具不会为驾考教练做优化）

### 市场参考
- [Opus Clip](https://www.opus.pro/) — AI高光检测+传播力评分，$15/月
- [CapCut/剪映](https://www.capcut.com/) — 免费全功能视频编辑器
- [灵剪 Lingji Cut](https://github.com/yoqu/lingji-cut) — 开源全流程AI视频工具
- [厉影AI](https://github.com/liying-main/liying_ai) — 全链路自动化视频创作

---

## 八、遗留问题和待办

### v4（内容教练工作台，当前方向）
- [x] P1 前端编辑风重设计 → 完成（2026-08-04，营销前置 + 双 Tab 工具区）
- [x] P1.1 核心修复（优化缓存隔离 + 输入泛化）→ 完成（2026-08-04 晚）
- [x] P2 帧点评（自动挑问题帧 + VLM 诊断 + 标注框）→ 完成（2026-08-04 晚）
- [x] P3 选题灵感（精选库 + AI 生成更多 + 轻量行业配置）→ 完成（2026-08-04 晚）
- [ ] P4 部署 + 运维手册（CF Tunnel 试用 / 云服务器正式，跨平台改造 + waitress）

### 已知 UI 布局/设计问题（审查 2026-08-04；修复 2026-08-04 晚）
- [x] **结果块布局失衡（主要）** → 已修：`#result .block` 改 2 列（80px/1fr），复制按钮置于正文下方（`grid-column:2` 左对齐），不再有 1.1fr 大空白
- [x] **移动端导航不可达** → 已修：`@media(max-width:760px)` 不再隐藏 `.nav-links`，改为紧凑显示（gap:16px / 13px）+ 压缩 logo/CTA；未上汉堡菜单（可后续做）
- [x] **手机/局域网访问复制失效** → 已修：`app.js` 新增 `copyText()`/`legacyCopy()`，非安全上下文自动降级 `execCommand('copy')`
- [x] 结果字段标签对齐 → 已微调：`.field .k` min-width 72→56px
- [ ] 平台下拉仅"抖音"一项（占位，等 P3 行业配置）

### 局域网访问（2026-08-04 用户改 0.0.0.0；修复 2026-08-04 晚）
- [x] **硬编码 IP 有误** → 已修：`run.py` 新增 `_get_lan_ip()` 动态探测本机 IP（当前 `192.168.0.102`），`webbrowser.open` 与启动打印用探测值；失败回退 127.0.0.1
- [x] `web/app.py` `--host` help 文案 → 已改"默认: 0.0.0.0，局域网可访问"
- [ ] Windows 防火墙需手动放行 5000 端口入站，否则手机连不上（run.py 启动打印已提示）
- [ ] `0.0.0.0` 暴露无鉴权 API，局域网内任意设备可 POST `/api/optimize` 消耗 API 额度（试用阶段可接受，需知晓）

### 立即
- [x] **决定产品方向**（A/B/C 三选一）→ 已定：内容优化工具（A 的内容诊断 + 获客转化，经真实用户验证）
- [x] 根据方向裁剪/重构代码 → v3 完成并验证

### 短期（v3.1 之后）
- [x] Web 界面浅色商务风重构 → v3.1 完成（静态 HTML/CSS/JS 零构建；框架决策见"中期"）
- [x] ASR 质量：SenseVoice-Small + fsmn-vad + 驾考热词 替换完成 → v3.2（残余：快速说话仍会碎）
- [ ] 接入真实教练试用 1-2 家 → 试用材料已备：`docs/trial/2026-08-02-教练试用方案.md`（流程/话术/数据表/成功标准）
- [ ] 反馈循环：记录每条视频的诊断→建议→实际播放/留资数据（试用数据表见试用方案第六节，可先手工记录）

### 短期
- [x] 解决ASR质量问题 → v3.2 已换 SenseVoice（如仍不够再评估云端 ASR）
- [ ] 替换BGM为真实音乐（下载免版税BGM资源）
- [ ] Web界面升级为 Vue/React SPA（当前纯静态足够；等产品放大/多用户/复杂状态时再上框架）

### 中期
- [ ] LLM评分替代规则评分（analyzer.py已有 `score_segment()`，但pipeline未调用）
- [ ] 风格学习功能完善（style_manager.py已有框架）
- [ ] 多用户支持（如选方向C）

### 长期
- [ ] 用户系统 + 任务队列 + 云存储
- [ ] 移动端小程序（如选方向C）
- [ ] 扩展到驾考之外的垂直领域

---

## 九、环境信息

| 项目 | 详情 |
|------|------|
| OS | Windows 11 Home China 10.0.26200 |
| GPU | NVIDIA RTX 5060 Laptop (8GB) — NVENC不可用 |
| Python | 3.12.10 (`py -3.12`) |
| ffmpeg | 8.1.2 @ `D:/Tools/ffmpeg/ffmpeg-8.1.2-full_build/` |
| API Key | DashScope 已配置在 `.env`，MODEL=qwen3.7-plus |
| Git | `git@github.com:Xin-der/ai-teaching-video-editor.git` |

### 运行方式
```bash
# ★ 内容优化（新方向，核心用法）
py -3.12 run.py input/视频.mp4 --optimize --city 长沙   # 视频 → 方案
py -3.12 run.py --optimize --text "粘贴脚本" --city 长沙  # 文字 → 方案

# Web 界面（推荐给教练/老板用）
py -3.12 run.py --web   # 打开 http://127.0.0.1:5000

# 旧流程（切片/导出，已弃用，仅兼容）
py -3.12 run.py input/PNIK4383.MOV --export

# 单元测试
py -3.12 tests/test_asr.py       # 10/10（SenseVoice 模块，mock 不下载模型）
py -3.12 tests/test_advisor.py   # 10/10
py -3.12 tests/test_frontend.py  # 11/11
```

---

## 十、给新会话的启动语

```
请先阅读 HANDOFF.md 和 PROGRESS.md 了解项目状态。
方向已定：驾校内容优化工具 → 内容教练工作台（v4，行业可配置·驾考先行；模块化 + 内容教练叙事）。已完成：v3 内容优化 + v3.1 前端 + v3.2 ASR 抗噪 + v4 P1 前端编辑风重设计 + v4 P1.1 核心修复（缓存隔离 + 输入泛化）+ v4 P2 帧点评 + v4 P3 选题灵感（精选库 + AI 生成更多 + 轻量行业配置）（详见第二/三/五章）。
下一步：P4 部署 + 运维手册（跨平台改造 + waitress + CF Tunnel / 云服务器 + 两套运维手册）。真实教练试用（docs/trial/）与反馈循环可并行推进。
协作注意：尽量轻量直接，别套重流程；superpowers 技能默认不用、用户明确要求才用；拿不准的开头一次性确认。
```
