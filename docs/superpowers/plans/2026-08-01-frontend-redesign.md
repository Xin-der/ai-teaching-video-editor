# 前端浅色商务风重构实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在功能与后端不变的前提下，把驾校内容优化工具前端重构为浅色商务风的单页 MVP 产品站（Hero → 三步 → 工具 → 历史方案 → 五块说明 → Footer），并新增本地历史记录功能。

**Architecture:** 纯静态前端，零框架零构建。`web/templates/optimize.html` 只保留页面骨架；全部样式进 `web/static/css/style.css`（设计 token + 组件）；全部交互进 `web/static/js/app.js`（真实调用 `/api/optimize` + `/api/optimize/status`，localStorage 存历史）。`web/app.py` 及 `engine/` 零改动。

**Tech Stack:** HTML5 / 原生 CSS（CSS 变量设计 token）/ 原生 JS（fetch + clipboard + localStorage）；Flask（仅托管，不修改）。

## Global Constraints

- 测试运行方式：`py -3.12 tests/test_frontend.py`（新）、`py -3.12 tests/test_advisor.py`（旧，必须保持 10/10）。
- **后端零改动**：`web/app.py`、`engine/`、`run.py` 一律不修改；只允许动 `web/templates/optimize.html`、`web/static/`、`tests/test_frontend.py`、文档。
- 页面必须保留文案 **"内容优化"** 与 **"生成方案"**（`tests/test_advisor.py` 的 `test_optimize_page_renders` 依赖）。
- 真实 API：`POST /api/optimize`（multipart 传视频 / JSON 传文字）、`GET /api/optimize/status`（轮询）。plan 结构：`diagnosis`/`script_rewrite`/`packaging`/`conversion` 为对象、`next_topics` 为 `[{title, why}]` 数组。
- 对象字段中文标签映射（显示与复制共用）：`summary→诊断, issues→问题, strengths→优点, hook→开头3秒, body→主体, proof→证明, cta→引导, title→标题, cover_text→封面文字, description→简介, pinned_comment→置顶评论, profile_bio→主页简介, dm_opening→私信开场白`。
- 历史记录：localStorage key `optimize_history`，数组新在前，上限 20 条，仅本机存储。
- 设计 token 色值以 spec 为准：`--bg:#F7F9FC --surface:#FFFFFF --border:#E5E7EB --text:#111827 --text-secondary:#4B5563 --text-muted:#9CA3AF --primary:#2563EB --primary-hover:#1D4ED8 --primary-soft:#EFF6FF --success:#16A34A --error:#DC2626`。
- 不引入网络字体；响应式到手机（触控目标 ≥44px）；`:focus-visible` 可见；尊重 `prefers-reduced-motion`。

### 文件结构

| 文件 | 职责 |
|------|------|
| `web/templates/optimize.html` | 页面骨架（导航/Hero/三步/工具/历史/五块说明/Footer/toast），引用 css/js |
| `web/static/css/style.css` | 设计 token + 全部组件样式 + 响应式 + 无障碍 |
| `web/static/js/app.js` | 全部交互：输入同步、生成、轮询、渲染 5 块、复制、toast、历史 |
| `tests/test_frontend.py` | 前端回归测试（Flask test client + 静态文件内容检查） |

### DOM 接口契约（HTML 与 JS 的约定，Task 1 定义、Task 3/4 消费）

固定元素 id：`#video-file`（file input）、`#dropzone`（上传区）、`#dropzone-empty`、`#file-name`、`#input-text`、`#city`、`#platform`、`#gen-btn`、`#progress`、`#progress-fill`、`#progress-text`、`#result`、`#toast`、`#history-list`。JS 侧常量：`BLOCKS`（5 块序号+标题）、`KEYS`（plan 字段名数组）、`LABELS`（字段中文映射）、`HISTORY_KEY='optimize_history'`、`HISTORY_MAX=20`；全局函数 `generate/pollStatus/renderPlan/copyBlock/fmtBlock/toast/esc/saveHistory/loadHistory/renderHistory/viewHistory/deleteHistory`。

---

### Task 1: 页面骨架 + 静态资源接线 + 页面测试

**Files:**
- Create: `tests/test_frontend.py`（含 5 个页面/后端测试）
- Create: `web/static/css/style.css`（占位：仅一行注释）
- Create: `web/static/js/app.js`（占位：仅一行注释）
- Rewrite: `web/templates/optimize.html`（完整骨架）

