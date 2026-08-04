/* 优化工作台：提交 → 轮询 → 跳转方案详情页 */

let pollTimer = null;

function generate() {
  const file = document.getElementById('video-file').files[0];
  const text = document.getElementById('input-text').value.trim();
  const city = document.getElementById('city').value.trim();
  const platform = document.getElementById('platform').value;
  if (!file && !text) { toast('请选择视频或粘贴文字', true); return; }

  resetBtn(true);
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
        document.getElementById('progress-text').textContent = '完成，正在打开方案...';
        if (s.plan_id) {
          // 正常路径：跳转方案详情页（可收藏、可回看）
          window.location.href = '/plan/' + s.plan_id;
        } else {
          // 兜底：就地渲染
          renderInline(s.plan);
          resetBtn();
          hideProgress();
        }
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

/* 兜底：没有 plan_id 时就地展示 */
function renderInline(plan) {
  const box = document.getElementById('result');
  if (!box) return;
  const blocks = planToBlocks(plan);
  box.innerHTML = blocks.map((b, i) => `
    <div class="block">
      <div class="block-num">0${i + 1}</div>
      <div class="block-body"><h3>${esc(b.title)}</h3>${renderBlockBody(b)}</div>
    </div>`).join('');
  box.scrollIntoView({ behavior: 'smooth' });
}

function showProgress(msg) {
  document.getElementById('progress').hidden = false;
  document.getElementById('progress-text').textContent = msg || '准备生成...';
}
function hideProgress() { document.getElementById('progress').hidden = true; }
function resetBtn(disable) { document.getElementById('gen-btn').disabled = !!disable; }

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
