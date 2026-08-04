/* 驾校内容优化工具 · 前端交互 */
const BLOCKS = ['诊断', '脚本改写', '包装', '转化话术', '下期选题'];
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
    } catch (e) {
      console.error(e);
      clearInterval(pollTimer);
      toast('获取进度失败，请重试', true);
      resetBtn();
      hideProgress();
    }
  }, 1000);
}

function renderPlan(plan) {
  const box = document.getElementById('result');
  const cards = [
    planCard(0, plan.diagnosis, false),
    planCard(1, plan.script_rewrite, false),
    planCard(2, plan.packaging, false),
    planCard(3, plan.conversion, false),
    planCard(4, plan.next_topics, true),
  ];
  const frameCard = (plan.frames && plan.frames.length) ? frameDiagnoseCard(plan.frames) : '';
  box.innerHTML = cards.join('') + frameCard;
  box.scrollIntoView({ behavior: 'smooth' });
}

function planCard(idx, data, isTopics) {
  const label = BLOCKS[idx];
  const body = isTopics ? renderTopics(data) : renderObj(data);
  return `<div class="block">
    <div class="block-num">0${idx + 1}</div>
    <div class="block-body"><h3>${label}</h3>${body}</div>
    <div class="copy-row"><button class="btn btn-text btn-sm" onclick="copyBlock(${idx})">复制 →</button></div>
  </div>`;
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

/* ===== 帧点评 ===== */
function frameDiagnoseCard(frames) {
  return `<div class="block frame-block">
    <div class="block-num">06</div>
    <div class="block-body">
      <h3>帧点评</h3>
      <p class="muted">AI 挑出最有问题的帧，橙色框是问题区域。</p>
      ${frames.map(renderFrame).join('')}
    </div>
    <div class="copy-row"><button class="btn btn-text btn-sm" onclick="copyFrameText()">复制诊断 →</button></div>
  </div>`;
}

function renderFrame(f) {
  const time = (f.time != null) ? fmtTime(f.time) : `帧 ${(f.index || 0) + 1}`;
  const probs = (f.problems || []).map(p =>
    `<p class="frame-problem"><span class="tag">${esc(p.label)}</span>` +
    (p.advice ? ` <span class="muted">——${esc(p.advice)}</span>` : '') +
    (p.severity != null ? ` <span class="muted">严重度 ${(p.severity).toFixed(2)}</span>` : '') +
    `</p>`
  ).join('') || '<p class="muted">（无明显问题）</p>';

  const img = f.image_b64
    ? `<div class="frame-img">
        <img src="data:image/jpeg;base64,${f.image_b64}" alt="诊断帧 ${time}">
        <div class="frame-boxes">${(f.problems || []).filter(p => p.box).map(p => {
          const b = p.box;
          return `<i class="frame-box" style="left:${b[0] * 100}%;top:${b[1] * 100}%;width:${(b[2] - b[0]) * 100}%;height:${(b[3] - b[1]) * 100}%" title="${esc(p.label)}"></i>`;
        }).join('')}</div>
      </div>`
    : '<p class="muted">（无画面）</p>';

  return `<div class="frame-card"><div class="frame-meta">${time}</div>${img}${probs}</div>`;
}

function copyFrameText() {
  const frames = (currentPlan && currentPlan.frames) || [];
  if (!frames.length) { toast('没有可复制的帧诊断', true); return; }
  const lines = frames.map((f, i) => {
    const time = (f.time != null) ? fmtTime(f.time) : `帧 ${i + 1}`;
    const probs = (f.problems || []).map(p =>
      `${p.label || ''}${p.severity != null ? `（${p.severity.toFixed(2)}）` : ''}${p.advice ? `——${p.advice}` : ''}`
    ).join('；');
    return `${time}：${probs || '无明显问题'}`;
  });
  copyText(lines.join('\n')).then(ok => toast(ok ? '已复制 ✅' : '复制失败', !ok));
}

function fmtTime(s) {
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
}

function copyBlock(idx) {
  const data = currentPlan ? currentPlan[KEYS[idx]] : null;
  const text = fmtBlock(data);
  if (!text) { toast('没有可复制的内容', true); return; }
  copyText(text).then(ok => toast(ok ? '已复制 ✅' : '复制失败', !ok));
}

function copyText(text) {
  // 优先 Clipboard API（需安全上下文：HTTPS 或 localhost）
  if (navigator.clipboard && window.isSecureContext) {
    return navigator.clipboard.writeText(text).then(() => true).catch(() => legacyCopy(text));
  }
  return Promise.resolve(legacyCopy(text));
}

function legacyCopy(text) {
  // 非安全上下文（局域网 / 手机 http 访问）降级：临时 textarea + execCommand
  try {
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.setAttribute('readonly', '');
    ta.style.position = 'fixed';
    ta.style.top = '0';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.focus();
    ta.select();
    const ok = document.execCommand('copy');
    document.body.removeChild(ta);
    return ok;
  } catch (e) { return false; }
}

function switchTab(name) {
  document.querySelectorAll('.tool-tab').forEach(t => {
    const on = t.getAttribute('data-tab') === name;
    t.classList.toggle('active', on);
    t.setAttribute('aria-selected', on ? 'true' : 'false');
  });
  const panels = { optimize: 'panel-optimize', topics: 'panel-topics' };
  Object.entries(panels).forEach(([k, id]) => {
    const el = document.getElementById(id); if (el) el.hidden = k !== name;
  });
}

/* ===== 选题灵感 ===== */
let curatedTopics = [];
let currentGeneratedTopics = null;
let topicsPollTimer = null;

function loadTopics() {
  fetch('/api/topics')
    .then(res => res.ok ? res.json() : Promise.reject(new Error('加载选题库失败')))
    .then(data => {
      curatedTopics = data.topics || [];
      renderTopicList(curatedTopics);
    })
    .catch(e => {
      const box = document.getElementById('topic-list');
      if (box) box.innerHTML = `<p class="muted">${esc(e.message)}</p>`;
    });
}

function renderTopicList(list) {
  const box = document.getElementById('topic-list');
  if (!box) return;
  if (!list.length) { box.innerHTML = '<p class="muted">（暂无选题）</p>'; return; }
  box.innerHTML = list.map((t, i) => `
    <div class="topic-card">
      <div class="topic-head">
        <span class="topic-cat">${esc(t.category || '')}</span>
        <span class="topic-diff">${esc(t.difficulty || '')}</span>
      </div>
      <h4 class="topic-title">${esc(t.title)}</h4>
      <p class="topic-desc">${esc(t.description || '')}</p>
      ${(t.tags && t.tags.length) ? `<div class="topic-tags">${t.tags.map(x => `<span class="tag">${esc(x)}</span>`).join('')}</div>` : ''}
      <button class="btn btn-text btn-sm" onclick="copyTopic(${i})">复制 →</button>
    </div>`).join('');
}

function generateTopics() {
  const city = document.getElementById('topic-city').value.trim();
  const season = document.getElementById('topic-season').value;
  const hot = document.getElementById('topic-hot').value.trim();
  const btn = document.getElementById('gen-topics-btn');
  btn.disabled = true;
  showTopicsProgress('生成中...');
  document.getElementById('topics-result').innerHTML = '';
  fetch('/api/topics/generate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ city, season, hot_topic: hot }),
  })
    .then(async res => {
      if (!res.ok) { const e = await res.json().catch(() => ({})); throw new Error(e.error || '提交失败'); }
      pollTopicsStatus();
    })
    .catch(e => {
      toast(e.message, true);
      hideTopicsProgress();
      btn.disabled = false;
    });
}

