# P1 UI 重设计（编辑风 · 营销前置）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将前端从浅蓝卡片风重构为极简编辑风（墨黑 + 暖橙 + 发丝边框）营销前置单页，核心工具区双 Tab 可直接使用。

**Architecture:** 纯静态前端改造，后端零改动。`web/templates/optimize.html` 重写为营销前置结构（Nav → Hero → 五块 → 三步 → 对比 → 工具区 → CTA → Footer）；`web/static/css/style.css` 整体重写 token 与组件；`web/static/js/app.js` 保留核心逻辑并新增 Tab 切换与编辑风结果渲染；`tests/test_frontend.py` 更新设计约束并新增结构断言。

**Tech Stack:** 原生 HTML/CSS/JS（零构建、零依赖）；Flask 后端（不变）；Python 3.12 脚本式单测。

## Global Constraints

- 后端 `web/app.py` **零改动**（`test_optimize_api_empty_input_rejected` 保证空输入仍返回 400）
- 页面必须包含文案 **`内容优化`**（品牌名）与 **`生成方案`**（生成按钮）
- `app.js` 必须保留核心函数名：`generate`/`pollStatus`/`renderPlan`/`copyBlock`/`toast`/`renderHistory`/`viewHistory`/`deleteHistory`
- 设计语言：墨黑 `--ink` + 暖橙 `--accent` + 发丝边框 + 编辑排版 + 胶囊按钮 + 滚动渐显（尊重 `prefers-reduced-motion`）；**无卡片、无阴影**
- 工具区双 Tab：`optimize` / `topics`；Tab2 本期为占位（P3 选题功能填充）
- 参考文件：`example_html/index-min.html`（设计语言来源）
- 提交消息末尾**不加** `Co-Authored-By: Claude`
- 运行命令：`py -3.12 tests/test_frontend.py`（脚本风格，全部 PASS 且退出码 0）

---

### Task 1: 更新前端回归测试（RED）

先改测试，建立新设计约束；此刻旧 HTML/CSS/JS 必然失败。

**Files:**
- Modify: `tests/test_frontend.py`

**Interfaces:**
- Produces: 新的测试断言（Task 2/3/4 必须满足才能转绿）

- [ ] **Step 1: 替换 `test_css_has_design_tokens` 为新 token 集合**

```python
def test_css_has_design_tokens():
    css = CSS_PATH.read_text(encoding="utf-8")
    for token in ("--ink", "--accent", "--line", "--paper", "--maxw", "--success", "--error"):
        assert token in css, f"缺少 token {token}"
    return True
```

- [ ] **Step 2: 新增三个测试函数**（插入到 `test_app_js_history` 之后）

```python
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
```

- [ ] **Step 3: 运行测试确认失败（RED）**

Run: `py -3.12 tests/test_frontend.py`
Expected: 至少 `test_css_has_design_tokens`、`test_page_has_editorial_sections`、`test_page_has_tool_tabs`、`test_app_js_tab_switch` FAIL（旧文件无新 token / 无 `compare` 区块 / 无 Tab / 无 `switchTab`）。其余旧断言因文件未动仍 PASS。

- [ ] **Step 4: 提交测试先行**

```bash
git add tests/test_frontend.py
git commit -m "test: 前端回归测试升级——新编辑风 token + 营销前置结构 + 双 Tab 断言"
```

---

### Task 2: 重写页面骨架 `optimize.html`

营销前置结构（照 `example_html/index-min.html` 段落顺序），工具区带双 Tab。

**Files:**
- Rewrite: `web/templates/optimize.html`

**Interfaces:**
- Consumes: 无（独立）
- Produces: 满足 Task 1 的 `test_page_has_editorial_sections`、`test_page_has_tool_tabs`、`test_page_links_static_assets`、`test_page_keeps_core_copy`

- [ ] **Step 1: 整文件重写为以下内容**

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

