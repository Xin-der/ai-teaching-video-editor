# 驾校内容优化工具 · 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 上传一条视频（或粘贴文字）→ 生成 5 块《内容优化方案》（诊断 / 脚本改写 / 包装 / 转化话术 / 下期选题），Web 页展示 + markdown 文件。

**Architecture:** 复用现有理解栈。`engine/advisor.py` 编排：有视频时用 `Pipeline` 的 ASR 转录 + 可选 VLM 看帧，然后调用 `analyzer.generate_optimization_plan()` 生成方案。`web/app.py` 新增 `/api/optimize`（后台线程 + 状态轮询，复用导出任务的模式）。前端新增 `optimize.html`（上传/粘贴 → 生成 → 每块可复制）。

**Tech Stack:** Python 3.12 (`py -3.12`)、Flask、DashScope qwen3.7-plus（OpenAI 兼容）、现有 FunASR/ffmpeg 管线。

## Global Constraints

- Python 命令统一用 `py -3.12`（Windows）。
- 测试运行：`py -3.12 tests/test_advisor.py`（沿用现有 print 式自定义 runner，不用 pytest）。
- 单元测试**禁止调用真实 LLM API**——用 `unittest.mock.patch` 打桩。
- 现有代码用中文注释；新代码保持同样的注释密度和风格。
- 工作产物进 `work/`，输出进 `output/`（两者已被 `.gitignore` 忽略）。
- `.env` 里的 `DASHSCOPE_API_KEY` 仅在真实运行需要，单元测试不依赖。
- 只新增/改造必要路径，**不删除**任何旧模块（exporter/scorer/style_manager 保留但退出调用链）。
- 所有测试函数名以 `test_` 开头，runner 自动发现。

---

### Task 1: Pipeline 公开方法 + 测试骨架

**Files:**
- Modify: `engine/pipeline.py`（在 `run()` 方法之后、`_probe_video()` 之前插入两个公开方法）
- Create: `tests/test_advisor.py`

**Interfaces:**
- Produces: `Pipeline.extract_transcript() -> list[dict]`（每个 dict 含 `start/end/text`）；`Pipeline.extract_visuals() -> list[dict]`（帧描述列表，含 `topic/detail`）。供 Task 3 的 `advisor._analyze_video()` 使用。

- [ ] **Step 1: 写失败测试（同时创建测试文件骨架）**

创建 `tests/test_advisor.py`：

```python
"""内容顾问模块验证脚本

用法:
    py -3.12 tests/test_advisor.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def green(s): return f"[PASS] {s}"
def red(s): return f"[FAIL] {s}"
def header(s): return f"\n{'='*60}\n  {s}\n{'='*60}"


def test_pipeline_public_methods():
    """Pipeline 公开方法存在"""
    from engine.pipeline import Pipeline
    for m in ("extract_transcript", "extract_visuals"):
        assert hasattr(Pipeline, m), f"Pipeline 缺少方法: {m}"
    return True


def main():
    tests = [(name, fn) for name, fn in globals().items()
             if name.startswith("test_") and callable(fn)]
    results = {}
    for name, fn in tests:
        print(header(name))
        try:
            results[name] = bool(fn())
        except Exception as e:
            import traceback
            traceback.print_exc()
            results[name] = False
    passed = sum(1 for v in results.values() if v)
    print(f"\n{'='*60}\n  验证结果: {passed}/{len(results)} 通过\n{'='*60}")
    for name, ok in results.items():
        print(f"  {green('✓') if ok else red('✗')} {name}")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: 运行确认失败**

Run: `py -3.12 tests/test_advisor.py`
Expected: FAIL — `assert hasattr(Pipeline, "extract_transcript")` 触发 `Pipeline 缺少方法: extract_transcript`。

- [ ] **Step 3: 实现最小代码**

在 `engine/pipeline.py` 的 `run()` 方法结束之后、`_probe_video()` 之前插入：

```python
    def extract_transcript(self) -> list:
        """公开：音频提取 + ASR 转录，返回 ASR 段列表 [{start, end, text}, ...]"""
        self._extract_audio()
        self._run_asr()
        return self.asr_segments

    def extract_visuals(self) -> list:
        """公开：场景检测 + 关键帧抽取 + VLM 描述，返回帧描述列表"""
        self._detect_scenes()
        self._describe_frames()
        return self.frame_descriptions
```

- [ ] **Step 4: 运行确认通过**

Run: `py -3.12 tests/test_advisor.py`
Expected: PASS — `test_pipeline_public_methods` 通过，汇总 `1/1 通过`。

- [ ] **Step 5: 提交**

```bash
git add engine/pipeline.py tests/test_advisor.py
git commit -m "feat: Pipeline 增加公开转录/画面方法 + 测试骨架"
```

---

### Task 2: analyzer 生成《内容优化方案》

**Files:**
- Modify: `engine/analyzer.py`
  - 主入口区（`analyze_style` 之后、`_call_llm` 之前）插入 `generate_optimization_plan`
  - 内部方法区插入 `_build_plan_prompt` 和 `_validate_plan`
- Modify: `tests/test_advisor.py`（在 `def main():` 之前追加两个测试函数）

**Interfaces:**
- Consumes: `self.knowledge`（`__init__` 已加载的驾考知识库）；`self._call_llm(prompt) -> dict`（已有，失败返回含 `_error`/`_parse_error` 的 dict）
- Produces:
  - `ContentAnalyzer.generate_optimization_plan(transcript: str, vlm_summary: dict, city: str = "", platform: str = "douyin") -> dict`（5 块方案，字段补全）
  - `ContentAnalyzer._build_plan_prompt(transcript, vlm_summary, city, platform) -> str`
  - `ContentAnalyzer._validate_plan(plan: dict) -> dict`

- [ ] **Step 1: 写失败测试（追加到测试文件 `def main():` 之前）**

```python
def test_plan_prompt_builder():
    """方案 prompt 包含 5 块结构和城市注入"""
    from engine.analyzer import ContentAnalyzer
    a = ContentAnalyzer()
    prompt = a._build_plan_prompt(
        "教练说倒车入库一定要看点位",
        {"topics": ["倒车入库"], "visuals": ["车内视角"]},
        city="长沙",
        platform="douyin",
    )
    for key in ("diagnosis", "script_rewrite", "packaging", "conversion", "next_topics"):
        assert key in prompt, f"prompt 缺少 {key}"
    assert "长沙" in prompt, "prompt 未注入城市"
    assert "倒车入库" in prompt, "prompt 未注入 transcript"
    return True


