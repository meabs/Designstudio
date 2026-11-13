// Pure helpers: escaping, icons, badges, Markdown preview, context diffs. No DOM access except icon markup strings.
export const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

const ICONS = {
  projects: '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/>',
  boards: '<rect x="3" y="3" width="18" height="18" rx="2"/><path d="M3 9h18M9 21V9"/>',
  research: '<circle cx="11" cy="11" r="7"/><path d="m21 21-4.3-4.3"/>',
  context: '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6M8 13h8M8 17h5"/>',
  history: '<circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/>',
  settings: '<path d="M4 6h10M18 6h2M4 12h2M10 12h10M4 18h12M20 18h0"/><circle cx="16" cy="6" r="2"/><circle cx="8" cy="12" r="2"/><circle cx="18" cy="18" r="2"/>',
  plus: '<path d="M12 5v14M5 12h14"/>', check: '<path d="m5 12 5 5L20 7"/>', x: '<path d="M18 6 6 18M6 6l12 12"/>',
  play: '<path d="M7 4v16l13-8z"/>', spark: '<path d="M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z"/>',
  download: '<path d="M12 4v11m0 0-4-4m4 4 4-4M5 20h14"/>', external: '<path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/>',
  undo: '<path d="M3 7v6h6"/><path d="M21 17a9 9 0 0 0-15-6.7L3 13"/>', back: '<path d="M19 12H5m0 0 6-6m-6 6 6 6"/>', forward: '<path d="M5 12h14m0 0-6-6m6 6-6 6"/>',
  refresh: '<path d="M21 12a9 9 0 1 1-3-6.7L21 8"/><path d="M21 3v5h-5"/>', phone: '<rect x="7" y="2" width="10" height="20" rx="2"/><path d="M11 18h2"/>',
  monitor: '<rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/>', trash: '<path d="M4 7h16M10 11v6M14 11v6M6 7l1 13h10l1-13M9 7V4h6v3"/>',
  edit: '<path d="M4 20h4L19 9l-4-4L4 16z"/>', pin: '<path d="M12 21s7-6.2 7-11a7 7 0 0 0-14 0c0 4.8 7 11 7 11z"/><circle cx="12" cy="10" r="2.5"/>',
  columns: '<rect x="3" y="4" width="8" height="16" rx="1"/><rect x="13" y="4" width="8" height="16" rx="1"/>', lock: '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
  dots: '<circle cx="5" cy="12" r="1"/><circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/>', link: '<path d="M10 14a4 4 0 0 0 5.7 0l3-3a4 4 0 0 0-5.7-5.7l-1 1M14 10a4 4 0 0 0-5.7 0l-3 3a4 4 0 0 0 5.7 5.7l1-1"/>',
  stop: '<rect x="6" y="6" width="12" height="12" rx="1"/>', file: '<path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9z"/><path d="M14 3v6h6"/>',
  tokens: '<circle cx="8" cy="8" r="4"/><circle cx="16" cy="16" r="4"/><path d="M11 11l2 2"/>', rules: '<path d="M9 6h11M9 12h11M9 18h11"/><path d="m3 6 1 1 2-2M3 12l1 1 2-2M3 18l1 1 2-2"/>',
  eye: '<path d="M2 12s4-7 10-7 10 7 10 7-4 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
  cursor: '<path d="M5 3l14 7-6 2-2 6z"/>', comment: '<path d="M4 5a2 2 0 0 1 2-2h12a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H9l-5 4z"/>', layers: '<path d="m12 3 9 5-9 5-9-5z"/><path d="m3 13 9 5 9-5"/>',
  frame: '<path d="M7 3v18M17 3v18M3 7h18M3 17h18"/>', chevron: '<path d="m9 6 6 6-6 6"/>', minus: '<path d="M5 12h14"/>', fit: '<path d="M4 9V5h4M20 9V5h-4M4 15v4h4M20 15v4h-4"/>',
  image: '<rect x="3" y="4" width="18" height="16" rx="2"/><circle cx="9" cy="10" r="1.6"/><path d="m21 16-5-5-8 9"/>', upload: '<path d="M12 16V4m0 0-4 4m4-4 4 4M5 20h14"/>',
};
export const icon = (name, size = 15) => `<svg class="ic" width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${ICONS[name] || ICONS.file}</svg>`;
export const badge = (text, kind = '') => `<span class="badge ${kind}">${text}</span>`;