<nav class="nav">
  <div class="nav-inner">
    <a class="logo" href="#tool"><span class="logo-dot"></span>驾校内容优化工具</a>
    <div class="nav-links">
      <a href="#blocks">功能</a>
      <a href="#steps">流程</a>
      <a href="#tool">选题</a>
    </div>
    <a class="nav-cta" href="#tool">开始使用</a>
  </div>
</nav>

<header class="hero">
  <div class="wrap">
    <div class="hero-inner">
      <div class="eyebrow">驾校内容，重新设计</div>
      <h1>让每条视频，<br>都带来 <em class="em">学员</em>。</h1>
      <p class="lede">上传教练的拍摄素材或口播文字，AI 五分钟生成一整套内容优化方案——从诊断到选题，照着改，照着发。</p>
      <div class="hero-actions">
        <a class="btn btn-primary" href="#tool">立即体验</a>
        <a class="btn btn-text" href="#blocks">了解它如何工作
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M5 12h14"/><path d="M13 6l6 6-6 6"/></svg>
        </a>
      </div>
    </div>
    <div class="meta-strip">
      <div class="meta-item"><div class="mv">5 块</div><div class="ml">完整优化方案</div></div>
      <div class="meta-item"><div class="mv">3 分钟</div><div class="ml">快速出稿</div></div>
      <div class="meta-item"><div class="mv">0 上传</div><div class="ml">原片不出本机</div></div>
      <div class="meta-item"><div class="mv">同城</div><div class="ml">精准获客</div></div>
    </div>
  </div>
</header>

<section id="blocks">
  <div class="wrap">
    <div class="sec-head reveal">
      <div class="sec-tag">功能</div>
      <h2>一套方案，五块拼图。</h2>
      <p>不是一段文案，是一整套能照着做的优化方案。每一块都解决一个具体问题。</p>
    </div>
    <div class="blocks">
      <div class="block reveal">
        <div class="block-num">01</div>
        <div class="block-body"><h3>内容诊断</h3><p class="desc">AI 看完素材，告诉你哪里不行——而不是夸哪里好。</p></div>
        <div class="block-example">开头 3 秒未点题，学员抓不住痛点；缺同城标签，流量难以本地化。</div>
      </div>
      <div class="block reveal">
        <div class="block-num">02</div>
        <div class="block-body"><h3>脚本改写</h3><p class="desc">把原话术重写成爆款结构，保留你的表达，重构节奏。</p></div>
        <div class="block-example"><span class="tag">【痛点】</span>科二挂科 3 次？<span class="tag">【方法】</span>这个点位记住…<span class="tag">【钩子】</span>关注看下期。</div>
      </div>
      <div class="block reveal">
        <div class="block-num">03</div>
        <div class="block-body"><h3>标题包装</h3><p class="desc">标题、封面文案、标签一次配齐，为同城流量而设计。</p></div>
        <div class="block-example">「深圳科二倒车入库，3 秒教会你」｜封面：点位示意｜#深圳驾校 #科二</div>
      </div>
      <div class="block reveal">
        <div class="block-num">04</div>
        <div class="block-body"><h3>转化话术</h3><p class="desc">评论区、私信、引导加微——把流量变成咨询。</p></div>
        <div class="block-example">评论区置顶：深圳想学车的滴滴，科二科三一对一带练。</div>
      </div>
      <div class="block reveal">
        <div class="block-num">05</div>
        <div class="block-body"><h3>下期选题</h3><p class="desc">基于本条数据，告诉你下一条该拍什么。</p></div>
        <div class="block-example">「科三路考常挂的 3 个细节」「深圳考场实地走线」</div>
      </div>
    </div>
  </div>
</section>

