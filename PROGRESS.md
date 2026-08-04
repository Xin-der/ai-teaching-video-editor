# 项目进度

> 最后更新: 2026-08-04 | 状态: v4 P3 选题灵感完成（P1 前端重设计 + P1.1 核心修复 + P2 帧点评 已完成）

---

## 版本演进

### v4 P1（完成）: 前端编辑风重设计（2026-08-04）
目标：把 v3.1 浅蓝卡片风前端重构成极简编辑风（墨黑+暖橙+发丝边框）营销前置单页，核心工具区双 Tab 可直接使用。
**当前状态**: 完成（2026-08-04），前端测试 11/11 + 顾问 10/10 + ASR 10/10 通过；HTTP 冒烟验证通过。
- 页面结构：Nav → 整屏 Hero（meta条）→ 五块拼图 → 三步 → 对比 → ★核心工具（Tab1 优化视频 / Tab2 选题灵感占位 + 历史方案）→ CTA → Footer；导航/CTA 一键滚到工具区
- 设计语言采用用户参考页 `example_html/index-min.html`：`--ink` 墨黑 + `--accent` 暖橙 + 发丝边框 + 超大排版（Hero 76px）+ 胶囊按钮 + sticky 毛玻璃导航 + 滚动渐显
- `web/templates/optimize.html` 重写为营销前置骨架；`web/static/css/style.css` 重写 token 与组件；`web/static/js/app.js` 保留核心逻辑 + 新增 `switchTab`（双 Tab）+ 编辑编号行结果渲染 + IntersectionObserver 滚动渐显
- `tests/test_frontend.py` 升级为 11 项（新 token + 营销前置结构 + 双 Tab 断言）；后端 `web/app.py` 零改动
- 设计文档 `docs/superpowers/specs/2026-08-02-v4-content-coach-design.md`、实施计划 `docs/superpowers/plans/2026-08-04-p1-frontend-editorial-redesign.md`
- 过程：子代理驱动 5 任务 + 每任务审查 + 最终整分支审查（opus）通过；修复波次（文档一致性 + switchTab 防御 + 触控目标）
- Deferred：Tab 键盘方向键导航（增强）；`em.em` 类名（参考页同款）；`--ink-3` 对比度按用户裁定保持参考页原值

**下一步**: P4 部署 + 运维手册（跨平台改造 + waitress + CF Tunnel / 云服务器 + 两套运维手册）。详见 HANDOFF.md 第二章。（P2 帧点评、P3 选题灵感已于 2026-08-04 晚完成）

### v4 P1.2（完成）: UI 问题 + 局域网 IP 修复（2026-08-04 晚）
目标：修前端审查发现的布局/设计问题；修 `run.py` 硬编码 IP 导致浏览器连不上的 bug。
**当前状态**: 完成，前端 11/11 + 顾问 13/13 + ASR 10/10 通过。
- **结果块布局**: `#result .block` 改 2 列，复制按钮不再占 1.1fr 大空白列
- **移动端导航**: `@media(max-width:760px)` 改为紧凑显示 `.nav-links`（原先直接隐藏）
- **复制降级**: `app.js` 新增 `copyText()/legacyCopy()`，非安全上下文（局域网/手机 http）自动 `execCommand` 降级
- **局域网 IP**: `run.py` 新增 `_get_lan_ip()` 动态探测（原先写死 `192.168.0.101`，实际 `192.168.0.102`）；`web/app.py` `--host` help 修正
- 未处理：平台下拉仅抖音（P3 依赖）、防火墙放行（需手动）、0.0.0.0 无鉴权（试用可接受，已记录）

### v4 P1.1（当前）: 核心修复与输入泛化（2026-08-04 晚）
目标：修"上传新视频却生成旧内容"的缓存 bug；让任意内容（非驾考）也能按实际主题生成方案。
**当前状态**: 完成，顾问 13/13 + 前端 11/11 + ASR 10/10 通过。
- **缓存隔离**: `engine/advisor.py` 每次视频分析用独立工作目录 `work/run_{时间戳}_{uuid}/`，根除 Pipeline 固定文件名缓存（`audio.wav`/`asr_result.json` 等）被上一个视频复用的问题
- **输入泛化**: `engine/analyzer.py` 方案 prompt 泛化（非驾考内容忽略驾考知识、按实际主题输出同样 5 块方案）；`engine/advisor.py` 过短/无声内容改为友好提示（转录 <10 字 → "内容太短"），不喂垃圾给 LLM
- **新增测试**: `test_build_plan_video_isolated_workdir`、`test_plan_prompt_supports_generic_content`、`test_build_plan_insufficient_transcript_clear_error`
- **遗留记录**: 已知 UI 布局/设计问题 + 局域网访问注意（硬编码 IP 有误等）已写入 HANDOFF.md 第八章