def test_plan_validation():
    """_validate_plan 补全 5 块结构、保留已有字段"""
    from engine.analyzer import ContentAnalyzer
    a = ContentAnalyzer()
    plan = a._validate_plan({"diagnosis": {"summary": "诊断内容"}})
    for key in ("diagnosis", "script_rewrite", "packaging", "conversion", "next_topics"):
        assert key in plan, f"缺少 {key}"
    assert plan["diagnosis"]["summary"] == "诊断内容", "已有字段被覆盖"
    assert plan["diagnosis"]["issues"] == [], "缺失字段未补默认"
    assert isinstance(plan["next_topics"], list), "next_topics 应为列表"
    return True
```

- [ ] **Step 2: 运行确认失败**

Run: `py -3.12 tests/test_advisor.py`
Expected: FAIL — `AttributeError: 'ContentAnalyzer' object has no attribute '_build_plan_prompt'`（两个测试都失败）。

- [ ] **Step 3: 实现**

在 `engine/analyzer.py` 主入口区（`analyze_style` 方法之后）插入：

```python
    def generate_optimization_plan(self, transcript: str,
                                   vlm_summary: dict,
                                   city: str = "",
                                   platform: str = "douyin") -> dict:
        """生成 5 块《内容优化方案》。LLM 失败自动重试一次。"""
        prompt = self._build_plan_prompt(transcript, vlm_summary, city, platform)
        result = self._call_llm(prompt)
        if result.get("_error") or result.get("_parse_error"):
            result = self._call_llm(prompt)
        if result.get("_error") or result.get("_parse_error"):
            return result  # 交给上层报错
        return self._validate_plan(result)
```

在内部方法区（`_call_llm` 之后）插入：

```python
    def _build_plan_prompt(self, transcript: str, vlm_summary: dict,
                           city: str = "", platform: str = "douyin") -> str:
        """构建《内容优化方案》prompt"""
        transcript = transcript[:4000] if len(transcript) > 4000 else transcript

        # 领域知识注入（高频话题 + 扣分点）
        kb_lines = []
        for t in self.knowledge.get("high_frequency_topics", [])[:8]:
            kp = " / ".join(t.get("deduction_points", [])[:3])
            kb_lines.append(f"- {t['topic']}: {kp}")
        kb_text = "\n".join(kb_lines) or "- (无)"

        topics = vlm_summary.get("topics", [])
        visuals = vlm_summary.get("visuals", [])
        visuals_text = "\n".join(f"- {v}" for v in visuals[:6]) if visuals else "(无画面信息)"
        city_text = city or "未指定（不要虚构城市）"

        prompt = f"""你是一个深耕驾考行业的抖音内容运营专家。学员刷抖音不是看"教学"，是看"怎么过、去哪学"。请把一段驾考视频的原始内容，改写成学员会看完、会私信的短视频方案。

【驾考领域知识（高频话题与扣分点）】
{kb_text}

【视频内容 transcript】
{transcript}

【画面信息】
画面主题: {', '.join(topics) if topics else '未知'}
画面细节:
{visuals_text}

【所在城市（用于同城关键词）】{city_text}
【目标平台】{platform}

请只返回如下 JSON，不要输出任何其他文字：

{{
  "diagnosis": {{
    "summary": "这条视频为什么没人看，3句话以内，基于实际内容",
    "issues": ["3-5个具体问题，如：开头没钩子/没痛点/没同城词/没引导"],
    "strengths": ["1-3个优点"]
  }},
  "script_rewrite": {{
    "hook": "开头3秒文案，直击学员痛点",
    "body": "干货主体，保留教练原话但重组得更紧凑、更有条理",
    "proof": "证明/案例（学员通过、资质、对比）",
    "cta": "引导话术（关注/评论扣1/私信/留资）"
  }},
  "packaging": {{
    "title": "标题，≤30字，若城市已指定必须带上城市名和关键词",
    "cover_text": "封面大字，≤12字",
    "description": "简介，≤100字"
  }},
  "conversion": {{
    "pinned_comment": "置顶评论文案",
    "profile_bio": "主页简介文案",
    "dm_opening": "私信开场白，自然不推销"
  }},
  "next_topics": [
    {{"title": "选题1", "why": "学员为什么在搜它"}},
    {{"title": "选题2", "why": "学员为什么在搜它"}},
    {{"title": "选题3", "why": "学员为什么在搜它"}}
  ]
}}

规则：
1. 一切面向学员视角（"我怎么过、去哪学"），不是教练视角。
2. 诊断必须基于 transcript 实际内容，禁止套话。
3. 城市指定时，标题必须带上城市名。
4. next_topics 必须 3 个。"""
        return prompt

    def _validate_plan(self, plan: dict) -> dict:
        """确保 5 块结构完整，缺失字段补默认值"""
        defaults = {
            "diagnosis": {"summary": "", "issues": [], "strengths": []},
            "script_rewrite": {"hook": "", "body": "", "proof": "", "cta": ""},
            "packaging": {"title": "", "cover_text": "", "description": ""},
            "conversion": {"pinned_comment": "", "profile_bio": "", "dm_opening": ""},
            "next_topics": [],
        }
        for key, dflt in defaults.items():
            if key == "next_topics":
                if key not in plan or not isinstance(plan[key], list):
                    plan[key] = []
            elif key not in plan or not isinstance(plan[key], dict):
                plan[key] = dict(dflt)
            else:
                for sub, val in dflt.items():
                    plan[key].setdefault(sub, val)
        return plan
