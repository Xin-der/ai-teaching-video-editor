/* 方案详情页：目录 + 内容块渲染 + 复制 */

document.addEventListener('DOMContentLoaded', () => {
  const plan = window.PLAN;
  if (!plan) return;

  const blocks = planToBlocks(plan);

  /* 头部信息 */
  const summary = plan.summary
    || (blocks[0] && blocks[0].data && blocks[0].data.summary)
    || '';
  if (summary) document.getElementById('plan-title').textContent = summary;

  const meta = [];
  if (plan.created_at) meta.push(plan.created_at);
  if (plan.city) meta.push(plan.city);
  if (plan.platform) meta.push(plan.platform === 'douyin' ? '抖音' : plan.platform);
  document.getElementById('plan-meta').textContent = meta.join(' · ');

  /* 目录 */
  const toc = document.getElementById('plan-toc');
  toc.innerHTML = blocks.map((b, i) =>
    `<a href="#block-${i}"><span class="toc-num">0${i + 1}</span>${esc(b.title)}</a>`
  ).join('');

  /* 内容块 */
  const box = document.getElementById('plan-blocks');
  box.innerHTML = blocks.map((b, i) => `
    <div class="plan-block" id="block-${i}">
      <div class="plan-block-head">
        <div class="plan-block-title">
          <span class="block-num">0${i + 1}</span>
          <h3>${esc(b.title)}</h3>
        </div>
        <button class="btn btn-text btn-sm" data-copy="${i}">复制 →</button>
      </div>
      <div class="plan-block-body">${renderBlockBody(b)}</div>
    </div>`).join('');

  /* 单块复制 */
  box.addEventListener('click', (e) => {
    const btn = e.target.closest('[data-copy]');
    if (!btn) return;
    const text = blockText(blocks[Number(btn.getAttribute('data-copy'))]);
    if (!text) { toast('没有可复制的内容', true); return; }
    copyText(text).then(ok => toast(ok ? '已复制' : '复制失败', !ok));
  });

  /* 复制全部 */
  document.getElementById('copy-all-btn').addEventListener('click', () => {
    const text = blocks.map(blockText).join('\n\n');
    copyText(text).then(ok => toast(ok ? '已复制整份方案' : '复制失败', !ok));
  });

  /* 目录滚动高亮 */
  const links = toc.querySelectorAll('a');
  const sections = box.querySelectorAll('.plan-block');
  const spy = new IntersectionObserver((es) => {
    es.forEach(en => {
      if (!en.isIntersecting) return;
      links.forEach(l => l.classList.toggle('active', l.getAttribute('href') === '#' + en.target.id));
    });
  }, { rootMargin: '-20% 0px -70% 0px' });
  sections.forEach(s => spy.observe(s));
});