### v4 P2（完成）: 帧点评（2026-08-04 晚）
目标：自动挑"最有问题"的帧 → VLM 诊断（画质 + 内容表达）→ 标注框 + 文字建议。
**当前状态**: 完成，顾问 18/18 + 前端 11/11 + ASR 10/10 通过；真实 4K 单镜头视频端到端验证。
- 新增 `engine/frame_diagnose.py`：逐帧 VLM 诊断 → 按 severity 取 top 3 帧；坐标归一化（越界→仅文字）、severity 收敛、图片降采样 ≤720p 后 base64 内嵌
- `advisor._analyze_video` 复用已采样关键帧 → 方案附加 `frames` 字段；`web/app.py` 零改动
- 前端 ⑥ 帧点评卡片（图 + 橙色标注框 + 文字 + 复制）；历史只存文字不存 base64
- `pipeline._detect_scenes` 无场景切换时合成 ≤4 段伪场景，保证单镜头视频也有帧可分析
- 降级：诊断失败/无 key/无帧 → 空，5 块方案照常出
- 成本：每次视频 optimize 新增 ≤4 次 VLM 诊断调用（后续可合并省一半）

### v4 P3（完成）: 选题灵感（2026-08-04 晚）
目标：给"不知道该拍什么"的教练一个入口——精选选题库（秒开零成本）+ AI 生成更多（结合城市/季节/热点）。
**当前状态**: 完成，选题 9/9 + 顾问 18/18 + 前端 13/13 + ASR 10/10 通过；真实 HTTP 冒烟 + 真实 LLM 生成验证。
- `knowledge/driving_exam_topics.json`：16 条精选选题（挂科点/考试季/新规/招生/技巧/学员故事），`{id,title,description,category,tags,difficulty}`
- `engine/industry_config.py`：轻量行业配置 `get_industry_config(industry)`（知识库/选题库路径+行业名+prompt 提示语），未知回退默认，仅 driving_exam
- `analyzer.generate_topics()`：注入行业知识库+城市+季节/节点+热点 → `[{title,description,why_now,shooting_idea}]`，失败自动重试，`_validate_topics` 补字段/过滤
- `web/app.py`：`GET /api/topics`（静态选题库）+ `POST /api/topics/generate`（后台线程+`/status` 轮询，count 1-10）；修复同步路由需先 `sys.path.insert(0, ROOT)`
- 前端 Tab2：精选库卡片（分类/难度/标签/复制）+ 生成表单（城市/季节下拉/热点）+ 结果卡片（编号/现在发/拍摄/复制）
- 测试：新增 `tests/test_topics.py` 9 项 + 前端 2 项 Tab2 断言
- 真实验证：GET /api/topics 返回 16 条；真实 LLM 生成 5 条（长沙/暑期/电子考官）约 30s、格式正确

### v3: 驾校内容优化工具
目标：教练的素材视频/文字 → AI 生成 5 块《内容优化方案》（诊断/脚本改写/包装/转化话术/下期选题）→ 帮已有内容获客转化（同城）。
**当前状态**: 开发完成，单元测试 10/10，真实 API（文字+视频）验证通过。

**已完成** (2026-08-01):
- 方向决策：与真实教练/老板对话确认——真痛点是"视频没人看+找不到学员"，非"缺内容"。产品定位从切片转向内容优化（详见 HANDOFF.md 第五/二章）
- `engine/advisor.py`：内容顾问编排（视频/文字 → ASR/VLM → LLM → 5 块方案 + markdown）
- `engine/analyzer.py`：新增 `generate_optimization_plan()`
- `engine/pipeline.py`：新增公开 `extract_transcript()/extract_visuals()`
- `web/`：新增 `/api/optimize` 接口 + `optimize.html` 前端（上传/粘贴 → 生成 → 一键复制）
- `run.py`：新增 `--optimize/--city/--text`
- `tests/test_advisor.py`：10 个单元测试（TDD）
- 集成验收：CLI 文字/视频模式 + Web 全流程真实调用均通过

### v3.2: ASR 抗噪升级（SenseVoice）
目标：把 ASR 从 paraformer（seaco 增强版）换成 SenseVoice-Small + fsmn-vad + 驾考热词，解决车内噪音+考试播报导致的碎片化转录。
**当前状态**: 完成（2026-08-02），单测 ASR 10/10 + 顾问 10/10 + 前端 8/8，真实转录 + 完整 optimize 流程端到端验证通过。
- 新增 `engine/asr.py`：`load_hotwords()`（从知识库生成驾考热词表）+ `SenseVoiceASR`（进程级模型单例，`transcribe()` 返回秒级 `[{start,end,text}]`）
- `pipeline._run_asr()` 改调用 `SenseVoiceASR`；删除 60s chunk 循环 + `_parse_asr_timestamps` + `numpy` 死导入；精简 `_postprocess_asr`
- 输出 schema 不变，analyzer/advisor/Web 下游零改动；无 paraformer 回退、无云端抽象
- 真实样本验证：343s 车内噪音音频 CPU 推理 9s（~38× 实时）；转录从"碎片化不可读"提升到"成句可读、考试播报干净"（"考试结束，成绩合格，请把车开回起点"）；完整 optimize 出的 5 块方案质量显著提升（LLM 正确提炼出"雨刮器找点法"）
- 新增依赖：`pypinyin`（funasr postprocess_hotwords 需要）
- 设计文档 `docs/superpowers/specs/2026-08-02-asr-sensevoice-upgrade-design.md`
- 残余：教练快速/密集说话仍会碎、个别同音字错误（可接受，后续可评估云端 ASR 升级）