```

- [ ] **Step 4: 运行确认通过**

Run: `py -3.12 tests/test_advisor.py`
Expected: PASS — `test_plan_prompt_builder`、`test_plan_validation` 通过，汇总 `3/3 通过`。

- [ ] **Step 5: 提交**

```bash
git add engine/analyzer.py tests/test_advisor.py
git commit -m "feat: analyzer 新增内容优化方案生成"
```

---

### Task 3: advisor 核心模块 + markdown 输出

**Files:**
- Create: `engine/advisor.py`
- Modify: `tests/test_advisor.py`（追加 3 个测试函数）

**Interfaces:**
- Consumes:
  - `Pipeline(video_path, work_dir=...)` + `.extract_transcript()` + `.extract_visuals()`（Task 1）
  - `ContentAnalyzer().generate_optimization_plan(transcript, vlm_summary, city, platform)`（Task 2）
- Produces:
  - `ContentAdvisor(work_dir: str = "work")`
  - `ContentAdvisor.build_plan(*, video_path=None, text=None, city="", platform="douyin") -> dict`
  - `advisor.write_plan_markdown(plan: dict, out_path: str) -> str`（模块级函数）

- [ ] **Step 1: 写失败测试（追加到 `def main():` 之前）**

```python
def test_build_plan_no_input():
    """无视频无文字 → 返回 error"""
    from engine.advisor import ContentAdvisor
    advisor = ContentAdvisor(work_dir="work")
    result = advisor.build_plan()
    assert "error" in result, "应返回 error"
    return True


def test_build_plan_text_only():
    """纯文字输入 → 传给 analyzer 并返回方案（打桩）"""
    from unittest import mock
    from engine.advisor import ContentAdvisor

    fake_plan = {
        "diagnosis": {"summary": "诊断", "issues": ["x"], "strengths": ["y"]},
        "script_rewrite": {"hook": "", "body": "", "proof": "", "cta": ""},
        "packaging": {"title": "", "cover_text": "", "description": ""},
        "conversion": {"pinned_comment": "", "profile_bio": "", "dm_opening": ""},
        "next_topics": [],
    }
    advisor = ContentAdvisor(work_dir="work")
    with mock.patch("engine.analyzer.ContentAnalyzer") as M:
        inst = M.return_value
        inst.generate_optimization_plan.return_value = fake_plan
        result = advisor.build_plan(text="教练说倒车入库一定要看点位")
        assert result == fake_plan, "应直接返回 analyzer 的方案"
        transcript_arg = inst.generate_optimization_plan.call_args[0][0]
        assert "倒车入库" in transcript_arg, "transcript 未透传"
    return True


def test_write_plan_markdown():
    """markdown 文件包含 5 块标题"""
    import tempfile
    from engine.advisor import write_plan_markdown

    plan = {
        "diagnosis": {"summary": "诊断", "issues": ["没钩子"], "strengths": ["教学清晰"]},
        "script_rewrite": {"hook": "开头", "body": "主体", "proof": "证明", "cta": "引导"},
        "packaging": {"title": "标题", "cover_text": "封面", "description": "简介"},
        "conversion": {"pinned_comment": "置顶", "profile_bio": "主页", "dm_opening": "私信"},
        "next_topics": [{"title": "选题1", "why": "原因1"}],
    }
    with tempfile.TemporaryDirectory() as tmp:
        out = write_plan_markdown(plan, f"{tmp}/plan.md")
        assert out.endswith("plan.md")
        with open(out, "r", encoding="utf-8") as f:
            content = f.read()
        for sec in ("① 诊断", "② 脚本改写", "③ 包装", "④ 转化话术", "⑤ 下期选题"):
            assert sec in content, f"缺少 {sec}"
    return True
```

- [ ] **Step 2: 运行确认失败**

Run: `py -3.12 tests/test_advisor.py`
Expected: FAIL — `ModuleNotFoundError: No module named 'engine.advisor'`。

- [ ] **Step 3: 实现**

创建 `engine/advisor.py`：

```python
"""
内容顾问 — 上传视频/文字 → 生成《内容优化方案》

流程:
  有视频 → 复用 Pipeline 的 ASR 转录 + 可选 VLM 看帧
  有文字 → 直接用文字
  两者皆无 → 报错
  调 analyzer.generate_optimization_plan() 生成 5 块方案
"""

import json
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def write_plan_markdown(plan: dict, out_path: str) -> str:
    """把 5 块方案写成 markdown 文件，返回路径"""
    d = plan.get("diagnosis", {})
    s = plan.get("script_rewrite", {})
    p = plan.get("packaging", {})
    c = plan.get("conversion", {})

    issues = "；".join(d.get("issues", [])) if d.get("issues") else "（无）"
    strengths = "；".join(d.get("strengths", [])) if d.get("strengths") else "（无）"

    lines = [
        "# 内容优化方案", "",
        "## ① 诊断",
        d.get("summary", "") or "（无）",
        f"**问题**：{issues}",
        f"**优点**：{strengths}",
        "", "## ② 脚本改写",
        "**开头3秒**：" + s.get("hook", ""),
        "**主体**：" + s.get("body", ""),
        "**证明**：" + s.get("proof", ""),
        "**引导**：" + s.get("cta", ""),
        "", "## ③ 包装",
        "**标题**：" + p.get("title", ""),
        "**封面文字**：" + p.get("cover_text", ""),
        "**简介**：" + p.get("description", ""),
        "", "## ④ 转化话术",
        "**置顶评论**：" + c.get("pinned_comment", ""),
        "**主页简介**：" + c.get("profile_bio", ""),
        "**私信开场白**：" + c.get("dm_opening", ""),
        "", "## ⑤ 下期选题",
    ]
    for t in plan.get("next_topics", []):
        lines.append(f"- **{t.get('title', '')}** — {t.get('why', '')}")

    text = "\n".join(lines)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(text)
    return out_path