<section id="steps">
  <div class="wrap">
    <div class="sec-head reveal">
      <div class="sec-tag">流程</div>
      <h2>三步开始。</h2>
      <p>不需要学剪辑，不需要懂运营。上传，等待，发布。</p>
    </div>
    <div class="steps reveal">
      <div class="step"><div class="sn">01</div><h4>上传素材</h4><p>视频片段或口播文字，原片不出本机。</p></div>
      <div class="step"><div class="sn">02</div><h4>AI 生成方案</h4><p>五分钟，五块完整优化方案。</p></div>
      <div class="step"><div class="sn">03</div><h4>照着改，照着发</h4><p>同城标签 + 转化话术，精准引流。</p></div>
    </div>
  </div>
</section>

<section id="compare">
  <div class="wrap">
    <div class="sec-head reveal">
      <div class="sec-tag">对比</div>
      <h2>改之前。改之后。</h2>
      <p>同样的素材，不同的结果。</p>
    </div>
    <div class="compare reveal">
      <div class="compare-col before">
        <div class="clabel">改之前</div>
        <ul><li>随手拍，流水账</li><li>没标题，没标签</li><li>评论区无人引导</li><li class="final">同城 0 获客</li></ul>
      </div>
      <div class="compare-col after">
        <div class="clabel">改之后</div>
        <ul><li>痛点开场，3 秒抓人</li><li>同城标签 + 封面文案</li><li>话术引导加微</li><li class="final">同城私信不断</li></ul>
      </div>
    </div>
  </div>
</section>

<section class="tool" id="tool">
  <div class="wrap">
    <div class="sec-head reveal">
      <div class="sec-tag">工具</div>
      <h2>生成你的方案。</h2>
      <p>选视频或贴文字，AI 帮你改。原片不出本机。</p>
    </div>

    <div class="tool-tabs reveal" role="tablist">
      <button class="tool-tab active" id="tab-optimize" data-tab="optimize" role="tab" aria-controls="panel-optimize" aria-selected="true">优化视频</button>
      <button class="tool-tab" id="tab-topics" data-tab="topics" role="tab" aria-controls="panel-topics" aria-selected="false">选题灵感</button>
    </div>

    <div class="tool-panel" id="panel-optimize" role="tabpanel" aria-labelledby="tab-optimize">
      <div id="dropzone" class="dropzone" tabindex="0">
        <input type="file" id="video-file" accept="video/*" hidden>
        <div id="dropzone-empty">
          <p class="dropzone-title">点击选择教学视频</p>
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
      <button class="btn btn-primary btn-block" id="gen-btn">生成方案</button>
      <div class="progress" id="progress" hidden>
        <div class="progress-bar"><div class="progress-fill" id="progress-fill"></div></div>
        <div class="progress-text" id="progress-text">准备生成...</div>
      </div>
      <div id="result"></div>
    </div>

    <div class="tool-panel" id="panel-topics" role="tabpanel" aria-labelledby="tab-topics" hidden>
      <p class="muted">选题灵感正在准备中——之后这里会给你当季该拍的选题。</p>
    </div>

    <div class="history" id="history">
      <div class="history-head"><span class="sec-tag">历史</span><h3>历史方案</h3></div>
      <div id="history-list"></div>
    </div>
  </div>
</section>

<section class="cta" id="cta">
  <div class="wrap">
    <h2>让 AI 帮你<br>写 <em class="em">第一条</em>。</h2>
    <p>免费试用，三分钟看到第一份方案。</p>
    <a class="btn btn-primary" href="#tool">开始使用</a>
  </div>
</section>

<footer>
  <div class="wrap foot-inner">
    <span class="copy">© 2026 驾校内容优化工具 · 本地运行</span>
    <div class="foot-links"><a href="#tool">开始使用</a></div>
  </div>
</footer>

<div class="toast" id="toast" hidden></div>

<script src="/static/js/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: 运行结构类测试确认转绿**

Run: `py -3.12 tests/test_frontend.py`
Expected: `test_page_links_static_assets`、`test_page_keeps_core_copy`、`test_page_has_editorial_sections`、`test_page_has_tool_tabs` PASS；CSS/JS 相关测试仍 FAIL（Task 3/4 解决）。

- [ ] **Step 3: 提交**

