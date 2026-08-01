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