class ContentAdvisor:
    """内容顾问：输入视频/文字 → 5 块《内容优化方案》"""

    def __init__(self, work_dir: str = "work"):
        self.work_dir = Path(work_dir)
        self.work_dir.mkdir(parents=True, exist_ok=True)

    def build_plan(self, *, video_path=None, text=None,
                   city: str = "", platform: str = "douyin") -> dict:
        """主入口。video_path 和 text 至少提供一个，text 优先。"""
        transcript = ""
        vlm_summary = {}

        if text and text.strip():
            transcript = text.strip()
        elif video_path:
            if not os.path.exists(video_path):
                return {"error": f"视频文件不存在: {video_path}"}
            transcript, vlm_summary = self._analyze_video(video_path)
        else:
            return {"error": "请上传视频或粘贴文字"}

        if not transcript or not transcript.strip():
            return {"error": "没有听到说话内容，请换一个视频或粘贴文字"}

        from engine.analyzer import ContentAnalyzer
        analyzer = ContentAnalyzer()
        plan = analyzer.generate_optimization_plan(
            transcript, vlm_summary, city, platform,
        )
        if plan.get("_error"):
            return {"error": f"方案生成失败: {plan.get('_error')}"}
        if plan.get("_parse_error"):
            return {"error": "方案解析失败，请重试"}
        return plan

    def _analyze_video(self, video_path: str) -> tuple:
        """复用 Pipeline 的 ASR + VLM。返回 (transcript_str, vlm_summary_dict)。"""
        from engine.pipeline import Pipeline

        p = Pipeline(video_path, work_dir=str(self.work_dir))
        p._probe_video()
        segs = p.extract_transcript()
        transcript = " ".join(s.get("text", "") for s in segs)

        vlm_summary = {"topics": [], "visuals": []}
        try:
            frames = p.extract_visuals()
            topics = list(dict.fromkeys(
                fd.get("topic", "") for fd in frames if fd.get("topic")
            ))
            visuals = [fd.get("detail", "") for fd in frames if fd.get("detail")]
            vlm_summary = {"topics": topics, "visuals": visuals, "frame_count": len(frames)}
        except Exception as e:
            print(f"  ⚠ VLM 描述失败（非阻塞，跳过）: {e}")
        return transcript, vlm_summary
```

- [ ] **Step 4: 运行确认通过**

Run: `py -3.12 tests/test_advisor.py`
Expected: PASS — `test_build_plan_no_input`、`test_build_plan_text_only`、`test_write_plan_markdown` 通过，汇总 `6/6 通过`。

- [ ] **Step 5: 提交**

```bash
git add engine/advisor.py tests/test_advisor.py
git commit -m "feat: 新增内容顾问 advisor 模块 + markdown 输出"
```

---

### Task 4: web 后端接口

**Files:**
- Modify: `web/app.py`
  - `app.py` 顶部模块级（`_export_status` 附近）新增 `_optimize_status` 全局
  - `/api/optimize` 路由 + `/api/optimize/status` 路由 + `_run_optimize` 函数（放在 `_run_export` 之后）
- Modify: `tests/test_advisor.py`（追加 1 个测试）

**Interfaces:**
- Consumes: `engine.advisor.ContentAdvisor`、`engine.advisor.write_plan_markdown`（Task 3）；`WORK_DIR`/`OUTPUT_DIR`（app.py 已有）
- Produces:
  - `POST /api/optimize`（multipart `video` + 表单 `city`/`platform`，或 JSON `{text, city, platform}`）→ `{"status": "started"}`
  - `GET /api/optimize/status` → `{running, progress, plan, error, markdown_path}`
  - `_run_optimize(payload: dict)`（模块级函数，供测试直接调用）

- [ ] **Step 1: 写失败测试（追加到 `def main():` 之前）**

```python
def test_run_optimize():
    """_run_optimize 成功路径：设置 plan 和 markdown_path"""
    from unittest import mock
    import web.app as app_mod

    fake_plan = {
        "diagnosis": {"summary": "诊断", "issues": [], "strengths": []},
        "script_rewrite": {"hook": "", "body": "", "proof": "", "cta": ""},
        "packaging": {"title": "", "cover_text": "", "description": ""},
        "conversion": {"pinned_comment": "", "profile_bio": "", "dm_opening": ""},
        "next_topics": [],
    }
    with mock.patch("engine.advisor.ContentAdvisor") as M, \
         mock.patch("engine.advisor.write_plan_markdown") as W:
        inst = M.return_value
        inst.build_plan.return_value = fake_plan
        W.return_value = "/fake/plan.md"

        app_mod._optimize_status = {"running": True, "progress": "", "plan": None, "error": None, "markdown_path": None}
        app_mod._run_optimize({"text": "测试文字", "city": "长沙", "platform": "douyin"})

    assert app_mod._optimize_status["plan"] == fake_plan, "plan 未写入状态"
    assert app_mod._optimize_status["markdown_path"] == "/fake/plan.md", "markdown 路径未写入"
    assert app_mod._optimize_status["running"] is False, "running 未复位"
    return True
```

- [ ] **Step 2: 运行确认失败**

Run: `py -3.12 tests/test_advisor.py`
Expected: FAIL — `AttributeError: module 'web.app' has no attribute '_run_optimize'`。

- [ ] **Step 3: 实现**

3a. 在 `web/app.py` 的模块级（`_export_status = {...}` 附近）新增：

```python
# 内容优化任务状态
_optimize_status = {"running": False, "progress": "", "plan": None, "error": None, "markdown_path": None}
```

3b. 在 `_run_export` 函数之后追加：

```python
@app.route("/api/optimize", methods=["POST"])
def api_optimize():
    """触发内容优化：上传视频(multipart) 或 粘贴文字(JSON)"""
    global _optimize_status
    if _optimize_status["running"]:
        return jsonify({"error": "正在生成中，请稍候"}), 409

    payload = {}
    if "video" in request.files and request.files["video"].filename:
        f = request.files["video"]
        upload_dir = WORK_DIR / "uploads"
        upload_dir.mkdir(parents=True, exist_ok=True)
        save_path = str(upload_dir / Path(f.filename).name)
        f.save(save_path)
        payload = {
            "video_path": save_path,
            "city": (request.form.get("city") or "").strip(),
            "platform": (request.form.get("platform") or "douyin").strip(),
        }
    else:
        data = request.get_json(silent=True) or {}
        payload = {
            "text": (data.get("text") or "").strip(),
            "city": (data.get("city") or "").strip(),
            "platform": (data.get("platform") or "douyin").strip(),
        }
        if not payload["text"]:
            return jsonify({"error": "请上传视频或粘贴文字"}), 400

    _optimize_status = {"running": True, "progress": "准备生成...", "plan": None, "error": None, "markdown_path": None}
    threading.Thread(target=_run_optimize, args=(payload,), daemon=True).start()
    return jsonify({"status": "started"})