```bash
git add web/templates/optimize.html
git commit -m "feat: 页面骨架重写为编辑风营销前置结构（Nav/Hero/五块/三步/对比/双Tab工具区/CTA）"
```

---

### Task 3: 重写设计系统 `style.css`

编辑风 token 与全部组件（照参考 `example_html/index-min.html` 语言，扩展工具区样式）。

**Files:**
- Rewrite: `web/static/css/style.css`

**Interfaces:**
- Consumes: Task 2 的 HTML 结构（class 名需一一对应）
- Produces: 满足 `test_css_has_design_tokens`；给 Task 4 结果渲染提供 `.block` 编辑编号行样式

- [ ] **Step 1: 整文件重写为以下内容**

```css
/* ===== 设计 Token（编辑风：墨黑 + 暖橙 + 发丝边框） ===== */
:root{
  --ink:oklch(20% 0.004 264);
  --ink-2:oklch(45% 0.004 264);
  --ink-3:oklch(62% 0.004 264);
  --ink-4:oklch(75% 0.004 264);
  --line:oklch(90% 0.003 264);
  --line-2:oklch(94% 0.002 264);
  --paper:oklch(99% 0 0);
  --paper-2:oklch(97% 0.001 264);
  --accent:oklch(55% 0.18 25);
  --accent-soft:oklch(96% 0.03 25);
  --success:oklch(55% 0.15 150);
  --error:oklch(55% 0.2 25);
  --maxw:1080px;
  --font:-apple-system,BlinkMacSystemFont,"SF Pro Display","SF Pro Text","Helvetica Neue","PingFang SC","Microsoft YaHei",system-ui,sans-serif;
}
*{box-sizing:border-box;margin:0;padding:0}
html{scroll-behavior:smooth;-webkit-font-smoothing:antialiased;-moz-osx-font-smoothing:grayscale}
body{font-family:var(--font);background:var(--paper);color:var(--ink);line-height:1.5;font-size:16px;letter-spacing:-0.003em}
a{color:inherit;text-decoration:none}
.wrap{max-width:var(--maxw);margin:0 auto;padding:0 28px}
.muted{color:var(--ink-3);font-size:14px}
.sec-tag{font-size:13px;color:var(--accent);font-weight:500;letter-spacing:0.04em;margin-bottom:20px;text-transform:uppercase}
h1,h2,h3,h4{font-weight:600}

/* ===== 导航 ===== */
.nav{position:sticky;top:0;z-index:50;background:rgba(255,255,255,0.85);backdrop-filter:saturate(180%) blur(20px);-webkit-backdrop-filter:saturate(180%) blur(20px);border-bottom:1px solid var(--line-2)}
.nav-inner{max-width:var(--maxw);margin:0 auto;padding:0 28px;height:56px;display:flex;align-items:center;justify-content:space-between}
.logo{display:flex;align-items:center;gap:10px;font-size:15px;font-weight:500;letter-spacing:-0.01em}
.logo-dot{width:9px;height:9px;border-radius:2px;background:var(--accent)}
.nav-links{display:flex;gap:32px;font-size:14px;color:var(--ink-2)}
.nav-links a{transition:color .2s}
.nav-links a:hover{color:var(--ink)}
.nav-cta{font-size:14px;font-weight:500;color:var(--paper);background:var(--ink);padding:8px 18px;border-radius:980px;transition:background .2s}
.nav-cta:hover{background:var(--accent)}

/* ===== 按钮（胶囊） ===== */
.btn{display:inline-flex;align-items:center;gap:6px;font-size:16px;font-weight:500;padding:13px 26px;border-radius:980px;cursor:pointer;border:none;transition:all .25s cubic-bezier(.2,.7,.3,1)}
.btn-primary{background:var(--ink);color:var(--paper)}
.btn-primary:hover{background:var(--accent)}
.btn-primary:disabled{background:var(--ink-4);cursor:not-allowed}
.btn-text{background:transparent;color:var(--ink-2);padding:13px 6px}
.btn-text:hover{color:var(--ink)}
.btn-text svg{transition:transform .25s}
.btn-text:hover svg{transform:translateX(3px)}
.btn-block{width:100%;justify-content:center;margin-top:24px}
.btn-sm{padding:9px 18px;font-size:14px}

/* ===== Hero ===== */
.hero{padding:120px 0 90px;border-bottom:1px solid var(--line-2)}
.hero-inner{max-width:780px}
.eyebrow{font-size:13px;color:var(--accent);font-weight:500;letter-spacing:0.02em;margin-bottom:28px;display:flex;align-items:center;gap:8px}
.eyebrow::before{content:"";width:24px;height:1px;background:var(--accent)}
.hero h1{font-size:clamp(44px,7vw,76px);font-weight:600;line-height:1.04;letter-spacing:-0.04em;margin-bottom:28px}
.hero h1 .em{color:var(--accent);font-style:normal}
.hero .lede{font-size:clamp(19px,2vw,23px);color:var(--ink-2);font-weight:400;line-height:1.5;max-width:560px;margin-bottom:40px;letter-spacing:-0.012em}
.hero-actions{display:flex;gap:8px;align-items:center;flex-wrap:wrap}
.meta-strip{display:flex;gap:48px;margin-top:72px;padding-top:32px;border-top:1px solid var(--line-2)}
.meta-item .mv{font-size:32px;font-weight:600;letter-spacing:-0.025em;line-height:1}
.meta-item .ml{font-size:13px;color:var(--ink-3);margin-top:8px;letter-spacing:0.01em}

/* ===== 区块 ===== */
section{padding:120px 0;border-bottom:1px solid var(--line-2)}
.sec-head{margin-bottom:80px;max-width:680px}
.sec-head h2{font-size:clamp(32px,4.6vw,52px);font-weight:600;letter-spacing:-0.035em;line-height:1.08;margin-bottom:20px}
.sec-head p{font-size:clamp(17px,1.7vw,20px);color:var(--ink-2);line-height:1.5}

/* ===== 五块（编辑编号块） ===== */
.blocks{border-top:1px solid var(--line)}
.block{display:grid;grid-template-columns:80px 1fr 1.1fr;gap:40px;padding:56px 0;border-bottom:1px solid var(--line);align-items:start}
.block-num{font-size:13px;font-weight:500;color:var(--ink-3);letter-spacing:0.06em;padding-top:8px;font-variant-numeric:tabular-nums}
.block-body h3{font-size:26px;font-weight:600;letter-spacing:-0.022em;margin-bottom:12px}
.block-body .desc{font-size:17px;color:var(--ink-2);line-height:1.5}
.block-example{font-size:15px;color:var(--ink);line-height:1.65;padding:4px 0 4px 24px;border-left:2px solid var(--accent)}
.block-example .tag{color:var(--accent);font-weight:500}

/* ===== 三步 ===== */
.steps{display:grid;grid-template-columns:repeat(3,1fr);border-top:1px solid var(--line)}
.step{padding:48px 32px;border-right:1px solid var(--line)}
.step:last-child{border-right:none}
.step .sn{font-size:13px;color:var(--accent);font-weight:500;letter-spacing:0.08em;margin-bottom:24px;font-variant-numeric:tabular-nums}
.step h4{font-size:22px;font-weight:600;letter-spacing:-0.02em;margin-bottom:10px}
.step p{font-size:15px;color:var(--ink-2);line-height:1.5}

/* ===== 对比 ===== */
.compare{display:grid;grid-template-columns:1fr 1fr;border-top:1px solid var(--line)}
.compare-col{padding:56px 0}
.compare-col + .compare-col{padding-left:64px;border-left:1px solid var(--line)}
.compare-col.before{padding-right:64px}
.compare-col .clabel{font-size:13px;font-weight:500;letter-spacing:0.06em;margin-bottom:32px;text-transform:uppercase}
.compare-col.before .clabel{color:var(--ink-3)}
.compare-col.after .clabel{color:var(--accent)}
.compare-col ul{list-style:none}
.compare-col li{font-size:18px;line-height:1.9;color:var(--ink-2)}
.compare-col.after li{color:var(--ink)}
.compare-col li.final{font-weight:600;margin-top:20px;padding-top:24px;border-top:1px solid var(--line-2);font-size:20px}
.compare-col.before li.final{color:var(--ink-3)}
.compare-col.after li.final{color:var(--accent)}

/* ===== 工具区（Tab） ===== */
.tool-tabs{display:flex;gap:0;border-bottom:1px solid var(--line);margin-bottom:48px}
.tool-tab{background:none;border:none;font-family:var(--font);font-size:15px;font-weight:500;color:var(--ink-3);padding:14px 28px;cursor:pointer;border-bottom:2px solid transparent;letter-spacing:0.01em;transition:color .2s,border-color .2s}
.tool-tab:hover{color:var(--ink)}
.tool-tab.active{color:var(--ink);border-bottom-color:var(--accent)}
.tool-panel{max-width:720px}
.tool-panel[hidden]{display:none}

/* ===== 表单（发丝细线） ===== */
label{display:block;font-size:13px;color:var(--ink-2);margin:20px 0 8px;letter-spacing:0.02em}
.input{width:100%;background:var(--paper);border:1px solid var(--line);border-radius:8px;padding:12px 14px;color:var(--ink);font-family:var(--font);font-size:15px;transition:border-color .15s}
.input:focus{outline:none;border-color:var(--accent)}
textarea.input{min-height:110px;resize:vertical}
.row{display:flex;gap:16px;align-items:flex-end}
.row > div{flex:1}
select.input{cursor:pointer}
.dropzone{border:1px dashed var(--line);border-radius:8px;padding:40px 24px;text-align:center;cursor:pointer;transition:border-color .15s,background .15s}
.dropzone:hover,.dropzone:focus-visible{border-color:var(--accent);background:var(--accent-soft);outline:none}
.dropzone-title{font-size:16px;font-weight:500;margin-bottom:6px}
.dropzone p{color:var(--ink-2)}
.file-name{color:var(--accent);font-weight:500}
.or-divider{text-align:center;color:var(--ink-3);font-size:13px;margin:18px 0 0;letter-spacing:0.04em}

/* ===== 进度（细线） ===== */
.progress{margin-top:20px}
.progress-bar{height:3px;border-radius:999px;background:var(--line);overflow:hidden}
.progress-fill{height:100%;width:40%;border-radius:999px;background:var(--accent);animation:indeterminate 1.2s ease-in-out infinite}
@keyframes indeterminate{0%{transform:translateX(-100%)}100%{transform:translateX(350%)}}
.progress-text{font-size:13px;color:var(--ink-2);margin-top:8px}

/* ===== 结果（编辑编号行） ===== */
#result{margin-top:56px}
#result .block{padding:40px 0}
.field{display:flex;gap:10px;margin-bottom:8px;font-size:14px}
.field .k{flex-shrink:0;color:var(--ink-3);min-width:72px;font-size:13px;padding-top:2px}
.copy-row{margin-top:14px;text-align:right}

/* ===== 历史 ===== */
.history{margin-top:72px;border-top:1px solid var(--line);padding-top:40px}
.history-head{margin-bottom:24px}
.history-head h3{font-size:22px;font-weight:600;letter-spacing:-0.02em}
.history-head .sec-tag{margin-bottom:8px}
.history-item{display:flex;align-items:center;gap:12px;padding:14px 0;border-bottom:1px solid var(--line)}
.history-item:last-child{border-bottom:none}
.history-time{color:var(--ink-3);font-size:12px;flex-shrink:0;width:140px}
.history-summary{flex:1;font-size:14px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.history-actions{display:flex;gap:8px;flex-shrink:0}

/* ===== CTA ===== */
.cta{padding:140px 0;text-align:center;border-bottom:1px solid var(--line-2)}
.cta h2{font-size:clamp(36px,5.4vw,60px);font-weight:600;letter-spacing:-0.038em;line-height:1.08;margin-bottom:24px}
.cta h2 .em{color:var(--accent)}
.cta p{font-size:19px;color:var(--ink-2);margin-bottom:40px}

/* ===== Footer ===== */
footer{padding:40px 0}
.foot-inner{display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:16px}
.foot-inner .copy{font-size:13px;color:var(--ink-3)}
.foot-links{display:flex;gap:24px;font-size:13px;color:var(--ink-2)}

/* ===== Toast ===== */
.toast{position:fixed;right:24px;bottom:24px;z-index:300;background:var(--ink);color:var(--paper);padding:12px 20px;border-radius:8px;font-size:14px;animation:toast-in .2s ease-out}
.toast.error{background:var(--error)}
@keyframes toast-in{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:none}}

/* ===== 滚动渐显 ===== */
.reveal{opacity:0;transform:translateY(20px);transition:opacity .9s cubic-bezier(.2,.7,.3,1),transform .9s cubic-bezier(.2,.7,.3,1)}
.reveal.in{opacity:1;transform:none}

/* ===== 无障碍 ===== */
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}

/* ===== 响应式 ===== */
@media (max-width:760px){
  .nav-links{display:none}
  section{padding:80px 0}
  .hero{padding:80px 0 60px}
  .meta-strip{flex-wrap:wrap;gap:28px;margin-top:48px}
  .block{grid-template-columns:1fr;gap:12px;padding:40px 0}
  .block-example{margin-top:8px}
  .steps{grid-template-columns:1fr}
  .step{border-right:none;border-bottom:1px solid var(--line)}
  .step:last-child{border-bottom:none}
  .compare{grid-template-columns:1fr}
  .compare-col + .compare-col{padding-left:0;border-left:none;border-top:1px solid var(--line);padding-top:48px}
  .compare-col.before{padding-right:0;padding-bottom:48px;border-bottom:1px solid var(--line)}
  .row{flex-direction:column;align-items:stretch}
  .row > div{width:100%}
  .history-item{flex-wrap:wrap}
  .history-time{width:auto}
  .tool-tab{padding:12px 16px;font-size:14px}
}
@media (prefers-reduced-motion:reduce){
  .reveal{opacity:1;transform:none;transition:none}
  html{scroll-behavior:auto}
  .progress-fill{animation:none}
}
```

