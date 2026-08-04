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


def test_build_plan_video_isolated_workdir():
    """视频路径每次分析用独立工作目录，避免复用上一个视频的固定文件名缓存"""
    import os
    import tempfile
    from unittest import mock
    from engine.advisor import ContentAdvisor

    with tempfile.TemporaryDirectory() as tmp:
        advisor = ContentAdvisor(work_dir=tmp)
        fake1 = os.path.join(tmp, "video_a.mp4")
        fake2 = os.path.join(tmp, "video_b.mp4")
        open(fake1, "w").close()
        open(fake2, "w").close()

        with mock.patch("engine.pipeline.Pipeline") as M:
            M.return_value.extract_transcript.return_value = [
                {"start": 0, "end": 1, "text": "视频A的转录"}
            ]
            M.return_value.extract_visuals.return_value = []
            advisor._analyze_video(fake1)
            advisor._analyze_video(fake2)

        workdirs = [c.kwargs.get("work_dir") for c in M.call_args_list]
        assert len(workdirs) == 2, "应针对两个视频各创建一次 Pipeline"
        assert workdirs[0] != workdirs[1], \
            "两次视频分析复用了同一工作目录——新视频会读到旧 audio.wav/asr_result.json 缓存"
        for w in workdirs:
            assert w.startswith(tmp), "工作目录应位于 advisor 的 work_dir 之下"
    return True


def test_build_plan_insufficient_transcript_clear_error():
    """转录/文字过短 → 返回友好错误，不进入 LLM 生成"""
    import os
    import tempfile
    from unittest import mock
    from engine.advisor import ContentAdvisor

    advisor = ContentAdvisor(work_dir="work")
    # 文字过短
    r = advisor.build_plan(text="系。")
    assert "error" in r and "太短" in r["error"], f"文字过短应提示太短: {r}"

    # 视频转录过短（打桩 _analyze_video，避免真实 ASR）
    with mock.patch.object(ContentAdvisor, "_analyze_video",
                           return_value=("系。", {}, [])):
        with tempfile.TemporaryDirectory() as tmp:
            v = os.path.join(tmp, "x.mp4")
            open(v, "w").close()
            r2 = advisor.build_plan(video_path=v)
    assert "error" in r2 and "太短" in r2["error"], f"视频转录过短应提示太短: {r2}"
    return True


def test_plan_prompt_supports_generic_content():
    """方案 prompt 对非驾考内容也能按实际内容输出（不强行套驾考框架）"""
    from engine.analyzer import ContentAnalyzer
    a = ContentAnalyzer()
    prompt = a._build_plan_prompt(
        "这是一段讲做菜的短视频", {"topics": ["其他"], "visuals": []},
        city="", platform="douyin",
    )
    assert "不是驾考" in prompt, "prompt 应声明非驾考内容按实际主题处理"
    assert "实际内容" in prompt, "prompt 应强调基于实际内容"
    for key in ("diagnosis", "script_rewrite", "packaging", "conversion", "next_topics"):
        assert key in prompt, f"prompt 缺少 {key}"
    return True


def test_frame_diagnose_selects_top_and_sanitizes():
    """帧诊断：按最严重问题取 top 帧；越界坐标丢弃；severity 收敛 0-1"""
    from unittest import mock
    import engine.frame_diagnose as fd

    problems_a = [{"category": "lighting", "label": "逆光", "box": [0.1, 0.1, 0.5, 0.5],
                   "severity": 0.3, "advice": "补光"}]
    problems_b = [{"category": "blur", "label": "模糊", "box": [0.0, 0.0, 1.5, 0.5],
                   "severity": 0.9, "advice": "防抖"}]
    problems_c = [{"category": "other", "label": "无框", "severity": 0.2}]
    specs = [
        {"path": "a.jpg", "time": 5},
        {"path": "b.jpg", "time": 30},
        {"path": "c.jpg", "time": 60},
    ]
    with mock.patch.object(fd, "_resize_and_read_b64", return_value="QUJD"), \
         mock.patch.object(fd, "_call_diagnose", side_effect=[problems_a, problems_b, problems_c]), \
         mock.patch.object(fd, "DASHSCOPE_API_KEY", "test"), \
         mock.patch("engine.frame_diagnose.os.path.exists", return_value=True):
        result = fd.diagnose_frames(specs, work_dir="work")

    frames = result.get("frames", [])
    assert frames, "应有诊断结果"
    assert frames[0]["time"] == 30, "最严重(0.9)帧应排第一"
    assert len(frames) <= 3, "最多取 3 帧"
    b = next(f for f in frames if f["time"] == 30)
    assert b["problems"][0]["box"] is None, "越界坐标应被丢弃"
    # 直接测 _sanitize_problems：越界 severity 收敛、越界 box 丢弃
    cleaned = fd._sanitize_problems([{"severity": 1.7, "box": [0, 0, 2, 2]}])
    assert cleaned[0]["severity"] == 1.0, "severity 应收敛到 1.0"
    assert cleaned[0]["box"] is None, "越界 box 应被丢弃"
    return True


