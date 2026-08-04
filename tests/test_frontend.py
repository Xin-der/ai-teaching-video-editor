"""前端页面结构 / 静态资源 / 设计约束验证脚本

用法:
    py -3.12 tests/test_frontend.py
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

CSS_PATH = ROOT / "web" / "static" / "css" / "style.css"
JS_PATH = ROOT / "web" / "static" / "js" / "app.js"


def green(s): return f"[PASS] {s}"
def red(s): return f"[FAIL] {s}"
def header(s): return f"\n{'='*60}\n  {s}\n{'='*60}"


def test_page_links_static_assets():
    from web.app import app
    client = app.test_client()
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "/static/css/style.css" in body, "页面未引用 style.css"
    assert "/static/js/app.js" in body, "页面未引用 app.js"
    return True


def test_static_css_served():
    from web.app import app
    client = app.test_client()
    resp = client.get("/static/css/style.css")
    assert resp.status_code == 200, f"style.css 状态码 {resp.status_code}"
    assert "text/css" in resp.content_type
    return True


def test_static_js_served():
    from web.app import app
    client = app.test_client()
    resp = client.get("/static/js/app.js")
    assert resp.status_code == 200, f"app.js 状态码 {resp.status_code}"
    assert "javascript" in resp.content_type
    return True


def test_page_keeps_core_copy():
    """旧测试依赖的文案必须保留：'内容优化' 与 '生成方案'"""
    from web.app import app
    client = app.test_client()
    body = client.get("/").get_data(as_text=True)
    assert "内容优化" in body
    assert "生成方案" in body
    return True


def test_optimize_api_empty_input_rejected():
    """后端未改动：空文字输入仍返回 400"""
    from web.app import app
    client = app.test_client()
    resp = client.post("/api/optimize", json={"text": ""})
    assert resp.status_code == 400, f"空输入应返回 400, 得到 {resp.status_code}"
    return True


def test_css_has_design_tokens():
    css = CSS_PATH.read_text(encoding="utf-8")
    for token in ("--ink", "--accent", "--line", "--paper", "--maxw", "--success", "--error"):
        assert token in css, f"缺少 token {token}"
    return True


def test_app_js_core_flow():
    js = JS_PATH.read_text(encoding="utf-8")
    for needle in ("generate(", "pollStatus(", "renderPlan(", "copyBlock(", "toast(",
                   "/api/optimize", "/api/optimize/status"):
        assert needle in js, f"app.js 缺少 {needle}"
    return True


def test_app_js_history():
    js = JS_PATH.read_text(encoding="utf-8")
    for needle in ("optimize_history", "localStorage", "renderHistory", "viewHistory", "deleteHistory"):
        assert needle in js, f"app.js 缺少 {needle}"
    return True


def test_page_has_editorial_sections():
    """营销前置结构：五块/三步/对比/工具/CTA 五个锚点区块"""
    from web.app import app
    client = app.test_client()
    body = client.get("/").get_data(as_text=True)
    for anchor in ('id="blocks"', 'id="steps"', 'id="compare"', 'id="tool"', 'id="cta"'):
        assert anchor in body, f"缺少区块 {anchor}"
    return True


def test_page_has_tool_tabs():
    """工具区双 Tab：optimize 与 topics 两个面板"""
    from web.app import app
    client = app.test_client()
    body = client.get("/").get_data(as_text=True)
    for needle in ('data-tab="optimize"', 'data-tab="topics"', 'id="panel-optimize"', 'id="panel-topics"'):
        assert needle in body, f"缺少 {needle}"
    return True


def test_app_js_tab_switch():
    js = JS_PATH.read_text(encoding="utf-8")
    for needle in ("switchTab(", "data-tab", "classList.toggle"):
        assert needle in js, f"app.js 缺少 {needle}"
    return True


def test_page_has_topics_panel_content():
    """Tab2 选题面板包含 精选选题库 / AI 生成更多 与关键控件"""
    from web.app import app
    client = app.test_client()
    body = client.get("/").get_data(as_text=True)
    for needle in ("精选选题库", "AI 生成更多", 'id="topic-list"', 'id="topic-city"',
                   'id="topic-season"', 'id="topic-hot"', 'id="gen-topics-btn"', 'id="topics-result"'):
        assert needle in body, f"缺少 {needle}"
    return True


def test_app_js_topics_flow():
    js = JS_PATH.read_text(encoding="utf-8")
    for needle in ("loadTopics(", "renderTopicList(", "generateTopics(", "pollTopicsStatus(",
                   "copyTopic(", "copyGeneratedTopic(", "/api/topics"):
        assert needle in js, f"app.js 缺少 {needle}"
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