@app.route("/api/optimize/status")
def api_optimize_status():
    """查询内容优化状态"""
    return jsonify(_optimize_status)


def _run_optimize(payload):
    """后台线程：调用 advisor 生成方案 + 写 markdown"""
    global _optimize_status
    try:
        engine_path = str(ROOT)
        if engine_path not in sys.path:
            sys.path.insert(0, engine_path)

        from engine.advisor import ContentAdvisor, write_plan_markdown

        _optimize_status["progress"] = "分析内容中..."
        advisor = ContentAdvisor(work_dir=str(WORK_DIR))
        plan = advisor.build_plan(
            video_path=payload.get("video_path"),
            text=payload.get("text"),
            city=payload.get("city", ""),
            platform=payload.get("platform", "douyin"),
        )

        if plan.get("error"):
            _optimize_status["error"] = plan["error"]
            _optimize_status["running"] = False
            return

        _optimize_status["plan"] = plan
        out_dir = OUTPUT_DIR / "optimize"
        out_dir.mkdir(parents=True, exist_ok=True)
        from datetime import datetime
        md_path = str(out_dir / f"plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md")
        write_plan_markdown(plan, md_path)
        _optimize_status["markdown_path"] = md_path
        _optimize_status["progress"] = "完成"
        _optimize_status["running"] = False
    except Exception as e:
        _optimize_status["error"] = str(e)
        _optimize_status["running"] = False
```

- [ ] **Step 4: 运行确认通过**

Run: `py -3.12 tests/test_advisor.py`
Expected: PASS — `test_run_optimize` 通过，汇总 `7/7 通过`。

- [ ] **Step 5: 提交**

```bash
git add web/app.py tests/test_advisor.py
git commit -m "feat: web 新增内容优化接口"
```

---

### Task 5: 前端优化页面

**Files:**
- Create: `web/templates/optimize.html`
- Modify: `web/app.py`（`/` 路由改渲染 `optimize.html`）
- Modify: `tests/test_advisor.py`（追加 1 个测试）

**Interfaces:**
- Consumes: `POST /api/optimize`、`GET /api/optimize/status`（Task 4）
- Produces: `/` 渲染 `optimize.html`（上传/粘贴 → 生成 → 5 块卡片 + 复制按钮）

- [ ] **Step 1: 写失败测试（追加到 `def main():` 之前）**

```python
def test_optimize_page_renders():
    """首页渲染优化工具页面"""
    from web.app import app
    client = app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200, f"状态码 {resp.status_code}"
    body = resp.get_data(as_text=True)
    assert "内容优化" in body, "页面缺少标题"
    assert "生成方案" in body, "页面缺少生成按钮"
    return True