def test_frame_diagnose_graceful_degrade():
    """帧诊断失败 / 无 key / 无帧 → 返回空 dict，不抛异常"""
    from unittest import mock
    import engine.frame_diagnose as fd

    # 无 API key → 空
    with mock.patch.object(fd, "DASHSCOPE_API_KEY", ""):
        assert fd.diagnose_frames([{"path": "a.jpg", "time": 1}]) == {}
    # 空帧列表 → 空
    with mock.patch.object(fd, "DASHSCOPE_API_KEY", "test"):
        assert fd.diagnose_frames([]) == {}
    # VLM 全部失败 → 空
    with mock.patch.object(fd, "_resize_and_read_b64", return_value="QUJD"), \
         mock.patch.object(fd, "_call_diagnose", return_value=[]), \
         mock.patch.object(fd, "DASHSCOPE_API_KEY", "test"), \
         mock.patch("engine.frame_diagnose.os.path.exists", return_value=True):
        assert fd.diagnose_frames([{"path": "a.jpg", "time": 1}]) == {}
    return True


def test_build_plan_attaches_frames():
    """视频方案应携带帧点评 frames 字段"""
    import os
    import tempfile
    from unittest import mock
    from engine.advisor import ContentAdvisor

    fake_plan = {
        "diagnosis": {"summary": "诊断", "issues": [], "strengths": []},
        "script_rewrite": {"hook": "", "body": "", "proof": "", "cta": ""},
        "packaging": {"title": "", "cover_text": "", "description": ""},
        "conversion": {"pinned_comment": "", "profile_bio": "", "dm_opening": ""},
        "next_topics": [],
    }
    fake_frames = [{"index": 0, "time": 5, "image_b64": "x",
                    "problems": [{"category": "lighting", "label": "逆光", "box": None,
                                  "severity": 0.8, "advice": "补光"}]}]
    with tempfile.TemporaryDirectory() as tmp:
        v = os.path.join(tmp, "v.mp4"); open(v, "w").close()
        advisor = ContentAdvisor(work_dir="work")
        with mock.patch.object(ContentAdvisor, "_analyze_video",
                               return_value=("这是一段足够长的教学视频内容", {"topics": []}, fake_frames)), \
             mock.patch("engine.analyzer.ContentAnalyzer") as M:
            inst = M.return_value
            inst.generate_optimization_plan.return_value = fake_plan
            result = advisor.build_plan(video_path=v)
    assert result.get("frames") == fake_frames, "方案应携带帧点评"
    return True


def test_write_plan_markdown_frame_text_only():
    """markdown 含帧点评文字，但不内嵌 base64 图片"""
    import tempfile
    from engine.advisor import write_plan_markdown

    plan = {
        "diagnosis": {"summary": "s", "issues": [], "strengths": []},
        "script_rewrite": {"hook": "", "body": "", "proof": "", "cta": ""},
        "packaging": {"title": "", "cover_text": "", "description": ""},
        "conversion": {"pinned_comment": "", "profile_bio": "", "dm_opening": ""},
        "next_topics": [],
        "frames": [{"index": 0, "time": 75,
                    "image_b64": "QmFzZTY0SU1BR0U=",  # "Base64IMAGE"
                    "problems": [{"category": "lighting", "label": "逆光",
                                  "severity": 0.8, "advice": "补光", "box": [0, 0, 0.5, 0.5]}]}],
    }
    with tempfile.TemporaryDirectory() as tmp:
        out = write_plan_markdown(plan, f"{tmp}/plan.md")
        content = open(out, "r", encoding="utf-8").read()
    assert "⑥ 帧点评" in content, "markdown 应含帧点评标题"
    assert "逆光" in content, "markdown 应含问题文字"
    assert "01:15" in content, "markdown 应含帧时间（75s → 01:15）"
    assert "QmFzZTY0SU1BR0U=" not in content, "markdown 不应内嵌 base64 图片"
    return True


def test_detect_scenes_fallback_synthesize():
    """无场景切换视频：合成等分伪场景，保证关键帧/帧点评可用"""
    from engine.pipeline import Pipeline
    p = object.__new__(Pipeline)  # 绕过 __init__（不要求真实视频）
    p.video_duration = 90
    scenes = p._synthesize_scenes()
    assert len(scenes) == 4, "90s 视频应合成 4 段"
    assert scenes[0]["start"] == 0.0
    assert scenes[-1]["end"] == 90.0
    assert all(0 <= s["start"] < s["end"] <= 90 for s in scenes)
    # 短视频至少 1 段
    p.video_duration = 9
    assert len(p._synthesize_scenes()) == 1
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