- [ ] **Step 2: 运行 token 测试确认转绿**

Run: `py -3.12 tests/test_frontend.py`
Expected: `test_css_has_design_tokens` PASS。JS 相关测试仍 FAIL（Task 4 解决）。

- [ ] **Step 3: 提交**

```bash
git add web/static/css/style.css
git commit -m "feat: 重写设计系统为编辑风（墨黑+暖橙 token + 发丝边框 + 胶囊按钮 + 编辑编号行）"
```

---

### Task 4: 更新交互逻辑 `app.js`

保留全部核心函数，新增 Tab 切换、编辑风结果渲染、滚动渐显。

**Files:**
- Modify: `web/static/js/app.js`

**Interfaces:**
- Consumes: Task 2 的 HTML（Tab 按钮 `data-tab` / 面板 `panel-*`；`.block` 结果容器）
- Produces: 满足 `test_app_js_core_flow`、`test_app_js_history`、`test_app_js_tab_switch`；5 块方案以编辑编号行渲染进 `#result`

- [ ] **Step 1: 替换 `BLOCKS` 常量为纯中文标签**（编辑风用 `01/02/…` 编号，不再用 `①` 字形）

```js
const BLOCKS = ['诊断', '脚本改写', '包装', '转化话术', '下期选题'];
```

