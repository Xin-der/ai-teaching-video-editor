/* Plan → Blocks 内容模型渲染
 * 新增 AI 产出类型时：在 PLAN_BLOCK_DEFS 注册，并在 RENDERERS / TEXTERS 加对应函数。
 * 页面结构无需改动。
 */

const LABELS = {
  summary: '诊断', issues: '问题', strengths: '优点',
  hook: '开头3秒', body: '主体', proof: '证明', cta: '引导',
  title: '标题', cover_text: '封面文字', description: '简介',
  pinned_comment: '置顶评论', profile_bio: '主页简介', dm_opening: '私信开场白',
};

const PLAN_BLOCK_DEFS = [
  { key: 'diagnosis',      title: '内容诊断' },
  { key: 'script_rewrite', title: '脚本改写' },
  { key: 'packaging',      title: '标题包装' },
  { key: 'conversion',     title: '转化话术' },
  { key: 'next_topics',    title: '下期选题' },
  { key: 'frame_review',   title: '帧点评' },
];

/* 把后端 plan 对象规范化为 blocks 数组（已有 blocks 字段则直接用） */
function planToBlocks(plan) {
  if (plan.blocks && plan.blocks.length) return plan.blocks;
  const blocks = [];
  PLAN_BLOCK_DEFS.forEach(def => {
    if (def.key === 'frame_review') {
      if (plan.frames && plan.frames.length) {
        blocks.push({ type: 'frame_review', title: def.title, data: plan.frames });
      }
    } else if (plan[def.key]) {
      blocks.push({ type: def.key, title: def.title, data: plan[def.key] });
    }
  });
  return blocks;
}

/* ===== 各类型的 HTML 渲染器 ===== */

function renderObj(obj) {
  if (!obj || !Object.keys(obj).length) return '<p class="muted">（无）</p>';
  return Object.entries(obj).map(([k, v]) => {
    if (Array.isArray(v)) v = v.join('；');
    return `<p class="field"><span class="k">${esc(LABELS[k] || k)}</span><span class="v">${esc(String(v))}</span></p>`;
  }).join('');
}

function renderTopicsList(list) {
  if (!list || !list.length) return '<p class="muted">（无）</p>';
  return list.map(t =>
    `<p class="field"><span class="k">选题</span><span class="v">${esc(t.title || '')} — ${esc(t.why || '')}</span></p>`
  ).join('');
}

function renderFrameItem(f) {
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

const RENDERERS = {
  next_topics: renderTopicsList,
  frame_review: (frames) =>
    `<p class="muted">AI 挑出最有问题的帧，橙色框是问题区域。</p>` +
    frames.map(renderFrameItem).join(''),
};

function renderBlockBody(block) {
  const fn = RENDERERS[block.type];
  return fn ? fn(block.data) : renderObj(block.data);
}

/* ===== 各类型的纯文本导出（复制用） ===== */

function objText(obj) {
  if (!obj) return '';
  return Object.entries(obj).map(([k, v]) => {
    if (Array.isArray(v)) v = v.join('；');
    return `${LABELS[k] || k}：${v}`;
  }).join('\n');
}

const TEXTERS = {
  next_topics: (list) => (list || []).map(t => `${t.title || ''}：${t.why || ''}`).join('\n'),
  frame_review: (frames) => (frames || []).map((f, i) => {
    const time = (f.time != null) ? fmtTime(f.time) : `帧 ${i + 1}`;
    const probs = (f.problems || []).map(p =>
      `${p.label || ''}${p.severity != null ? `（${p.severity.toFixed(2)}）` : ''}${p.advice ? `——${p.advice}` : ''}`
    ).join('；');
    return `${time}：${probs || '无明显问题'}`;
  }).join('\n'),
};

function blockText(block) {
  const fn = TEXTERS[block.type];
  const body = fn ? fn(block.data) : objText(block.data);
  return `【${block.title}】\n${body}`;
}