**Interfaces:**
- Produces: 上述 DOM id 契约；Flask 自动托管 `/static/css/style.css`、`/static/js/app.js`。

- [ ] **Step 1: 写失败测试 `tests/test_frontend.py`**

```python
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

- [ ] **Step 2: 运行测试，确认失败**

Run: `py -3.12 tests/test_frontend.py`
Expected: 5 个测试均失败（页面未引用静态资源 → 断言失败；static 404；空输入测试应通过，因后端未动——若其它全挂、空输入测试通过，符合预期）。

- [ ] **Step 3: 实现页面骨架**

创建 `web/static/css/style.css`：
```css
/* 设计系统见 Task 2 */
```

创建 `web/static/js/app.js`：
```js
/* 交互逻辑见 Task 3/4 */
```

重写 `web/templates/optimize.html`：
```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>驾校内容优化工具</title>
<link rel="stylesheet" href="/static/css/style.css">
</head>
<body>

<header class="site-header">
  <div class="container nav">
    <div class="brand"><span class="brand-emoji">🚗</span><span>驾校内容优化工具</span></div>
    <a class="btn btn-primary nav-cta" href="#tool">开始生成</a>
  </div>
</header>

<section class="hero">
  <div class="container">
    <p class="eyebrow">AI 同城获客工具</p>
    <h1>视频没人看？让 AI 把它改成能招生的内容</h1>
    <p class="hero-sub">上传教学视频或粘贴文案，3 分钟拿到 5 块内容优化方案——诊断、脚本改写、包装、转化话术、下期选题。照着改、照着发，抖音同城获客。</p>
    <div class="hero-actions">
      <a class="btn btn-primary" href="#tool">免费生成方案</a>
      <a class="btn btn-outline" href="#how">看看怎么用</a>
    </div>
  </div>
</section>

<section class="how" id="how">
  <div class="container">
    <h2 class="section-title">三步怎么用</h2>
    <div class="steps">
      <div class="step"><span class="step-num">①</span><h3>上传 / 粘贴</h3><p>教学视频或口述文案，二选一</p></div>
      <div class="step"><span class="step-num">②</span><h3>AI 生成方案</h3><p>3 分钟产出 5 块优化方案</p></div>
      <div class="step"><span class="step-num">③</span><h3>复制发布</h3><p>照抄到抖音，同城获客</p></div>
    </div>
  </div>
</section>

<section class="tool" id="tool">
  <div class="container">
    <h2 class="section-title">开始生成你的方案</h2>
    <div class="card">
      <h3 class="card-title">📤 输入内容</h3>
      <div id="dropzone" class="dropzone" tabindex="0">
        <input type="file" id="video-file" accept="video/*" hidden>
        <div id="dropzone-empty">
          <p class="dropzone-icon">📤</p>
          <p>点击选择教学视频</p>
          <p class="muted">原始素材或剪辑过均可，需有说话内容</p>
        </div>
        <div id="file-name" class="file-name" hidden></div>
      </div>
      <p class="or-divider">或</p>
      <label for="input-text">粘贴文字（脚本 / 简介 / 口述）</label>
      <textarea id="input-text" class="input" placeholder="把视频内容粘贴到这里，二选一"></textarea>
      <div class="row">
        <div><label for="city">所在城市（可选，用于同城关键词）</label><input type="text" id="city" class="input" placeholder="如：长沙"></div>
        <div><label for="platform">目标平台</label><select id="platform" class="input"><option value="douyin">抖音</option></select></div>
      </div>
      <button class="btn btn-primary btn-block" id="gen-btn">✨ 生成方案</button>
      <div class="progress" id="progress" hidden>
        <div class="progress-bar"><div class="progress-fill" id="progress-fill"></div></div>
        <div class="progress-text" id="progress-text">准备生成...</div>
      </div>
    </div>
    <div id="result"></div>
  </div>
</section>

<section class="history" id="history">
  <div class="container">
    <h2 class="section-title">历史方案</h2>
    <div class="card" id="history-list"></div>
  </div>
</section>

<section class="blocks" id="blocks">
  <div class="container">
    <h2 class="section-title">五块方案是什么</h2>
    <div class="blocks-grid">
      <div class="block"><h3>① 诊断</h3><p>你的视频为什么没人看——问题与优点</p></div>
      <div class="block"><h3>② 脚本改写</h3><p>开头 3 秒、主体、证明、引导怎么改</p></div>
      <div class="block"><h3>③ 包装</h3><p>标题、封面、简介怎么起</p></div>
      <div class="block"><h3>④ 转化话术</h3><p>置顶评论、主页简介、私信开场白</p></div>
      <div class="block"><h3>⑤ 下期选题</h3><p>下一期拍什么更容易获客</p></div>
    </div>
  </div>
