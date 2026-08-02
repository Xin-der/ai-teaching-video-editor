# 项目进度

> 最后更新: 2026-08-02 | 状态: v3.1 前端浅色商务风重构完成

---

## 版本演进

### v3（当前）: 驾校内容优化工具
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

### v3.1（当前）: 前端浅色商务风重构（MVP 产品站）
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

**下一步**: v3.1 之后——真实教练试用 1-2 家验证"视频→方案→发布→留资"闭环、修 ASR 抗噪。前端暂不上 SPA 框架（单页纯静态足够；等产品放大/多用户再上 Vue/React）。

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
