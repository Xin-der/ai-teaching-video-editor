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
    import os
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
        with mock.patch("engine.advisor.ContentAdvisor") as M, \
             mock.patch.dict(os.environ, {"DASHSCOPE_API_KEY": "test"}):
            inst = M.return_value
            inst.build_plan.return_value = fake_plan
            result = run.main()
        assert result is None, f"main() 应正常返回, 得到 {result}"
        inst.build_plan.assert_called_once()
    finally:
        sys.argv = old_argv
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