</section>

<footer class="site-footer"><div class="container"><p class="muted">© 驾校内容优化工具 · 本地运行</p></div></footer>

<div class="toast" id="toast" hidden></div>

<script src="/static/js/app.js"></script>
</body>
</html>
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `py -3.12 tests/test_frontend.py`
Expected: 5 个测试全部通过（页面引用静态资源、静态文件 200、核心文案保留、空输入 400）。

- [ ] **Step 5: Commit**

```bash
git add tests/test_frontend.py web/templates/optimize.html web/static/css/style.css web/static/js/app.js
git commit -m "feat: 前端页面骨架 + 静态资源接线 + 回归测试

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 2: 设计系统 + 完整样式（style.css）

**Files:**
- Modify: `web/static/css/style.css`（占位 → 完整样式）
- Modify: `tests/test_frontend.py`（追加 token 测试）

**Interfaces:**
- Consumes: Task 1 的 HTML 骨架（class 名：`site-header/.nav/.brand/.hero/.eyebrow/.steps/.step/.tool/.card/.dropzone/.input/.row/.btn*/.progress*/#result 内 .field/.k/.v/.copy-row/.history-item/.block/.toast`）。
- Produces: 上述 class 的全部样式；`:focus-visible`、`prefers-reduced-motion`、移动端媒体查询。

- [ ] **Step 1: 追加失败测试**

在 `tests/test_frontend.py` 的 `test_optimize_api_empty_input_rejected` 之后插入：

```python
def test_css_has_design_tokens():
    css = CSS_PATH.read_text(encoding="utf-8")
    for token in ("--primary", "--bg", "--surface", "--text", "--border", "--success", "--error"):
        assert token in css, f"缺少 token {token}"
    return True
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `py -3.12 tests/test_frontend.py`
Expected: `test_css_has_design_tokens` 失败（占位 css 无 token）。

- [ ] **Step 3: 写完整 `web/static/css/style.css`**

```css
/* ===== 设计 Token ===== */
:root{
  --bg:#F7F9FC; --surface:#FFFFFF; --border:#E5E7EB;
  --text:#111827; --text-secondary:#4B5563; --text-muted:#9CA3AF;
  --primary:#2563EB; --primary-hover:#1D4ED8; --primary-soft:#EFF6FF;
  --success:#16A34A; --error:#DC2626;
  --radius:12px; --radius-lg:16px;
  --shadow-card:0 1px 3px rgba(0,0,0,.05), 0 4px 12px rgba(0,0,0,.04);
  --shadow-btn:0 2px 6px rgba(37,99,235,.30);
  --font:-apple-system,"PingFang SC","Microsoft YaHei","Segoe UI",system-ui,sans-serif;
  --content-max:880px;
}

/* ===== 基础 ===== */
*{ margin:0; padding:0; box-sizing:border-box; }
html{ scroll-behavior:smooth; }
body{ font-family:var(--font); background:var(--bg); color:var(--text); line-height:1.6; -webkit-font-smoothing:antialiased; }
.container{ max-width:var(--content-max); margin:0 auto; padding:0 24px; }
h1,h2,h3{ font-weight:600; }
a{ color:var(--primary); text-decoration:none; }
a:hover{ color:var(--primary-hover); }
.muted{ color:var(--text-muted); font-size:13px; }

/* ===== 头部 ===== */
.site-header{ position:sticky; top:0; z-index:100; background:rgba(255,255,255,.92); backdrop-filter:blur(8px); border-bottom:1px solid var(--border); }
.nav{ display:flex; align-items:center; justify-content:space-between; padding-top:14px; padding-bottom:14px; }
.brand{ display:flex; align-items:center; gap:8px; font-size:17px; font-weight:600; }
.brand-emoji{ font-size:20px; }
.nav-cta{ padding:8px 18px; font-size:14px; }

