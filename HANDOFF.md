# 项目交接文档

> 最后更新: 2026-08-02 | 状态: v3.1 前端浅色商务风重构完成（v3 内容优化工具 + v3.1 前端）

---

## 一、项目概述

**产品名**: 驾校内容优化工具

**核心目标**: 教练的素材视频/文字 → AI 生成 5 块《内容优化方案》（诊断 / 脚本改写 / 包装 / 转化话术 / 下期选题）→ 照着改、照着发，帮驾校同城获客

**当前阶段**: v3.1（2026-08-02）前端浅色商务风重构完成。单元测试 10/10 + 前端回归 8/8，真实 API（文字/视频）+ 真实 HTTP/LLM 前端调用验证通过。

---

## 二、v3 新增（内容优化工具）

**v3.1 前端重构（2026-08-02）**: 前端从暗色单页工具重构为**浅色商务风单页 MVP 产品站**（Hero 价值主张 → 三步怎么用 → 核心工具 → 历史方案 → 五块说明 → Footer），面向驾校老板/运营（非技术人群），简约大气、讲究留白。样式拆至 `web/static/css/style.css`（设计 token + 组件 + 响应式 + 无障碍），逻辑拆至 `web/static/js/app.js`（真实调 `/api/optimize` + `/api/optimize/status`）；新增本地历史方案（localStorage 上限 20，可回看/复制/删除）。`web/app.py` 零改动。设计文档/实施计划见 `docs/superpowers/specs/` 与 `docs/superpowers/plans/`。框架决策：暂不上 SPA（单页纯静态足够；产品放大/多用户时再上 Vue/React）。

**核心链路**: 上传视频（或粘贴文字，可选填城市）→ ASR 转录 + 可选 VLM 看帧 → LLM 生成 5 块《内容优化方案》→ Web 页展示 + markdown 文件，每块可一键复制。

**新文件**:
- `engine/advisor.py` — 内容顾问（编排 + `write_plan_markdown`）
- `web/templates/optimize.html` — 新前端页面（上传/粘贴 → 生成 → 复制）
- `tests/test_advisor.py` — 10 个单元测试

**改动**: `engine/analyzer.py` 新增 `generate_optimization_plan()`；`engine/pipeline.py` 新增公开 `extract_transcript()/extract_visuals()`；`web/app.py` 新增 `/api/optimize` + `/api/optimize/status`；`run.py` 新增 `--optimize`。

**已删除**: `engine/style_manager.py`（旧风格学习，无引用）、`web/templates/index.html`（旧切片首页，已被 optimize.html 取代）。

**遗留（保留但不再进入新调用链）**: `engine/exporter.py`、`engine/scorer.py`、`templates/`、`assets/bgm/` 均为旧"多平台切片/导出"方向遗留，仅旧流程 `--export` 使用；新方向不涉及。

---

## 三、用户需求（原始 + 演进）

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

## 四、当前代码状态

### 项目结构
```
ai-teaching-video-editor/
├── engine/                        ← 核心引擎
│   ├── pipeline.py                ← 7步管线（音频→ASR→场景→VLM→LLM→分段→评分）
│   ├── scorer.py                  ← 5维度规则评分（30%关键词+25%知识库+20%时长+15%画面+10%重复）
│   ├── exporter.py                ← ffmpeg CLI 导出（ASS字幕 + BGM混音 + 画质增强）
│   ├── analyzer.py                ← LLM 内容分析器（qwen3.7-plus，知识点提取/文案生成/风格分析）
│   └── style_manager.py           ← 风格管理器（自定义模板 CRUD + 风格学习）
├── templates/                     ← 平台模板
│   ├── douyin.json                ← 9:16竖屏 | 字幕0.038h | 位置78% | BGM音量45%
│   ├── bilibili.json              ← 16:9横屏 | 知识卡片 | 无BGM
│   ├── xiaohongshu.json           ← 1:1方形 | KeyPoints要点 | BGM音量40%
│   └── custom/                    ← 用户自定义模板目录
├── knowledge/
│   └── driving_exam.json          ← 驾考知识库（12个话题+扣分点+关键词+文案模板）
├── assets/
│   └── bgm/default_bgm.m4a        ← 默认BGM（C大调和弦进行，16s循环）
├── web/                           ← Web 产品站（Flask）
│   ├── app.py                     ← API服务（optimize/status/静态托管/旧导出接口）
│   ├── templates/optimize.html    ← 页面骨架（Hero/三步/工具/历史/五块说明/Footer）
│   └── static/
│       ├── css/style.css          ← 设计系统（浅色商务风 token + 组件 + 响应式）
│       └── js/app.js              ← 交互逻辑（生成/轮询/渲染/复制/历史）
├── run.py                         ← CLI 入口
├── RUN.bat / RUN_WEB.bat          ← Windows 一键启动
├── tests/test_export.py           ← 导出测试
└── PROGRESS.md                    ← 详细进度记录
```

### 管线流程
```
视频 → ffprobe探测 → ffmpeg音频提取(16kHz mono)
  → FunASR Paraformer(32句/5.7min, RMS 0.003, chunk 60s+5s重叠)
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
| ASR模型 | FunASR Paraformer v2.0.4 |
| VLM/LLM模型 | qwen3.7-plus (DashScope OpenAI兼容) |
| API端点 | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| 编码器 | libx264 (NVENC在RTX 5060不可用，已自动降级) |
| 预设 | `preset=medium, crf=21` |
| Python | 3.12.10 |
| ffmpeg | 8.1.2 @ `D:/Tools/ffmpeg/ffmpeg-8.1.2-full_build/` |

---

## 五、已完成的重大修复（2026-07-29 ~ 08-01）

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
- **ASR质量**: 车内噪音+考试播报叠加，FunASR识别碎片化严重（"休息休息试准准请问试没问题题是考试"）
- **字幕效果**: 虽有 `\clip` 防止溢出，但整体视觉效果仍远不如剪映/CapCut
- **BGM**: ffmpeg生成的sine波和弦，无法与真实音乐库相比

---

## 六、产品方向（已定：内容优化工具）

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

## 七、遗留问题和待办

### 立即
- [x] **决定产品方向**（A/B/C 三选一）→ 已定：内容优化工具（A 的内容诊断 + 获客转化，经真实用户验证）
- [x] 根据方向裁剪/重构代码 → v3 完成并验证

### 短期（v3.1 之后）
- [x] Web 界面浅色商务风重构 → v3.1 完成（静态 HTML/CSS/JS 零构建；框架决策见"中期"）
- [ ] ASR 质量：车内噪音识别仍待优化（换 SenseVoice 或云端 ASR）
- [ ] 接入真实教练试用 1-2 家，验证"视频→方案→发布→留资"闭环
- [ ] 反馈循环：记录每条视频的诊断→建议→实际播放/留资数据

### 短期
- [ ] 解决ASR质量问题（尝试SenseVoice/faster-whisper 或云端ASR API）
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

## 八、环境信息

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
py -3.12 tests/test_advisor.py   # 10/10
py -3.12 tests/test_frontend.py  # 8/8
```

---

## 九、给新会话的启动语

```
请先阅读 HANDOFF.md 和 PROGRESS.md 了解项目状态。
方向已定：驾校内容优化工具（v3 内容优化 + v3.1 前端浅色商务风重构已完成，详见第二章/第四章）。
下一步：真实教练试用 1-2 家验证"视频→方案→发布→留资"闭环、修 ASR 抗噪（见第七章短期待办）。
```