```

- [ ] **Step 2: 运行确认失败**

Run: `py -3.12 tests/test_advisor.py`
Expected: FAIL — `render_template('optimize.html')` 报 `TemplateNotFound: optimize.html`（Task 4 未改 `/` 路由时，这里先按"页面不存在"失败）。

- [ ] **Step 3: 实现**

3a. 创建 `web/templates/optimize.html`：

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>驾校内容优化工具</title>
<style>
:root { --bg:#0f0f0f; --surface:#1a1a1a; --border:#2a2a2a; --text:#e0e0e0; --text2:#999; --accent:#ff4444; --accent2:#00a8ff; --green:#4caf50; }
* { margin:0; padding:0; box-sizing:border-box; }
body { font-family:-apple-system,"Microsoft YaHei",sans-serif; background:var(--bg); color:var(--text); min-height:100vh; }
.header { background:var(--surface); border-bottom:1px solid var(--border); padding:12px 24px; display:flex; align-items:center; gap:12px; position:sticky; top:0; z-index:100; }
.header h1 { font-size:18px; font-weight:600; }
.container { max-width:900px; margin:0 auto; padding:24px; }
.card { background:var(--surface); border:1px solid var(--border); border-radius:10px; padding:20px; margin-bottom:16px; }
.card h2 { font-size:15px; margin-bottom:14px; }
label { display:block; font-size:13px; color:var(--text2); margin:14px 0 6px; }
.input { width:100%; background:#111; border:1px solid var(--border); border-radius:8px; padding:12px; color:var(--text); font-family:"Microsoft YaHei",sans-serif; font-size:14px; }
textarea.input { min-height:120px; resize:vertical; }
.row { display:flex; gap:12px; align-items:flex-end; }
.row > div { flex:1; }
.btn { display:inline-flex; align-items:center; justify-content:center; gap:6px; padding:10px 20px; border:none; border-radius:8px; font-size:14px; font-weight:600; cursor:pointer; }
.btn-primary { background:var(--accent); color:#fff; width:100%; margin-top:16px; }
.btn-primary:disabled { background:#444; cursor:not-allowed; }
.btn-sm { padding:6px 12px; font-size:12px; border-radius:6px; }
.btn-outline { background:transparent; border:1px solid var(--border); color:var(--text); }
.btn-outline:hover { border-color:var(--accent2); }
.field { display:flex; gap:10px; margin-bottom:8px; font-size:13px; line-height:1.6; }
.field .k { flex-shrink:0; color:var(--text2); min-width:70px; }
.muted { color:var(--text2); font-size:12px; }
.progress { display:none; margin-top:12px; }
.progress-text { font-size:12px; color:var(--text2); }
#result { display:none; }
.copy-row { margin-top:8px; text-align:right; }
.toast { position:fixed; bottom:24px; right:24px; background:var(--green); color:#fff; padding:12px 20px; border-radius:8px; font-size:14px; z-index:300; display:none; }
.toast.error { background:var(--accent); }
</style>
</head>
<body>

<div class="header">
  <h1>🚗 驾校内容优化工具</h1>
  <span class="muted">上传视频 → 得到可直接照着改、照着发的方案</span>
</div>

<div class="container">
  <div class="card">
    <h2>📤 输入内容</h2>
    <label>上传视频（原始素材/剪辑过均可，需有说话内容）</label>
    <input type="file" id="video-file" class="input" accept="video/*">
    <label>或粘贴文字（脚本/简介/口述）</label>
    <textarea id="input-text" class="input" placeholder="把视频内容粘贴到这里，二选一"></textarea>
    <div class="row">
      <div>
        <label>所在城市（可选，用于同城关键词）</label>
        <input type="text" id="city" class="input" placeholder="如：长沙">
      </div>
      <div>
        <label>目标平台</label>
        <select id="platform" class="input">
          <option value="douyin">抖音</option>
        </select>
      </div>
    </div>
    <button class="btn btn-primary" id="gen-btn" onclick="generate()">✨ 生成方案</button>
    <div class="progress" id="progress">
      <div class="progress-text" id="progress-text">准备生成...</div>
    </div>
  </div>

  <div id="result"></div>
</div>

<div class="toast" id="toast"></div>

<script>
let currentPlan = null;
let pollTimer = null;
const KEYS = ['diagnosis', 'script_rewrite', 'packaging', 'conversion', 'next_topics'];

document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('gen-btn');
  const file = document.getElementById('video-file');
  const text = document.getElementById('input-text');
  const sync = () => { btn.disabled = !(file.files.length || text.value.trim()); };
  file.addEventListener('change', sync);
  text.addEventListener('input', sync);
  sync();
});

async function generate() {
  const file = document.getElementById('video-file').files[0];
  const text = document.getElementById('input-text').value.trim();
  const city = document.getElementById('city').value.trim();
  const platform = document.getElementById('platform').value;
  if (!file && !text) { toast('请选择视频或粘贴文字', true); return; }

  const btn = document.getElementById('gen-btn');
  btn.disabled = true;
  document.getElementById('result').style.display = 'none';
  document.getElementById('progress').style.display = 'block';
  document.getElementById('progress-text').textContent = '准备生成...';

  let res;
  try {
    if (file) {
      const fd = new FormData();
      fd.append('video', file);
      fd.append('city', city);
      fd.append('platform', platform);
      res = await fetch('/api/optimize', { method: 'POST', body: fd });
    } else {
      res = await fetch('/api/optimize', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text, city, platform }),
      });
    }
    if (!res.ok) {
      const e = await res.json();
      throw new Error(e.error || '提交失败');
    }
    pollStatus();
  } catch (e) {
    toast(e.message, true);
    btn.disabled = false;
    document.getElementById('progress').style.display = 'none';
  }
}

function pollStatus() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    try {
      const s = await (await fetch('/api/optimize/status')).json();
      document.getElementById('progress-text').textContent = s.progress || '';
      if (s.error) {
        clearInterval(pollTimer);
        toast(s.error, true);
        resetBtn();
        return;
      }
      if (s.plan) {
        clearInterval(pollTimer);
        currentPlan = s.plan;
        renderPlan(s.plan);
        resetBtn();
      }
    } catch (e) { console.error(e); }
  }, 1000);
}

function resetBtn() {
  document.getElementById('gen-btn').disabled = false;
  setTimeout(() => { document.getElementById('progress').style.display = 'none'; }, 500);
}

function renderPlan(plan) {
  const box = document.getElementById('result');
  box.style.display = 'block';
  box.innerHTML = [
    planCard('① 诊断', renderObj(plan.diagnosis), 0),
    planCard('② 脚本改写', renderObj(plan.script_rewrite), 1),
    planCard('③ 包装', renderObj(plan.packaging), 2),
    planCard('④ 转化话术', renderObj(plan.conversion), 3),
    planCard('⑤ 下期选题', renderTopics(plan.next_topics), 4),
  ].join('');
  box.scrollIntoView({ behavior: 'smooth' });
}

function planCard(title, html, idx) {
  return `<div class="card"><h2>${title}</h2>${html}
    <div class="copy-row"><button class="btn btn-sm btn-outline" onclick="copyBlock(${idx})">📋 复制</button></div>
  </div>`;
}

function renderObj(obj) {
  if (!obj || !Object.keys(obj).length) return '<p class="muted">（无）</p>';
  return Object.entries(obj).map(([k, v]) => {
    if (Array.isArray(v)) v = v.join('；');
    return `<p class="field"><span class="k">${esc(k)}</span><span class="v">${esc(String(v))}</span></p>`;
  }).join('');
}

function renderTopics(list) {
  if (!list || !list.length) return '<p class="muted">（无）</p>';
  return list.map(t =>
    `<p class="field"><span class="k">选题</span><span class="v">${esc(t.title || '')} — ${esc(t.why || '')}</span></p>`
  ).join('');
}

function copyBlock(idx) {
  const data = currentPlan ? currentPlan[KEYS[idx]] : null;
  const text = fmtBlock(data);
  if (!text) { toast('没有可复制的内容', true); return; }
  navigator.clipboard.writeText(text).then(() => toast('已复制 ✅')).catch(() => toast('复制失败', true));
}

function fmtBlock(obj) {
  if (Array.isArray(obj)) {
    return obj.map(t => `${t.title || ''}：${t.why || ''}`).join('\n');
  }
  if (!obj) return '';
  const names = { summary:'诊断', issues:'问题', strengths:'优点', hook:'开头3秒', body:'主体', proof:'证明', cta:'引导', title:'标题', cover_text:'封面文字', description:'简介', pinned_comment:'置顶评论', profile_bio:'主页简介', dm_opening:'私信开场白' };
  return Object.entries(obj).map(([k, v]) => {
    if (Array.isArray(v)) v = v.join('；');
    return `${names[k] || k}：${v}`;
  }).join('\n');
}

function toast(msg, isError) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.toggle('error', !!isError);
  t.style.display = 'block';
  setTimeout(() => { t.style.display = 'none'; }, 2500);
}

function esc(s) { return (s || '').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }
</script>

</body>
</html>
```

