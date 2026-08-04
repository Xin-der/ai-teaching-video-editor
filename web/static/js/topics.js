/* 选题库页：精选选题 + AI 生成 */

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
  copyText(text).then(ok => toast(ok ? '已复制' : '复制失败', !ok));
}

function copyGeneratedTopic(i) {
  const t = (currentGeneratedTopics || [])[i];
  if (!t) return;
  const text = `${t.title}\n${t.description || ''}\n为什么现在发：${t.why_now || ''}\n拍摄思路：${t.shooting_idea || ''}`;
  copyText(text).then(ok => toast(ok ? '已复制' : '复制失败', !ok));
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

document.addEventListener('DOMContentLoaded', () => {
  loadTopics();
  const genTopicsBtn = document.getElementById('gen-topics-btn');
  if (genTopicsBtn) genTopicsBtn.addEventListener('click', generateTopics);
});