function pollTopicsStatus() {
  if (topicsPollTimer) clearInterval(topicsPollTimer);
  topicsPollTimer = setInterval(async () => {
    try {
      const s = await (await fetch('/api/topics/generate/status')).json();
      if (s.progress) document.getElementById('topics-progress-text').textContent = s.progress;
      if (s.error) {
        clearInterval(topicsPollTimer);
        toast(s.error, true);
        hideTopicsProgress();
        document.getElementById('gen-topics-btn').disabled = false;
        return;
      }
      if (s.topics) {
        clearInterval(topicsPollTimer);
        currentGeneratedTopics = s.topics;
        renderGeneratedTopics(s.topics);
        hideTopicsProgress();
        document.getElementById('gen-topics-btn').disabled = false;
      }
    } catch (e) {
      console.error(e);
      clearInterval(topicsPollTimer);
      toast('获取生成状态失败，请重试', true);
      hideTopicsProgress();
      document.getElementById('gen-topics-btn').disabled = false;
    }
  }, 1000);
}

function renderGeneratedTopics(list) {
  const box = document.getElementById('topics-result');
  if (!box) return;
  if (!list || !list.length) { box.innerHTML = '<p class="muted">（没有生成到选题，请重试）</p>'; return; }
  box.innerHTML = list.map((t, i) => `
    <div class="topic-card generated">
      <div class="block-num">0${i + 1}</div>
      <h4 class="topic-title">${esc(t.title)}</h4>
      <p class="topic-desc">${esc(t.description || '')}</p>
      <p class="field"><span class="k">现在发</span><span class="v">${esc(t.why_now || '')}</span></p>
      <p class="field"><span class="k">拍摄</span><span class="v">${esc(t.shooting_idea || '')}</span></p>
      <button class="btn btn-text btn-sm" onclick="copyGeneratedTopic(${i})">复制 →</button>
    </div>`).join('');
}