3b. 修改 `web/app.py` 的 `/` 路由：

```python
@app.route("/")
def index():
    """主页面：内容优化工具"""
    return render_template("optimize.html")
```

- [ ] **Step 4: 运行确认通过**

Run: `py -3.12 tests/test_advisor.py`
Expected: PASS — `test_optimize_page_renders` 通过，汇总 `8/8 通过`。

- [ ] **Step 5: 提交**

```bash
git add web/templates/optimize.html web/app.py tests/test_advisor.py
git commit -m "feat: 内容优化前端页面"
```

---

### Task 6: run.py CLI 支持 `--optimize`

**Files:**
- Modify: `run.py`
  - 把 `main()` 里的 `argparse.ArgumentParser(...)` 抽成模块级 `build_parser()`，并新增 `--optimize`/`--city`/`--text` 参数
  - 视频存在性检查改为"视频或文字模式"两者满足其一即可
  - 在 API Key 检查之后、`--only-export` 之前插入 `--optimize` 分支
- Modify: `tests/test_advisor.py`（追加 2 个测试）

**Interfaces:**
- Consumes: `engine.advisor.ContentAdvisor`（Task 3）
- Produces: `run.build_parser() -> argparse.ArgumentParser`；`py -3.12 run.py <视频> --optimize [--city 长沙]` 或 `py -3.12 run.py --optimize --text "..."` 打印方案 JSON

- [ ] **Step 1: 写失败测试（追加到 `def main():` 之前）**

```python
def test_cli_parser_has_optimize():
    """run.py 参数包含 --optimize/--city/--text"""
    import run
    p = run.build_parser()
    args = p.parse_args(["--optimize", "--text", "一段驾考教学", "--city", "长沙"])
    assert args.optimize is True, "--optimize 未解析"
    assert args.text == "一段驾考教学", "--text 未解析"
    assert args.city == "长沙", "--city 未解析"
    return True


def test_cli_optimize_text_runs():
    """--optimize --text 走 advisor 并返回（打桩，不调真实 LLM）"""
    from unittest import mock
    import run

    fake_plan = {
        "diagnosis": {"summary": "ok", "issues": [], "strengths": []},
        "script_rewrite": {"hook": "", "body": "", "proof": "", "cta": ""},
        "packaging": {"title": "", "cover_text": "", "description": ""},
        "conversion": {"pinned_comment": "", "profile_bio": "", "dm_opening": ""},
        "next_topics": [],
    }
    old_argv = sys.argv
    sys.argv = ["run.py", "--optimize", "--text", "教练说倒车入库要看点位", "--city", "长沙"]
    try:
        with mock.patch("engine.advisor.ContentAdvisor") as M:
            inst = M.return_value
            inst.build_plan.return_value = fake_plan
            result = run.main()
        assert result is None, f"main() 应正常返回, 得到 {result}"
        inst.build_plan.assert_called_once()
    finally:
        sys.argv = old_argv
    return True
```

- [ ] **Step 2: 运行确认失败**

Run: `py -3.12 tests/test_advisor.py`
Expected: FAIL — `AttributeError: module 'run' has no attribute 'build_parser'`。

- [ ] **Step 3: 实现**

3a. 在 `run.py` 中把 `main()` 开头的 parser 构建抽成模块级函数。原 `main()` 里：

```python
def main():
    parser = argparse.ArgumentParser(
        description="多平台智能切片工具 — 长教学视频 → 智能切片 → 多平台导出 + 文案",
        ...
    )
    parser.add_argument("video", nargs="?", help="输入视频路径（使用 --web 时可选）")
    ...
    args = parser.parse_args()
```

改为：

```python
def build_parser() -> argparse.ArgumentParser:
    """构建命令行参数解析器"""
    parser = argparse.ArgumentParser(
        description="多平台智能切片工具 — 长教学视频 → 智能切片 → 多平台导出 + 文案",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python run.py input/video.mp4                    分段预览
  python run.py input/video.mp4 --export            分段 + 全平台导出
  python run.py input/video.mp4 --optimize          内容优化（出方案）
  python run.py --optimize --text "粘贴内容"        文字内容优化
        """,
    )
    parser.add_argument("video", nargs="?", help="输入视频路径（使用 --web 时可选）")
    parser.add_argument("--output-dir", default="output", help="输出目录 (默认: output)")
    parser.add_argument("--work-dir", default="work", help="工作目录 (默认: work)")

    # 步骤跳过
    parser.add_argument("--skip-audio", action="store_true", help="跳过音频提取")
    parser.add_argument("--skip-asr", action="store_true", help="跳过 ASR 语音识别")
    parser.add_argument("--skip-scenes", action="store_true", help="跳过场景检测")
    parser.add_argument("--skip-vlm", action="store_true", help="跳过 VLM 关键帧描述")
    parser.add_argument("--skip-llm", action="store_true", help="跳过 LLM 内容分析")
    parser.add_argument("--skip-all", action="store_true", help="跳过所有分析步骤")

    # 导出
    parser.add_argument("--export", action="store_true", help="分段后自动导出")
    parser.add_argument("--platforms", default="douyin,bilibili,xiaohongshu",
                        help="导出平台，逗号分隔 (默认: douyin,bilibili,xiaohongshu)")

    # 其他
    parser.add_argument("--interactive", action="store_true",
                        help="交互模式：分段后等待确认再导出")
    parser.add_argument("--only-export", action="store_true",
                        help="仅导出（不运行管线，使用已有分段结果）")
    parser.add_argument("--web", action="store_true",
                        help="启动 Web 预览界面（本地浏览器）")
    parser.add_argument("--web-port", type=int, default=5000,
                        help="Web 界面端口 (默认: 5000)")

    # 内容优化
    parser.add_argument("--optimize", action="store_true",
                        help="内容优化模式：视频/文字 → 《内容优化方案》")
    parser.add_argument("--city", default="", help="所在城市（用于同城关键词）")
    parser.add_argument("--text", default="", help="直接输入文字内容（代替视频）")
    return parser


def main():
    args = build_parser().parse_args()
```

