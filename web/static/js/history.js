/* 历史方案页：从服务端读取方案列表 */

document.addEventListener('DOMContentLoaded', () => {
  const box = document.getElementById('history-list');
  if (!box) return;

  fetch('/api/plans')
    .then(res => res.ok ? res.json() : Promise.reject(new Error('加载历史失败')))
    .then(data => {
      const list = data.plans || [];
      if (!list.length) {
        box.innerHTML = '<p class="muted">还没有历史方案，<a href="/optimize" style="color:var(--accent)">去生成第一份 →</a></p>';
        return;
      }
      box.innerHTML = list.map(p => `
        <div class="history-item">
          <span class="history-time">${esc(p.created_at || p.id)}</span>
          <span class="history-summary">${esc(p.summary || '（方案）')}${p.city ? ` <span class="muted">· ${esc(p.city)}</span>` : ''}</span>
          <span class="history-actions">
            <a class="btn btn-outline btn-sm" href="/plan/${esc(p.id)}">查看</a>
          </span>
        </div>`).join('');
    })
    .catch(e => {
      box.innerHTML = `<p class="muted">${esc(e.message)}</p>`;
    });
});
