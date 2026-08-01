# 项目进度

> 最后更新: 2026-08-01 | 状态: v3 内容优化工具开发完成并验证通过

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

### v3.1 前端重构（浅色商务风 MVP 产品站）
- 2026-08-01 前端从暗色单页工具重构为浅色商务风单页产品站（Hero/三步/工具/五块说明/Footer）
- 样式与逻辑拆分至 `web/static/css/style.css` + `web/static/js/app.js`，`web/app.py` 零改动
- 新增本地历史方案（localStorage，最多 20 条）
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

**下一步**: v3 之后——真实教练试用 1-2 家验证闭环、修 ASR 抗噪、前端升级 SPA。

---

## 项目文件清单

```
保留（核心代码）:
├── engine/           ← 核心引擎（pipeline/scorer/exporter/analyzer/style_manager）
├── templates/        ← 平台模板 + custom/自定义目录
├── knowledge/        ← 驾考知识库
├── web/              ← Flask Web预览界面
├── run.py            ← CLI入口
├── tests/            ← 测试文件
├── assets/bgm/       ← BGM资源
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