3b. 修改视频存在性检查（原 `if not args.video:` 处）：

```python
    # 检查视频文件（--optimize --text 模式可无视频）
    if not args.video and not (args.optimize and args.text):
        print("❌ 请指定视频文件")
        print(f"\n用法:")
        print(f"   python run.py <视频路径>             运行管线")
        print(f"   python run.py <视频路径> --export     管线 + 导出")
        print(f"   python run.py --web                   启动 Web 预览界面")
        print(f"   python run.py --optimize --text \"...\"  文字内容优化")
        sys.exit(1)
    if args.video and not os.path.exists(args.video):
        print(f"❌ 找不到视频文件: {args.video}")
        print(f"\n💡 请将视频放入 input/ 目录，然后运行:")
        print(f"   python run.py input/你的视频.mp4")
        sys.exit(1)
```

3c. 在 API Key 检查（`if not os.environ.get("DASHSCOPE_API_KEY"):`）之后、`# --- 仅导出模式 ---` 之前插入：

```python
    # --- 内容优化模式 ---
    if args.optimize:
        import json as _json
        from engine.advisor import ContentAdvisor

        print("🚀 内容优化模式...")
        advisor = ContentAdvisor(work_dir=args.work_dir)
        plan = advisor.build_plan(
            video_path=args.video,
            text=args.text or None,
            city=args.city,
        )
        print(_json.dumps(plan, ensure_ascii=False, indent=2))
        if plan.get("error"):
            sys.exit(1)
        return
```

- [ ] **Step 4: 运行确认通过**

Run: `py -3.12 tests/test_advisor.py`
Expected: PASS — `test_cli_parser_has_optimize`、`test_cli_optimize_text_runs` 通过，汇总 `10/10 通过`。

- [ ] **Step 5: 提交**

```bash
git add run.py tests/test_advisor.py
git commit -m "feat: run.py 支持 --optimize 内容优化模式"
```

---

### Task 7: 集成验收（真实 API + 真实视频）

**Files:**
- 无代码改动；验证用。

**Interfaces:**
- Consumes: 前 6 个任务的全部产物；`.env` 中的 `DASHSCOPE_API_KEY`；`input/` 下有真实视频（如 `PNIK4383.MOV`）。

- [ ] **Step 1: 全部单元测试通过**

Run: `py -3.12 tests/test_advisor.py`
Expected: `10/10 通过`。

- [ ] **Step 2: CLI 文字模式真实调用（验证 LLM 出真方案）**

Run: `py -3.12 run.py --optimize --text "教练说科目二倒车入库，车身出线直接扣100分，点位一定要看准，很多人挂科都是这个原因" --city 长沙`
Expected: 打印 5 块 JSON，无 `_error`/`_parse_error`，`title` 含"长沙"或"倒库"。

- [ ] **Step 3: CLI 视频模式真实调用（验证 ASR+VLM+LLM 全链路）**

Run: `py -3.12 run.py input/PNIK4383.MOV --optimize --city 长沙`
Expected: 打印 5 块 JSON；若 ASR 空则返回"没有听到说话内容"，属正常（换有讲解的视频）。

- [ ] **Step 4: Web 界面人工验收**

Run: `py -3.12 run.py --web` → 浏览器打开 `http://127.0.0.1:5000`
Expected:
1. 页面上传视频 → "生成方案" → 进度显示 → 5 块卡片出现
2. 每块"复制"按钮能复制到剪贴板
3. 纯粘贴文字同样能出方案
4. `output/optimize/` 下生成对应 markdown 文件

- [ ] **Step 5: 记录已知问题到 HANDOFF.md 的"遗留问题"区（如有）**

把真实运行中发现的问题（如 ASR 对车内噪音的识别、LLM 偶发非法 JSON）追加到 `HANDOFF.md`，方便下一轮迭代。提交：

```bash
git add HANDOFF.md
git commit -m "docs: 记录内容优化工具首轮验收发现"
```

---

## Self-Review

**1. Spec coverage（对照 `docs/superpowers/specs/2026-08-01-driving-content-optimizer-design.md`）**
- 输入（视频/文字 + 城市 + 平台）→ Task 4 接口 + Task 3 `build_plan` ✅
- 5 块输出 → Task 2 prompt/JSON + Task 3 markdown ✅
- 复用理解栈（ASR/VLM）→ Task 1 公开方法 + Task 3 `_analyze_video` ✅
- 砍渲染/切片 → 无任务触碰 exporter 调用链 ✅
- Web 展示 + 复制 → Task 4/5 ✅
- CLI 测试用 → Task 6 ✅
- 错误处理（无说话内容/非法 JSON/VLM 失败）→ Task 3 + Task 2 重试 ✅
- 测试 → tests/test_advisor.py 10 项 ✅
- 验证标准（<5 分钟出方案、可照抄）→ Task 7 人工验收 ✅

**2. Placeholder scan:** 所有步骤均含实际代码，无 TBD/TODO/"添加适当错误处理"类占位 ✅

**3. Type consistency:**
- `Pipeline.extract_transcript()/extract_visuals()`（Task 1）→ Task 3 `_analyze_video` 调用 ✅
- `generate_optimization_plan(transcript, vlm_summary, city, platform)`（Task 2）→ Task 3 调用 ✅
- `build_plan(*, video_path, text, city, platform)`（Task 3）→ Task 4 `_run_optimize`、Task 6 CLI 调用 ✅
- `write_plan_markdown(plan, out_path)`（Task 3）→ Task 4 调用 ✅
- 测试桩 `fake_plan` 的 5 块结构与 `_validate_plan` 默认结构一致 ✅
