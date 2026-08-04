"""选题灵感模块验证脚本（v4 P3）

用法:
    py -3.12 tests/test_topics.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

TOPICS_PATH = ROOT / "knowledge" / "driving_exam_topics.json"


def green(s): return f"[PASS] {s}"
def red(s): return f"[FAIL] {s}"
def header(s): return f"\n{'='*60}\n  {s}\n{'='*60}"


def test_topics_library_schema():
    """精选选题库 schema 合法：每条含 id/title/description/category/tags/difficulty"""
    import json
    data = json.loads(TOPICS_PATH.read_text(encoding="utf-8"))
    topics = data.get("topics", [])
    assert len(topics) >= 10, f"选题应至少 10 条, 实际 {len(topics)}"
    ids = set()
    for t in topics:
        assert isinstance(t, dict), "选题应为对象"
        for field in ("id", "title", "description", "category", "tags", "difficulty"):
            assert field in t and t[field] not in ("", None), f"选题缺少字段 {field}"
        assert isinstance(t["tags"], list) and t["tags"], "tags 应为非空列表"
        assert t["id"] not in ids, f"重复 id: {t['id']}"
        ids.add(t["id"])
    return True


def test_industry_config_driving_exam():
    """行业配置：driving_exam 返回知识库与选题库路径"""
    from engine.industry_config import get_industry_config, supported_industries
    cfg = get_industry_config("driving_exam")
    assert cfg["id"] == "driving_exam"
    assert cfg["knowledge_path"].endswith("driving_exam.json"), "知识库路径错误"
    assert cfg["topics_path"].endswith("driving_exam_topics.json"), "选题库路径错误"
    assert "driving_exam" in supported_industries(), "supported_industries 缺 driving_exam"
    return True


def test_industry_config_unknown_falls_back():
    """未知行业回退到默认驾考配置"""
    from engine.industry_config import get_industry_config
    assert get_industry_config("not_exist")["id"] == "driving_exam"
    assert get_industry_config("")["id"] == "driving_exam"
    return True


def test_topics_prompt_injects_context():
    """选题 prompt 注入 城市/季节/热点/知识库"""
    from engine.analyzer import ContentAnalyzer
    a = ContentAnalyzer()
    prompt = a._build_topics_prompt(city="长沙", season="暑期", hot_topic="电子考官")
    for needle in ("长沙", "暑期", "电子考官", "倒车入库", "topics"):
        assert needle in prompt, f"prompt 缺少 {needle}"
    assert "5 条" in prompt, "prompt 应指定生成条数"
    return True


def test_validate_topics_fills_fields():
    """_validate_topics 补全字段、去除空白、过滤非法项"""
    from engine.analyzer import ContentAnalyzer
    a = ContentAnalyzer()
    raw = {
        "topics": [
            {"title": "标题", "why_now": "因为"},          # 缺 description/shooting_idea
            {"title": "  标题2  ", "description": " 说明 ", "why_now": " 理由 ", "shooting_idea": " 思路 "},
            "not-a-dict",                                  # 非法项应被过滤
        ]
    }
    out = a._validate_topics(raw)
    topics = out["topics"]
    assert len(topics) == 2, f"应过滤非法项, 实际 {len(topics)}"
    assert topics[0]["title"] == "标题"
    assert topics[0]["description"] == "", "缺失字段应补空串"
    assert topics[1]["title"] == "标题2", "应去除首尾空白"
    assert topics[1]["description"] == "说明"
    # 非 dict / 无 topics → 空列表
    assert a._validate_topics({"topics": "oops"})["topics"] == []
    assert a._validate_topics({})["topics"] == []
    return True


def test_generate_topics_uses_llm_and_validates():
    """generate_topics：mock LLM 返回 → 校验后透传；LLM 失败自动重试一次"""
    from unittest import mock
    from engine.analyzer import ContentAnalyzer
    a = ContentAnalyzer()

    llm_result = {
        "topics": [
            {"title": "T", "description": "D", "why_now": "W", "shooting_idea": "S"}
        ]
    }
    with mock.patch.object(a, "_call_llm", return_value=llm_result) as M:
        out = a.generate_topics(city="长沙")
        assert out["topics"][0]["title"] == "T", "成功路径应透传选题"
        M.assert_called_once()

    # LLM 首次失败 → 重试成功
    with mock.patch.object(a, "_call_llm", side_effect=[{"_error": "boom"}, llm_result]) as M:
        out = a.generate_topics()
        assert out["topics"][0]["title"] == "T"
        assert M.call_count == 2, "失败应重试一次"

    # 重试仍失败 → 返回错误交由上层
    with mock.patch.object(a, "_call_llm", return_value={"_error": "boom"}) as M:
        out = a.generate_topics()
        assert "_error" in out, "应返回错误交由上层"
    return True


def test_api_topics_returns_library():
    """GET /api/topics 返回精选选题库（秒开，零 LLM 成本）"""
    from web.app import app
    client = app.test_client()
    resp = client.get("/api/topics")
    assert resp.status_code == 200, f"状态码 {resp.status_code}"
    data = resp.get_json()
    assert len(data.get("topics", [])) >= 10, "选题库至少 10 条"
    return True


def test_api_topics_generate_flow():
    """POST /api/topics/generate → 后台线程产出 topics → status 透传；LLM 错误写 error"""
    from unittest import mock
    import web.app as app_mod

    fake = {"topics": [{"title": "T", "description": "D", "why_now": "W", "shooting_idea": "S"}]}
    app_mod._topics_status = {"running": True, "progress": "", "topics": None, "error": None}
    with mock.patch("engine.analyzer.ContentAnalyzer") as M:
        inst = M.return_value
        inst.generate_topics.return_value = fake
        app_mod._run_generate_topics({"city": "长沙", "season": "", "hot_topic": "",
                                      "industry": "driving_exam", "count": 5})
    assert app_mod._topics_status["topics"] == fake["topics"], "topics 未写入状态"
    assert app_mod._topics_status["running"] is False, "running 未复位"

    app_mod._topics_status = {"running": True, "progress": "", "topics": None, "error": None}
    with mock.patch("engine.analyzer.ContentAnalyzer") as M:
        inst = M.return_value
        inst.generate_topics.return_value = {"_error": "API key 失效"}
        app_mod._run_generate_topics({"city": "", "season": "", "hot_topic": "",
                                      "industry": "driving_exam", "count": 5})
    assert "key" in app_mod._topics_status["error"], "错误信息未写入"
    assert app_mod._topics_status["running"] is False
    return True


def test_api_topics_generate_rejects_when_busy():
    """生成进行中重复 POST → 409"""
    import web.app as app_mod
    app_mod._topics_status["running"] = True
    client = app_mod.app.test_client()
    resp = client.post("/api/topics/generate", json={"city": "长沙"})
    assert resp.status_code == 409, f"进行中应返回 409, 得到 {resp.status_code}"
    app_mod._topics_status["running"] = False
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
