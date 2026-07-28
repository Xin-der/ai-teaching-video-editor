# 项目进度

> 最后更新: 2026-07-28 | 方向: 多平台智能切片工具

---

## 方向变更记录

### v1（已废弃）: AI 全自动出片

目标：AI 学一次剪辑风格，以后自动渲染完整 mp4。

**为什么废弃**：
- 试图让 AI 模拟剪辑师审美（路线图叠加、红点跟随、关键帧动画），技术难度过高
- 全流程硬编码参考视频路径，第二段出片完全不读新视频
- 10 小时渲染跑不出正确结果，体验不可接受
- 用户实际需求是多平台发布，不是全自动出片

### v2（当前）: 多平台智能切片工具

目标：长教学视频 → AI 理解内容 → 智能切片 → 一键导出抖音/B站/小红书 + 文案。

**核心转变**：
- AI 做擅长的事（理解教学内容），不做不擅长的（模仿剪辑审美）
- 从"一条完整 mp4"改为"N 个片段 × 3 个平台"
- 用户预览确认分段，不追求全自动

详见 `docs/新方案_多平台切片工具.md`

---

## 当前代码状态

```
保留:
  scripts/run_asr.py           FunASR ASR 引擎（可复用）
  scripts/run_scenes.py        PySceneDetect 场景检测（可复用）
  docs/AI视频剪辑方案调研.md    原始调研

已删除（旧方案相关）:
  scripts/describe_frames.py   VLM 描述（硬编码参考视频）
  scripts/merge_content_map.py  合并 ASR+VLM（旧结构）
  scripts/translate_style.py    LLM 风格翻译（旧方案专用）
  scripts/match_style.py       标签匹配引擎（旧方案专用）
  scripts/render.py            渲染（fallback 到参考视频）
  scripts/process_video.py     处理新视频（路径全硬编码）
  scripts/extract_segments.py  工程文件分段（依赖 draft_content）
  scripts/parse_draft_deep.py  工程文件解析
  style_labels.json / skill_style.md  旧风格规则

可复用的知识资产:
  work/asr_result.json         参考视频 ASR 结果（272 句）
  work/frame_descriptions.json VLM 描述（17 段）
  work/content_map.json        ASR+VLM 合并结果
  ref/materials/               路线图素材（6 张）
  .env                         API Key 配置
```

---

## 当前进度（v2 多平台智能切片工具）

### ✅ 已完成 (2026-07-28)

```
新增:
├── engine/
│   ├── __init__.py          ✅ 模块入口
│   ├── pipeline.py          ✅ 核心管线（音频→ASR→场景→VLM→分段→评分）
│   ├── scorer.py            ✅ 片段评分引擎（5维度确定性打分）
│   └── exporter.py          ✅ 多平台导出器（MoviePy模板渲染）
├── templates/
│   ├── douyin.json          ✅ 抖音模板（9:16竖屏+大字幕+关键词弹窗+进度条）
│   ├── bilibili.json        ✅ B站模板（16:9+知识卡片+章节）
│   └── xiaohongshu.json     ✅ 小红书模板（1:1+要点覆盖+封面）
├── knowledge/
│   └── driving_exam.json    ✅ 驾考知识库（扣分点+高频错误+重点话题）
└── run.py                   ✅ 重写为简洁CLI入口
```

### 📋 待确认事项（已确认）

1. **界面形式**: 先 CLI，再加 Web 预览界面
2. **知识库**: 先用预填的 15 个话题 + 扣分点，跑起来再细调
3. **教学类型**: 先只聚焦驾考

### 🔜 下一步（在新机器上）

1. **准备测试视频** — 已放入 `input/SGOI6715.MOV`（4K HEVC 4GB）
2. **运行完整管线** — 建议先转 1080p 代理，参考 `HANDOFF_新机器交接.md`
3. **验证导出** — 用 ffmpeg CLI 代替 MoviePy（MoviePy 在 4K 下太慢）
4. **调优** — 根据实际效果调整评分权重、合并阈值、模板参数
5. **Web 预览界面** — 用轻量框架（Flask/FastAPI）做本地预览
6. **扩展** — 静音加速、BGM 叠加、关键词弹窗动画

### ⚠️ 已知问题

- **4K HEVC 性能瓶颈**: PySceneDetect 和 MoviePy 在 4K 源上超时，需用 1080p 代理
- **MoviePy API 兼容**: `write_videofile` 的 `verbose`/`preset` 参数在 v2.2.1 不支持
- **字体路径**: Pillow 需完整路径 `C:/Windows/Fonts/simhei.ttf`