// Minimal, escaping-first Markdown for the guidelines preview (headings, lists, bold, code, paragraphs).
export function renderMarkdown(src) {
  const inline = t => esc(t).replace(/`([^`]+)`/g, '<code>$1</code>').replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>').replace(/\*([^*]+)\*/g, '<em>$1</em>');
  const out = []; let list = false, para = [];
  const flush = () => { if (para.length) out.push(`<p>${inline(para.join(' '))}</p>`); para = []; };
  const close = () => { if (list) out.push('</ul>'); list = false; };
  for (const raw of String(src ?? '').split('\n')) {
    const line = raw.trimEnd(); let m;
    if (!line.trim()) { flush(); close(); continue; }
    if ((m = line.match(/^(#{1,4})\s+(.*)$/))) { flush(); close(); out.push(`<h${m[1].length + 1}>${inline(m[2])}</h${m[1].length + 1}>`); continue; }
    if ((m = line.match(/^\s*[-*]\s+(.*)$/))) { flush(); if (!list) out.push('<ul>'); list = true; out.push(`<li>${inline(m[1])}</li>`); continue; }
    close(); para.push(line.trim());
  }
  flush(); close(); return out.join('') || '<p class="muted">Nothing to preview yet.</p>';
}

// Structural diff between two saved context versions.
export function contextDiff(prev, cur) {
  if (!prev) return { markdown: { added: [], removed: [] }, tokens: { added: [], changed: [], removed: [] }, rules: { added: [], changed: [], removed: [] }, initial: true };
  const lines = t => String(t ?? '').split('\n').map(x => x.trim()).filter(Boolean);
  const [a, b] = [lines(prev.markdown), lines(cur.markdown)];
  const keys = (x, y) => ({ added: Object.keys(y).filter(k => !(k in x)), removed: Object.keys(x).filter(k => !(k in y)), changed: Object.keys(y).filter(k => k in x && String(x[k]) !== String(y[k])) });
  const ruleMap = rs => Object.fromEntries((rs || []).map(r => [r.id, { ...r, version: undefined }]));
  const [ra, rb] = [ruleMap(prev.rules), ruleMap(cur.rules)];
  const rk = { added: Object.keys(rb).filter(k => !(k in ra)), removed: Object.keys(ra).filter(k => !(k in rb)), changed: Object.keys(rb).filter(k => k in ra && JSON.stringify(ra[k]) !== JSON.stringify(rb[k])) };
  return { markdown: { added: b.filter(l => !a.includes(l)), removed: a.filter(l => !b.includes(l)) }, tokens: keys(prev.tokens, cur.tokens), rules: rk };
}
export function diffIsEmpty(d) { return !d.markdown.added.length && !d.markdown.removed.length && Object.values(d.tokens).every(x => !x.length) && Object.values(d.rules).every(x => !x.length); }
export function diffSummary(d) {
  if (d.initial) return 'Initial version';
  const parts = [];
  const n = (label, count) => count && parts.push(`${count} ${label}`);
  n('guideline lines changed', d.markdown.added.length + d.markdown.removed.length);
  n('token changes', d.tokens.added.length + d.tokens.changed.length + d.tokens.removed.length);
  n('rule changes', d.rules.added.length + d.rules.changed.length + d.rules.removed.length);
  return parts.join(' · ') || 'No content changes';
}

export const fmtTime = t => new Date(t * 1000).toLocaleString();
export const fmtDuration = j => { const end = j.events.at(-1)?.time, start = j.events[0]?.time; return end && start ? `${Math.max(0, Math.round(end - start))}s` : ''; };
export const fmtHash = h => (h || '').slice(0, 8);
export const isUrl = s => /^https?:\/\/\S+$/i.test(String(s || '').trim());

export const fmtBytes = n => n > 1e6 ? (n / 1e6).toFixed(1) + ' MB' : Math.max(1, Math.round(n / 1e3)) + ' KB';
