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

## 下一步（下次会话）

详见 `HANDOFF.md`

核心任务：
1. 新建 `engine/pipeline.py` — 核心管线
2. 新建 `engine/scorer.py` — 片段评分引擎  
3. 新建 `engine/exporter.py` — 多平台模板导出
4. 新建 `templates/` — 三个平台的 JSON 模板
5. 新建 `knowledge/driving_exam.json` — 驾考知识库
6. 重写 `run.py` — 简洁入口

先做最小版本：分段 + 评分 + 抖音导出，验证链路后再扩展。