/* ===== Hero ===== */
.hero{ background:linear-gradient(180deg,#EEF4FF 0%,var(--bg) 100%); padding:80px 0 72px; text-align:center; }
.hero .eyebrow{ display:inline-block; color:var(--primary); background:var(--primary-soft); border-radius:999px; padding:4px 14px; font-size:13px; margin-bottom:20px; }
.hero h1{ font-size:32px; line-height:1.35; max-width:640px; margin:0 auto 16px; }
.hero-sub{ font-size:16px; color:var(--text-secondary); max-width:560px; margin:0 auto 28px; }
.hero-actions{ display:flex; gap:12px; justify-content:center; flex-wrap:wrap; }

/* ===== 区块标题 ===== */
.section-title{ font-size:20px; margin:48px 0 20px; }
.how{ padding-top:8px; }
.tool .section-title, .blocks .section-title, .history .section-title{ margin-top:0; }

/* ===== 按钮 ===== */
.btn{ display:inline-flex; align-items:center; justify-content:center; gap:6px; padding:10px 22px; border:none; border-radius:10px; font-family:var(--font); font-size:15px; font-weight:600; cursor:pointer; transition:background .15s, box-shadow .15s, transform .05s; }
.btn:active{ transform:translateY(1px); }
.btn-primary{ background:var(--primary); color:#fff; box-shadow:var(--shadow-btn); }
.btn-primary:hover{ background:var(--primary-hover); }
.btn-primary:disabled{ background:#CBD5E1; box-shadow:none; cursor:not-allowed; }
.btn-outline{ background:var(--surface); border:1px solid var(--border); color:var(--text); }
.btn-outline:hover{ border-color:var(--primary); color:var(--primary); }
.btn-block{ width:100%; margin-top:20px; padding:14px 20px; font-size:16px; }
.btn-sm{ padding:6px 14px; font-size:13px; border-radius:8px; }
.btn-danger:hover{ border-color:var(--error); color:var(--error); }

/* ===== 卡片 ===== */
.card{ background:var(--surface); border:1px solid var(--border); border-radius:var(--radius-lg); box-shadow:var(--shadow-card); padding:28px; margin-bottom:20px; }
.card-title{ font-size:16px; margin-bottom:14px; display:flex; align-items:center; gap:10px; }
.card-num{ display:inline-flex; align-items:center; justify-content:center; min-width:28px; height:28px; padding:0 6px; border-radius:8px; background:var(--primary-soft); color:var(--primary); font-size:14px; font-weight:600; }

/* ===== 表单 ===== */
label{ display:block; font-size:13px; color:var(--text-secondary); margin:16px 0 6px; }
.input{ width:100%; background:var(--surface); border:1px solid var(--border); border-radius:10px; padding:12px; color:var(--text); font-family:var(--font); font-size:14px; transition:border-color .15s, box-shadow .15s; }
.input:focus{ outline:none; border-color:var(--primary); box-shadow:0 0 0 3px rgba(37,99,235,.15); }
textarea.input{ min-height:110px; resize:vertical; }
.row{ display:flex; gap:16px; align-items:flex-end; }
.row > div{ flex:1; }
select.input{ cursor:pointer; }

.dropzone{ border:2px dashed var(--border); border-radius:var(--radius); background:var(--bg); padding:28px; text-align:center; cursor:pointer; transition:border-color .15s, background .15s; }
.dropzone:hover, .dropzone:focus-visible{ border-color:var(--primary); background:var(--primary-soft); outline:none; }
.dropzone-icon{ font-size:28px; margin-bottom:6px; }
.dropzone p{ color:var(--text-secondary); }
.file-name{ color:var(--primary); font-weight:600; }
.or-divider{ text-align:center; color:var(--text-muted); font-size:13px; margin:18px 0 0; }

/* ===== 进度 ===== */
.progress{ margin-top:16px; }
.progress-bar{ height:6px; border-radius:999px; background:var(--border); overflow:hidden; }
.progress-fill{ height:100%; width:40%; border-radius:999px; background:var(--primary); animation:indeterminate 1.2s ease-in-out infinite; }
@keyframes indeterminate{ 0%{ transform:translateX(-100%); } 100%{ transform:translateX(350%); } }
.progress-text{ font-size:13px; color:var(--text-secondary); margin-top:8px; }

/* ===== 结果字段 ===== */
.field{ display:flex; gap:10px; margin-bottom:8px; font-size:14px; }
.field .k{ flex-shrink:0; color:var(--text-secondary); min-width:72px; font-size:13px; padding-top:2px; }
.copy-row{ margin-top:14px; text-align:right; }

/* ===== 三步 ===== */
.steps{ display:grid; grid-template-columns:repeat(3,1fr); gap:20px; }
.step{ background:var(--surface); border:1px solid var(--border); border-radius:var(--radius-lg); padding:24px; }
.step-num{ color:var(--primary); font-weight:600; font-size:18px; }
.step h3{ margin:10px 0 6px; font-size:16px; }
.step p{ color:var(--text-secondary); font-size:14px; }

/* ===== 五块说明 ===== */
.blocks-grid{ display:grid; grid-template-columns:repeat(3,1fr); gap:16px; }
.block{ background:var(--surface); border:1px solid var(--border); border-radius:var(--radius); padding:20px; }
.block h3{ font-size:15px; margin-bottom:6px; }
.block p{ color:var(--text-secondary); font-size:13px; }

/* ===== 历史 ===== */
.history-item{ display:flex; align-items:center; gap:12px; padding:12px 0; border-bottom:1px solid var(--border); }
.history-item:last-child{ border-bottom:none; }
.history-time{ color:var(--text-muted); font-size:12px; flex-shrink:0; width:130px; }
.history-summary{ flex:1; font-size:14px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
.history-actions{ display:flex; gap:8px; flex-shrink:0; }

/* ===== Footer ===== */
.site-footer{ border-top:1px solid var(--border); margin-top:56px; padding:28px 0; text-align:center; }

/* ===== Toast ===== */
.toast{ position:fixed; right:24px; bottom:24px; z-index:300; background:var(--success); color:#fff; padding:12px 20px; border-radius:10px; font-size:14px; box-shadow:var(--shadow-card); animation:toast-in .2s ease-out; }
.toast.error{ background:var(--error); }
@keyframes toast-in{ from{ opacity:0; transform:translateY(8px); } to{ opacity:1; transform:none; } }

/* ===== 响应式 ===== */
@media (max-width:720px){
  .hero{ padding:56px 0 48px; }
  .hero h1{ font-size:24px; }
  .hero-sub{ font-size:15px; }
  .steps, .blocks-grid{ grid-template-columns:1fr; }
  .row{ flex-direction:column; align-items:stretch; }
  .row > div{ width:100%; }
  .history-item{ flex-wrap:wrap; }
  .history-time{ width:auto; }
  .nav-cta{ display:none; }
}

/* ===== 无障碍 ===== */
:focus-visible{ outline:2px solid var(--primary); outline-offset:2px; }
@media (prefers-reduced-motion: reduce){
  *{ animation:none !important; transition:none !important; }
  html{ scroll-behavior:auto; }
}
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `py -3.12 tests/test_frontend.py`
Expected: 6 个测试全部通过。

- [ ] **Step 5: 视觉抽检（可选，浏览器确认）**

Run: `py run.py --web`，打开 http://127.0.0.1:5000 ，目视检查 Hero/三步/工具卡/Footer 布局与配色（浅灰底、白卡、蓝主色、留白充分），缩窄窗口确认单列响应式。

- [ ] **Step 6: Commit**

```bash
git add web/static/css/style.css tests/test_frontend.py
git commit -m "feat: 前端设计系统与完整样式（浅色商务风）

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 3: JS 核心流程（生成 / 轮询 / 渲染 / 复制 / toast）

**Files:**
- Modify: `web/static/js/app.js`（占位 → 核心逻辑）
- Modify: `tests/test_frontend.py`（追加核心流程测试）

**Interfaces:**
- Consumes: Task 1 的 DOM id（`#gen-btn/#video-file/#dropzone/#input-text/#city/#platform/#progress/#progress-text/#result/#toast`）；真实 API `/api/optimize`、`/api/optimize/status`；`BLOCKS`/`LABELS` 常量。
- Produces: 全局函数 `generate/pollStatus/renderPlan/copyBlock/fmtBlock/toast/esc/showProgress/hideProgress/resetBtn`；`currentPlan` 变量。Task 4 复用 `renderPlan`、`toast` 与 `HISTORY_KEY` 常量。

- [ ] **Step 1: 追加失败测试**

在 `test_css_has_design_tokens` 之后插入：

```python
def test_app_js_core_flow():
    js = JS_PATH.read_text(encoding="utf-8")
    for needle in ("generate(", "pollStatus(", "renderPlan(", "copyBlock(", "toast(",
                   "/api/optimize", "/api/optimize/status"):
        assert needle in js, f"app.js 缺少 {needle}"
    return True
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `py -3.12 tests/test_frontend.py`
Expected: `test_app_js_core_flow` 失败（占位 app.js 无这些函数）。

- [ ] **Step 3: 写 `web/static/js/app.js` 核心逻辑**

```js
/* 驾校内容优化工具 · 前端交互 */
const BLOCKS = [
  ['①', '诊断'], ['②', '脚本改写'], ['③', '包装'], ['④', '转化话术'], ['⑤', '下期选题'],
];
const KEYS = ['diagnosis', 'script_rewrite', 'packaging', 'conversion', 'next_topics'];
const LABELS = {
  summary: '诊断', issues: '问题', strengths: '优点',
  hook: '开头3秒', body: '主体', proof: '证明', cta: '引导',
  title: '标题', cover_text: '封面文字', description: '简介',
  pinned_comment: '置顶评论', profile_bio: '主页简介', dm_opening: '私信开场白',
};
const HISTORY_KEY = 'optimize_history';
const HISTORY_MAX = 20;

let currentPlan = null;
let pollTimer = null;

function generate() {
  const file = document.getElementById('video-file').files[0];
  const text = document.getElementById('input-text').value.trim();
  const city = document.getElementById('city').value.trim();
  const platform = document.getElementById('platform').value;
  if (!file && !text) { toast('请选择视频或粘贴文字', true); return; }

  resetBtn(true);
  document.getElementById('result').innerHTML = '';
  showProgress('准备生成...');

  fetch('/api/optimize', {
    method: 'POST',
    body: file
      ? (() => { const fd = new FormData(); fd.append('video', file); fd.append('city', city); fd.append('platform', platform); return fd; })()
      : JSON.stringify({ text, city, platform }),
    headers: file ? {} : { 'Content-Type': 'application/json' },
  })
    .then(async res => {
      if (!res.ok) {
        const e = await res.json().catch(() => ({}));
        throw new Error(e.error || '提交失败');
      }
      pollStatus();
    })
    .catch(e => {
      toast(e.message, true);
      resetBtn();
      hideProgress();
    });
}

function pollStatus() {
  if (pollTimer) clearInterval(pollTimer);
  pollTimer = setInterval(async () => {
    try {
      const s = await (await fetch('/api/optimize/status')).json();
      if (s.progress) document.getElementById('progress-text').textContent = s.progress;
      if (s.error) {
        clearInterval(pollTimer);
        toast(s.error, true);
        resetBtn();
        hideProgress();
        return;
      }
      if (s.plan) {
        clearInterval(pollTimer);
        currentPlan = s.plan;
        saveHistory(s.plan);
        renderPlan(s.plan);
        resetBtn();
        hideProgress();
      }
    } catch (e) { console.error(e); }
  }, 1000);
}

function renderPlan(plan) {
  const box = document.getElementById('result');
  box.innerHTML = [
    planCard(0, plan.diagnosis, false),
    planCard(1, plan.script_rewrite, false),
    planCard(2, plan.packaging, false),
    planCard(3, plan.conversion, false),
    planCard(4, plan.next_topics, true),
  ].join('');
  box.scrollIntoView({ behavior: 'smooth' });
}

function planCard(idx, data, isTopics) {
  const [num, label] = BLOCKS[idx];
  const body = isTopics ? renderTopics(data) : renderObj(data);
  return `<div class="card"><h3 class="card-title"><span class="card-num">${num}</span>${label}</h3>${body}<div class="copy-row"><button class="btn btn-outline btn-sm" onclick="copyBlock(${idx})">📋 复制</button></div></div>`;
}

function renderObj(obj) {
  if (!obj || !Object.keys(obj).length) return '<p class="muted">（无）</p>';
  return Object.entries(obj).map(([k, v]) => {
    if (Array.isArray(v)) v = v.join('；');
    return `<p class="field"><span class="k">${esc(LABELS[k] || k)}</span><span class="v">${esc(String(v))}</span></p>`;
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
  if (Array.isArray(obj)) return obj.map(t => `${t.title || ''}：${t.why || ''}`).join('\n');
  if (!obj) return '';
  return Object.entries(obj).map(([k, v]) => {
    if (Array.isArray(v)) v = v.join('；');
    return `${LABELS[k] || k}：${v}`;
  }).join('\n');
}

function showProgress(msg) {
  document.getElementById('progress').hidden = false;
  document.getElementById('progress-text').textContent = msg || '准备生成...';
}
function hideProgress() { document.getElementById('progress').hidden = true; }
function resetBtn(disable) { document.getElementById('gen-btn').disabled = !!disable; }

function toast(msg, isError) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.toggle('error', !!isError);
  t.hidden = false;
  clearTimeout(t._timer);
  t._timer = setTimeout(() => { t.hidden = true; }, 2500);
}

function esc(s) { return (s || '').replace(/</g, '&lt;').replace(/>/g, '&gt;'); }

document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('gen-btn');
  const file = document.getElementById('video-file');
  const text = document.getElementById('input-text');
  const dz = document.getElementById('dropzone');

  const sync = () => { btn.disabled = !(file.files.length || text.value.trim()); };

  file.addEventListener('change', () => {
    if (file.files.length) {
      const f = file.files[0];
      document.getElementById('dropzone-empty').hidden = true;
      const nameEl = document.getElementById('file-name');
      nameEl.textContent = `🎬 ${f.name}（${(f.size / 1024 / 1024).toFixed(1)} MB）`;
      nameEl.hidden = false;
    } else {
      document.getElementById('dropzone-empty').hidden = false;
      document.getElementById('file-name').hidden = true;
    }
    sync();
  });

  text.addEventListener('input', sync);
  dz.addEventListener('click', () => file.click());
  dz.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); file.click(); }
  });
  btn.addEventListener('click', generate);
  sync();
});
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `py -3.12 tests/test_frontend.py`
Expected: 7 个测试全部通过。

- [ ] **Step 5: 真实调用验证（后端不被架空）**

Run: `py -3.12 -c "import web.app as m; m._optimize_status={'running':True,'progress':'','plan':None,'error':None,'markdown_path':None}; m._run_optimize({'text':'教练说倒车入库一定要看点位，不然会压线。学员老是方向盘打晚。','city':'长沙','platform':'douyin'}); import json; print(json.dumps(m._optimize_status, ensure_ascii=False)[:500])"`
Expected: 打印出含 `plan` 且无 `error` 的 JSON（真实调用 LLM，耗时约数秒~1 分钟；需 `.env` 中 `DASHSCOPE_API_KEY` 已配置）。若网络/Key 不可用，跳过本步并记录原因，不阻塞后续。

- [ ] **Step 6: Commit**

```bash
git add web/static/js/app.js tests/test_frontend.py
git commit -m "feat: 前端核心交互（生成/轮询/渲染/复制）

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 4: JS 历史记录（localStorage）

**Files:**
- Modify: `web/static/js/app.js`（追加历史逻辑 + init 中调用 `renderHistory`）
- Modify: `tests/test_frontend.py`（追加历史测试）

**Interfaces:**
- Consumes: Task 3 的 `renderPlan`、`toast`、`esc`、`HISTORY_KEY`、`HISTORY_MAX`；HTML 的 `#history-list`。
- Produces: `saveHistory(plan)` / `loadHistory()` / `renderHistory()` / `viewHistory(i)` / `deleteHistory(i)`。

- [ ] **Step 1: 追加失败测试**

在 `test_app_js_core_flow` 之后插入：

```python
def test_app_js_history():
    js = JS_PATH.read_text(encoding="utf-8")
    for needle in ("optimize_history", "localStorage", "renderHistory", "viewHistory", "deleteHistory"):
        assert needle in js, f"app.js 缺少 {needle}"
    return True
```

- [ ] **Step 2: 运行测试，确认失败**

Run: `py -3.12 tests/test_frontend.py`
Expected: `test_app_js_history` 失败。

- [ ] **Step 3: 在 `web/static/js/app.js` 追加历史逻辑**

在 `function esc` 定义之后、`document.addEventListener('DOMContentLoaded'` 之前插入：

```js
function loadHistory() {
  try { return JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]'); }
  catch (e) { return []; }
}

function saveHistory(plan) {
  const list = loadHistory();
  list.unshift({ ts: Date.now(), plan });
  if (list.length > HISTORY_MAX) list.length = HISTORY_MAX;
  localStorage.setItem(HISTORY_KEY, JSON.stringify(list));
  renderHistory();
}

function renderHistory() {
  const list = loadHistory();
  const box = document.getElementById('history-list');
  if (!box) return;
  if (!list.length) { box.innerHTML = '<p class="muted">还没有历史方案，生成一份试试。</p>'; return; }
  box.innerHTML = list.map((item, i) => {
    const d = new Date(item.ts);
    const pad = n => String(n).padStart(2, '0');
    const time = `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
    const summary = (item.plan.diagnosis && item.plan.diagnosis.summary) || '（方案）';
    return `<div class="history-item">
      <span class="history-time">${time}</span>
      <span class="history-summary">${esc(summary)}</span>
      <span class="history-actions">
        <button class="btn btn-outline btn-sm" onclick="viewHistory(${i})">查看</button>
        <button class="btn btn-outline btn-sm btn-danger" onclick="deleteHistory(${i})">删除</button>
      </span>
    </div>`;
  }).join('');
}