function copyTopic(i) {
  const t = curatedTopics[i];
  if (!t) return;
  const tags = (t.tags || []).length ? '\n#' + t.tags.join(' #') : '';
  const text = `【${t.title}】\n${t.description || ''}${tags}`;
  copyText(text).then(ok => toast(ok ? '已复制 ✅' : '复制失败', !ok));
}

function copyGeneratedTopic(i) {
  const t = (currentGeneratedTopics || [])[i];
  if (!t) return;
  const text = `${t.title}\n${t.description || ''}\n为什么现在发：${t.why_now || ''}\n拍摄思路：${t.shooting_idea || ''}`;
  copyText(text).then(ok => toast(ok ? '已复制 ✅' : '复制失败', !ok));
}

function showTopicsProgress(msg) {
  const p = document.getElementById('topics-progress');
  if (p) p.hidden = false;
  const t = document.getElementById('topics-progress-text');
  if (t) t.textContent = msg || '生成中...';
}
function hideTopicsProgress() {
  const p = document.getElementById('topics-progress');
  if (p) p.hidden = true;
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

function loadHistory() {
  try {
    const list = JSON.parse(localStorage.getItem(HISTORY_KEY) || '[]');
    return Array.isArray(list) ? list : [];
  } catch (e) { return []; }
}

function saveHistory(plan) {
  const list = loadHistory();
  // 历史只存文字诊断，不存 base64 图片，避免撑爆 localStorage
  const slim = JSON.parse(JSON.stringify(plan));
  if (slim.frames) slim.frames.forEach(f => delete f.image_b64);
  list.unshift({ ts: Date.now(), plan: slim });
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
    const summary = (item.plan && item.plan.diagnosis && item.plan.diagnosis.summary) || '（方案）';
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
  renderHistory();
  loadTopics();

  const genTopicsBtn = document.getElementById('gen-topics-btn');
  if (genTopicsBtn) genTopicsBtn.addEventListener('click', generateTopics);

  document.querySelectorAll('.tool-tab').forEach(t => {
    t.addEventListener('click', () => switchTab(t.getAttribute('data-tab')));
  });

  const io = new IntersectionObserver((es) => {
    es.forEach(e => { if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target); } });
  }, { threshold: 0.1, rootMargin: '0px 0px -6% 0px' });
  document.querySelectorAll('.reveal').forEach(el => io.observe(el));
});