### v3.1: 前端浅色商务风重构（MVP 产品站）
目标：把暗色单页工具重构成驾校老板信任的浅色商务风单页产品站，功能与后端不变。
**当前状态**: 完成（2026-08-02），前端回归 8/8，后端 10/10，真实 HTTP + LLM 验证通过。
- 页面结构：Hero（价值主张）/ 三步怎么用 / 核心工具 / 历史方案 / 五块说明 / Footer
- 样式拆至 `web/static/css/style.css`（设计 token + 组件 + 响应式 + 无障碍），逻辑拆至 `web/static/js/app.js`（真实调 `/api/optimize` + `/api/optimize/status`），`web/app.py` 零改动
- 新增本地历史方案（localStorage，上限 20 条，可回看/复制/删除）
- 设计文档 `docs/superpowers/specs/2026-08-01-frontend-redesign-design.md`、实施计划 `docs/superpowers/plans/2026-08-01-frontend-redesign.md`
- 过程：subagent 驱动 5 任务实施 + 每任务审查 + 整分支审查 + 健壮性修复（clipboard/历史校验/轮询恢复/触控目标 44px）
- `tests/test_frontend.py` 8 项回归通过；`tests/test_advisor.py` 仍 10/10

### v2（已废弃）: 多平台智能切片工具
目标：AI 学一次剪辑风格，自动渲染完整 mp4。
**废弃原因**: 模拟剪辑审美技术难度过高、流程硬编码严重、10小时渲染仍不正确。

### v2（当前）: 多平台智能切片工具
目标：长教学视频 → AI 理解 → 智能切片 → 抖音/B站/小红书 + 文案。
**当前状态**: 技术验证完成，效果不达预期，正在重新定位。

**已完成** (2026-07-28 ~ 08-01):

| 日期 | 工作内容 |
|------|---------|
| 07-28 | 方向调整：全自动出片→多平台切片，核心引擎搭建完成 |
| 07-29 | 导出链路验证完成（ffmpeg CLI + ASS字幕替代MoviePy） |
| 07-29 | ASR阻塞解除（Windows AppLocker→torchaudio可用） |
| 07-29 | 管线全流程跑通（9片段→18视频） |
| 07-29 | 字幕溢出修复（多轮迭代，最终方案: `\clip`硬裁剪+`\3c`背景） |
| 07-29 | 文件清理（释放约457MB） |
| 07-29 | ASR参数优化（RMS 0.01→0.003, chunk重叠5s, 后处理修复） |
| 07-29 | LLM内容分析器（`analyzer.py`, 知识点提取+文案生成+风格学习） |
| 07-29 | BGM混音实现（ffmpeg filter_complex amix） |
| 07-29 | Web预览界面（Flask + 暗色主题前端） |
| 07-29 | 风格管理器（`style_manager.py`, 自定义模板CRUD） |
| 07-29 | VLM调用优化（19帧→≤6帧采样） |
| 08-01 | 市场调研 + 产品方向讨论（方向A/B/C） |

**已知限制**:
- ASR质量受源视频音频质量限制（车内噪音+考试播报叠加）
- NVENC在RTX 5060 (Blackwell) 不可用，使用libx264软件编码
- BGM为ffmpeg合成，无法替代真实音乐库
- 整体视频效果远不如商业产品（剪映/CapCut）

**下一步**: 按 `docs/trial/2026-08-02-教练试用方案.md` 接 1-2 家真实教练试用，验证"视频→方案→发布→留资"闭环；落地反馈循环（记录诊断→建议→实际播放/留资，试用数据表已设计，可先手工记录）。前端暂不上 SPA 框架（单页纯静态足够；等产品放大/多用户再上 Vue/React）。

---

## 项目文件清单

```
保留（核心代码）:
├── engine/           ← 核心引擎（pipeline/scorer/exporter/analyzer/style_manager）
├── templates/        ← 平台模板 + custom/自定义目录
├── knowledge/        ← 驾考知识库
├── web/              ← Flask 产品站（templates/optimize.html + static/css + static/js）
├── run.py            ← CLI入口
├── tests/            ← 测试文件
├── assets/bgm/       ← BGM资源
├── docs/superpowers/ ← 设计文档(specs/)与实施计划(plans/)
├── docs/trial/       ← 教练试用材料（流程/话术/数据表，2026-08-02 已备）
├── HANDOFF.md        ← 交接文档
├── PROGRESS.md       ← 本文件
├── README.md         ← 项目说明
└── .env              ← API Key配置

可清理（非必要）:
├── scripts/          ← 旧独立脚本（已被engine/替代，可删除）
└── docs/             ← 旧调研文档（可归档）

.gitignore 已忽略:
├── work/             ← 中间产物（音频/ASR/VLM缓存/分段结果）
├── output/           ← 导出视频
├── input/            ← 源视频
└── .env              ← API密钥
```