function viewHistory(i) {
  const list = loadHistory();
  const item = list[i];
  if (!item) return;
  currentPlan = item.plan;
  renderPlan(item.plan);
}

function deleteHistory(i) {
  const list = loadHistory();
  list.splice(i, 1);
  localStorage.setItem(HISTORY_KEY, JSON.stringify(list));
  renderHistory();
}
```

并在 `document.addEventListener('DOMContentLoaded', () => {` 回调末尾（`sync();` 之后）追加一行：

```js
  renderHistory();
```

- [ ] **Step 4: 运行测试，确认通过**

Run: `py -3.12 tests/test_frontend.py`
Expected: 8 个测试全部通过。

- [ ] **Step 5: Commit**

```bash
git add web/static/js/app.js tests/test_frontend.py
git commit -m "feat: 前端历史方案（localStorage 本地保存/回看/删除）

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

### Task 5: 集成验证 + 文档收尾

**Files:**
- Verify: 全部前端文件；后端测试
- Modify: `PROGRESS.md`（记录前端重构完成）

**Interfaces:**
- Consumes: Task 1-4 的全部产物。

- [ ] **Step 1: 后端回归**

Run: `py -3.12 tests/test_advisor.py`
Expected: `10/10 通过`（后端零改动）。

- [ ] **Step 2: 前端回归**

Run: `py -3.12 tests/test_frontend.py`
Expected: `8/8 通过`。

- [ ] **Step 3: 真实端到端（HTTP）**

Run（后台起服务，前台 curl 验证）：
```bash
cd "D:/ai video/ai-teaching-video-editor"
py -3.12 -c "from web.app import app; app.run(port=5055)" &
sleep 4
curl -s http://127.0.0.1:5055/ | grep -o "驾校内容优化工具" | head -1
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5055/static/css/style.css
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:5055/static/js/app.js
curl -s -X POST http://127.0.0.1:5055/api/optimize -H "Content-Type: application/json" -d '{"text":"教练说倒车入库一定要看点位","city":"长沙","platform":"douyin"}'
kill %1
```
Expected: 首页含品牌文案、css/js 均 200、POST 返回 `{"status":"started"}`。

- [ ] **Step 4: 更新 `PROGRESS.md`**

在"v3（当前）"一节下方追加：
```markdown
### v3.1 前端重构（浅色商务风 MVP 产品站）
- 2026-08-01 前端从暗色单页工具重构为浅色商务风单页产品站（Hero/三步/工具/五块说明/Footer）
- 样式与逻辑拆分至 `web/static/css/style.css` + `web/static/js/app.js`，`web/app.py` 零改动
- 新增本地历史方案（localStorage，最多 20 条）
- `tests/test_frontend.py` 8 项回归通过；`tests/test_advisor.py` 仍 10/10
```

- [ ] **Step 5: Commit**

```bash
git add PROGRESS.md
git commit -m "docs: 记录前端浅色商务风重构（v3.1）

Co-Authored-By: Claude <noreply@anthropic.com>"
```

---

## Self-Review

- **Spec 覆盖**：颜色 token（Task 2 ✓）、排版/留白/圆角/阴影（Task 2 ✓）、页面结构 Hero/三步/工具/历史/五块说明/Footer（Task 1 ✓）、中文标签渲染（Task 3 ✓）、复制+toast（Task 3 ✓）、历史记录 localStorage（Task 4 ✓）、移动端/焦点/reduced-motion（Task 2 ✓）、后端零改动+真实 API（Task 3 Step 5 / Task 5 ✓）、验收标准（Task 5 ✓）。
- **占位符扫描**：各代码步骤均有完整实现代码，无 TODO/TBD。
- **类型/命名一致性**：DOM id 契约在 Task 1 定义、Task 3/4 消费一致；`BLOCKS/LABELS/HISTORY_KEY/HISTORY_MAX` 常量在 Task 3 定义、Task 4 复用一致；函数名 `generate/pollStatus/renderPlan/copyBlock/fmtBlock/toast/esc/saveHistory/loadHistory/renderHistory/viewHistory/deleteHistory` 在测试断言与实现中一致。