- [ ] **Step 2: 替换 `planCard` 为编辑编号行渲染**

```js
function planCard(idx, data, isTopics) {
  const label = BLOCKS[idx];
  const body = isTopics ? renderTopics(data) : renderObj(data);
  return `<div class="block">
    <div class="block-num">0${idx + 1}</div>
    <div class="block-body"><h3>${label}</h3>${body}</div>
    <div class="copy-row"><button class="btn btn-text btn-sm" onclick="copyBlock(${idx})">复制 →</button></div>
  </div>`;
}
```

- [ ] **Step 3: 新增 `switchTab` 函数**（插在 `copyBlock` 之后）

```js
function switchTab(name) {
  document.querySelectorAll('.tool-tab').forEach(t => {
    const on = t.dataset.tab === name;
    t.classList.toggle('active', on);
    t.setAttribute('aria-selected', on ? 'true' : 'false');
  });
  const panels = { optimize: 'panel-optimize', topics: 'panel-topics' };
  Object.entries(panels).forEach(([k, id]) => {
    document.getElementById(id).hidden = k !== name;
  });
}
```

- [ ] **Step 4: 在 `DOMContentLoaded` 内绑定 Tab 点击 + 滚动渐显**（在 `renderHistory();` 之后追加）

```js
  document.querySelectorAll('.tool-tab').forEach(t => {
    t.addEventListener('click', () => switchTab(t.dataset.tab));
  });

  const io = new IntersectionObserver((es) => {
    es.forEach(e => { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } });
  }, { threshold: 0.1, rootMargin: '0px 0px -6% 0px' });
  document.querySelectorAll('.reveal').forEach(el => io.observe(el));
```

