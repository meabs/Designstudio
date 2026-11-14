// Pure helpers ported from the old UI: formatting, Markdown preview, context diffs, ids.
export const esc = (s: unknown) => String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c] as string));

// Minimal, escaping-first Markdown for the guidelines preview (headings, lists, bold, code, paragraphs).
export function renderMarkdown(src: unknown): string {
  const inline = (t: string) => esc(t).replace(/`([^`]+)`/g, '<code>$1</code>').replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>').replace(/\*([^*]+)\*/g, '<em>$1</em>');
  const out: string[] = []; let list = false; let para: string[] = [];
  const flush = () => { if (para.length) out.push(`<p>${inline(para.join(' '))}</p>`); para = []; };
  const close = () => { if (list) out.push('</ul>'); list = false; };
  for (const raw of String(src ?? '').split('\n')) {
    const line = raw.trimEnd(); let m: RegExpMatchArray | null;
    if (!line.trim()) { flush(); close(); continue; }
    if ((m = line.match(/^(#{1,4})\s+(.*)$/))) { flush(); close(); out.push(`<h${m[1].length + 1}>${inline(m[2])}</h${m[1].length + 1}>`); continue; }
    if ((m = line.match(/^\s*[-*]\s+(.*)$/))) { flush(); if (!list) out.push('<ul>'); list = true; out.push(`<li>${inline(m[1])}</li>`); continue; }
    close(); para.push(line.trim());
  }
  flush(); close(); return out.join('') || '<p class="muted">Nothing to preview yet.</p>';
}

export function contextDiff(prev: any, cur: any) {
  if (!prev) return { markdown: { added: [], removed: [] }, tokens: { added: [], changed: [], removed: [] }, rules: { added: [], changed: [], removed: [] }, initial: true } as any;
  const lines = (t: unknown) => String(t ?? '').split('\n').map((x) => x.trim()).filter(Boolean);
  const [a, b] = [lines(prev.markdown), lines(cur.markdown)];
  const keys = (x: any, y: any) => ({ added: Object.keys(y).filter((k) => !(k in x)), removed: Object.keys(x).filter((k) => !(k in y)), changed: Object.keys(y).filter((k) => k in x && String(x[k]) !== String(y[k])) });
  const ruleMap = (rs: any[]) => Object.fromEntries((rs || []).map((r) => [r.id, { ...r, version: undefined }]));
  const [ra, rb] = [ruleMap(prev.rules), ruleMap(cur.rules)] as any[];
  const rk = { added: Object.keys(rb).filter((k) => !(k in ra)), removed: Object.keys(ra).filter((k) => !(k in rb)), changed: Object.keys(rb).filter((k) => k in ra && JSON.stringify(ra[k]) !== JSON.stringify(rb[k])) };
  return { markdown: { added: b.filter((l) => !a.includes(l)), removed: a.filter((l) => !b.includes(l)) }, tokens: keys(prev.tokens, cur.tokens), rules: rk } as any;
}
export const diffIsEmpty = (d: any) => !d.markdown.added.length && !d.markdown.removed.length && Object.values(d.tokens).every((x: any) => !x.length) && Object.values(d.rules).every((x: any) => !x.length);
export function diffSummary(d: any) {
  if (d.initial) return 'Initial version';
  const parts: string[] = []; const n = (label: string, count: number) => count && parts.push(`${count} ${label}`);
  n('guideline lines changed', d.markdown.added.length + d.markdown.removed.length);
  n('token changes', d.tokens.added.length + d.tokens.changed.length + d.tokens.removed.length);
  n('rule changes', d.rules.added.length + d.rules.changed.length + d.rules.removed.length);
  return parts.join(' · ') || 'No content changes';
}

export const fmtTime = (t: number) => new Date(t * 1000).toLocaleString();
export const fmtDuration = (j: any) => { const end = j.events.at(-1)?.time; const start = j.events[0]?.time; return end && start ? `${Math.max(0, Math.round(end - start))}s` : ''; };
export const fmtHash = (h?: string) => (h || '').slice(0, 8);
export const isUrl = (s: unknown) => /^https?:\/\/\S+$/i.test(String(s || '').trim());
export const fmtBytes = (n: number) => (n > 1e6 ? (n / 1e6).toFixed(1) + ' MB' : Math.max(1, Math.round(n / 1e3)) + ' KB');
export const fmtWhen = (t: number) => new Date(t * 1000).toLocaleString(undefined, { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
export function ago(t: number, now = Date.now() / 1000) {
  const d = Math.max(0, now - t);
  if (d < 90) return 'just now'; if (d < 3600) return `${Math.round(d / 60)} min ago`; if (d < 86400) return `${Math.round(d / 3600)} h ago`;
  const days = Math.round(d / 86400); return days < 14 ? `${days} day${days === 1 ? '' : 's'} ago` : new Date(t * 1000).toLocaleDateString(undefined, { day: 'numeric', month: 'short' });
}
export const fmtDur = (s?: number | null) => (s == null ? '' : s < 1 ? '<1s' : s < 60 ? `${Math.round(s)}s` : `${Math.floor(s / 60)}m ${String(Math.round(s % 60)).padStart(2, '0')}s`);
export const kTokens = (n: number) => (n >= 1e6 ? (n / 1e6).toFixed(1) + 'M' : n >= 1e3 ? Math.round(n / 1e3) + 'k' : String(n));

// crypto.randomUUID exists only on secure pages (HTTPS or localhost); a phone on the LAN uses plain http.
export function uuid(c: any = (globalThis as any).crypto): string {
  if (c?.randomUUID) return c.randomUUID();
  const b = new Uint8Array(16);
  if (c?.getRandomValues) c.getRandomValues(b); else for (let i = 0; i < 16; i++) b[i] = Math.floor(Math.random() * 256);
  b[6] = (b[6] & 0x0f) | 0x40; b[8] = (b[8] & 0x3f) | 0x80;
  const h = [...b].map((x) => x.toString(16).padStart(2, '0')).join('');
  return `${h.slice(0, 8)}-${h.slice(8, 12)}-${h.slice(12, 16)}-${h.slice(16, 20)}-${h.slice(20)}`;
}