- [ ] **Step 5: 运行全部前端测试确认转绿**

Run: `py -3.12 tests/test_frontend.py`
Expected: **全部 PASS，退出码 0**（现共 11 项）。

- [ ] **Step 6: 提交**

```bash
git add web/static/js/app.js
git commit -m "feat: 前端交互升级——Tab 切换 + 编辑编号行结果渲染 + 滚动渐显"
```

---

### Task 5: 全量回归 + 手动验证 + 收尾

**Files:**
- Verify: `web/templates/optimize.html`、`web/static/css/style.css`、`web/static/js/app.js`、`tests/test_frontend.py`
- Docs: `PROGRESS.md`（v4 P1 记录）

**Interfaces:**
- Consumes: Task 1-4 全部产物

- [ ] **Step 1: 全量回归**

Run: `py -3.12 tests/test_frontend.py`
Expected: 全部 PASS，退出码 0。

Run: `py -3.12 tests/test_advisor.py`
Expected: 10/10 PASS（后端未动，确保无副作用）。

Run: `py -3.12 tests/test_asr.py`
Expected: 10/10 PASS。

- [ ] **Step 2: 启动 Web 手动验证**

Run: `py -3.12 run.py --web`（后台启动），浏览器打开 `http://127.0.0.1:5000`
手动确认：
- 页面渲染为编辑风（墨黑文字 + 暖橙强调、发丝边框、无卡片阴影、Hero 大标题）
- 导航"开始使用"、Hero"立即体验"点击滚动到工具区
- Tab 可切换：`优化视频` / `选题灵感`（选题占位文案可见）
- 粘贴文字 → 生成方案（真实调用，需 `.env` Key）→ 5 块以编辑编号行展示、每块可复制
- 生成成功后"历史方案"出现新条目，可查看/删除
- 缩窄窗口（≤760px）响应式正常；键盘焦点可见

- [ ] **Step 3: 更新 PROGRESS.md**

在版本演进顶部新增 v4 P1 记录（前端编辑风重设计完成，含 commit 说明、测试数），并把 HANDOFF.md 状态行更新为 v4 P1 进度。

- [ ] **Step 4: 最终提交**

```bash
git add PROGRESS.md HANDOFF.md
git commit -m "docs: v4 P1 前端编辑风重设计完成（回归 + 手动验证通过）"
```
