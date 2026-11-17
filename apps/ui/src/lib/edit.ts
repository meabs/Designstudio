// Direct-edit state: an ordered log of edits per version and screen. The log is applied live to the preview frame and sent unchanged
// to the studio, which replays it on the saved HTML. Undo pops the log and reloads the frame; redo replays forward.
import { createStore, api } from './store';

export type Pos = 'before' | 'after' | 'inside';
export type Op = { op?: 'delete' | 'duplicate' | 'move' | 'insert' | 'image' | 'component'; design_id?: string; target_id?: string; position?: Pos; kind?: 'text' | 'button' | 'image'; style?: Record<string, string>; text?: string; at?: 'd' | 'm';
  data_url?: string; alt?: string; source_screen?: string; source_id?: string; html?: string }; // html is browser-only: the studio copies the component from the saved version itself
type Logs = Record<string, Record<string, Op[]>>; // version -> screen -> ops

export const editStore = createStore({ sel: [] as string[], logs: {} as Logs, redo: {} as Logs, tick: 0, free: false, at: '' as '' | 'd' | 'm', scope: 'all' as 'all' | 'view' });
export const frame: { doc: Document | null; version: string; screen: string } = { doc: null, version: '', screen: '' };

const KEY = (v: string) => `ds-edit:${v}`;
const STAMP = (v: string) => `ds-edit-t:${v}`;
const loaded = new Set<string>();
const hasOps = (l?: Record<string, Op[]>) => !!l && Object.values(l).some((x) => x.length);
function ensureLoaded(v: string) {
  if (loaded.has(v)) return; loaded.add(v);
  try { const raw = localStorage.getItem(KEY(v)); if (raw) { const l = JSON.parse(raw); if (l && typeof l === 'object') editStore.set((s) => ({ logs: { ...s.logs, [v]: l } })); } } catch { /* no storage: drafts just stay in memory */ }
  void pull(v);
}
// The studio keeps a copy of every draft, so it follows you to another browser. The newer copy wins.
async function pull(v: string) {
  try {
    const d = await api('draft-get', { variant_id: v }); const local = Number((() => { try { return localStorage.getItem(STAMP(v)); } catch { return 0; } })() || 0);
    if (hasOps(d.logs) && d.updated_at * 1000 > local && JSON.stringify(d.logs) !== JSON.stringify(editStore.get().logs[v] || {})) { editStore.set((s) => ({ logs: { ...s.logs, [v]: d.logs } })); reload(); bump(); }
  } catch { /* offline or no draft */ }
}
const timers: Record<string, ReturnType<typeof setTimeout>> = {};
function push(v: string) {
  clearTimeout(timers[v]);
  timers[v] = setTimeout(() => { const l = editStore.get().logs[v]; api('draft-save', { variant_id: v, logs: hasOps(l) ? l : {} }).catch(() => { /* kept locally */ }); }, 700);
}
function persist(v: string) {
  try { const l = editStore.get().logs[v]; if (hasOps(l)) { localStorage.setItem(KEY(v), JSON.stringify(l)); localStorage.setItem(STAMP(v), String(Date.now())); } else { localStorage.removeItem(KEY(v)); localStorage.removeItem(STAMP(v)); } } catch { /* ignore */ }
  push(v);
}
export const logOf = (v: string, screen: string): Op[] => { ensureLoaded(v); return editStore.get().logs[v]?.[screen] || []; };
const redoOf = (v: string, screen: string): Op[] => editStore.get().redo[v]?.[screen] || [];
const bump = () => editStore.set((s) => ({ tick: s.tick + 1 }));
const setLog = (v: string, screen: string, ops: Op[], redo?: Op[]) => {
  editStore.set((s) => ({ logs: { ...s.logs, [v]: { ...s.logs[v], [screen]: ops } }, ...(redo ? { redo: { ...s.redo, [v]: { ...s.redo[v], [screen]: redo } } } : {}) }));
  persist(v);
};

/* ---------- DOM helpers (mirror apps/api/edits.py exactly so ids agree before and after saving) ---------- */
export const elOf = (id: string): HTMLElement | null => (id && frame.doc ? (frame.doc.querySelector(`[data-design-id="${CSS.escape(id)}"]`) as HTMLElement | null) : null);
const q = (doc: Document, id: string) => doc.querySelector(`[data-design-id="${CSS.escape(id)}"]`) as HTMLElement | null;
const VOID = new Set(['AREA', 'BASE', 'BR', 'COL', 'EMBED', 'HR', 'IMG', 'INPUT', 'LINK', 'META', 'SOURCE', 'TRACK', 'WBR']);
const takenIds = (doc: Document) => new Set([...doc.querySelectorAll<HTMLElement>('[data-design-id]')].map((e) => e.dataset.designId as string));
function copyId(base: string, taken: Set<string>) { let c = base + '-copy', n = 2; while (taken.has(c)) { c = `${base}-copy-${n}`; n++; } taken.add(c); return c; }
// A copy never carries the screen's primary-action role, mirroring the studio, so "one primary action" stays true.
const demote = (root: HTMLElement) => [root, ...root.querySelectorAll<HTMLElement>('[data-role="primary-action"]')].forEach((e) => { if (e.getAttribute('data-role') === 'primary-action') e.removeAttribute('data-role'); });
function place(doc: Document, el: Element, target: HTMLElement, pos: Pos) {
  if (pos === 'before') target.before(el); else if (pos === 'after') target.after(el); else target.append(el);
  void doc;
}
export const docOrder = (ids: string[]) => ids.map((id) => ({ id, el: elOf(id) })).filter((x) => x.el).sort((a, b) => (a.el!.compareDocumentPosition(b.el!) & Node.DOCUMENT_POSITION_FOLLOWING ? -1 : 1)).map((x) => x.id);

export function paint(el: HTMLElement | null, e: { style?: Record<string, string>; text?: string }) {
  if (!el) return;
  for (const [k, v] of Object.entries(e.style || {})) { if (v === '') el.style.removeProperty(k); else el.style.setProperty(k, v); }
  if (e.text !== undefined && el.children.length === 0) el.textContent = e.text;
}
/* Width-specific styles: one generated block of media rules, the same format the studio writes (see apps/api/edits.py). */
const AT = { m: ['max', 600], d: ['min', 601] } as const; const RULE = /@media \((max|min)-width: (\d+)px\)\{\[data-design-id="([^"]+)"\]\{([^}]*)\}\}/g;
function scopedPaint(doc: Document, id: string, at: 'd' | 'm', style: Record<string, string>) {
  let el = doc.querySelector('style[data-studio-edits]') as HTMLStyleElement | null; const rules = new Map<string, Record<string, string>>();
  for (const m of (el?.textContent || '').matchAll(RULE)) { const d: Record<string, string> = {}; for (const part of m[4].split(';')) { const i = part.indexOf(':'); if (i > 0) d[part.slice(0, i).trim()] = part.slice(i + 1).replace('!important', '').trim(); } rules.set(`${m[1] === 'max' ? 'm' : 'd'}|${m[3]}`, d); }
  const cur = rules.get(`${at}|${id}`) || {}; for (const [k, v] of Object.entries(style)) { if (v === '') delete cur[k]; else cur[k] = v; } rules.set(`${at}|${id}`, cur);
  const out = [...rules.entries()].sort(([a], [b]) => (a < b ? -1 : 1)).filter(([, d]) => Object.keys(d).length).map(([key, d]) => { const [a, rid] = key.split('|'); const [kind, px] = AT[a as 'm' | 'd']; return `@media (${kind}-width: ${px}px){[data-design-id="${rid}"]{${Object.entries(d).map(([k, v]) => `${k}:${v} !important`).join(';')}}}`; });
  if (!out.length) { el?.remove(); return; }
  if (!el) { el = doc.createElement('style'); el.setAttribute('data-studio-edits', ''); (doc.head || doc.documentElement).append(el); }
  el.textContent = out.join('');
}
/** Apply one op to a document. Returns ids the selection should move to, if the op creates elements. */
export function applyOp(doc: Document, op: Op): string[] | null {
  if (op.op === 'insert') {
    const t = q(doc, op.target_id || ''); if (!t) return null; const taken = takenIds(doc); let n = 1; while (taken.has(`new-${op.kind}-${n}`)) n++;
    if (op.kind === 'image') {
      let m = 1; while (taken.has(`new-image-${m}`)) m++; const iid = `new-image-${m}`; const img = doc.createElement('img'); img.setAttribute('data-design-id', iid);
      img.setAttribute('src', op.data_url || ''); img.setAttribute('alt', op.alt || 'Image'); img.setAttribute('style', 'max-width:100%;height:auto'); place(doc, img, t, op.position || 'after'); return [iid];
    }
    const id = `new-${op.kind}-${n}`; const el = doc.createElement(op.kind === 'button' ? 'button' : 'p'); if (op.kind === 'button') el.setAttribute('type', 'button');
    el.setAttribute('data-design-id', id); el.textContent = op.kind === 'button' ? 'Button' : 'New text'; place(doc, el, t, op.position || 'after'); return [id];
  }
  if (op.op === 'component') {
    const t = q(doc, op.target_id || ''); if (!t || !op.html) return null; const tpl = doc.createElement('template'); tpl.innerHTML = op.html; const clone = tpl.content.firstElementChild as HTMLElement | null; if (!clone) return null;
    const taken = takenIds(doc); const made: string[] = [];
    [clone, ...clone.querySelectorAll<HTMLElement>('[data-design-id]')].forEach((c) => { if (c.dataset.designId) { const n = copyId(c.dataset.designId, taken); c.setAttribute('data-design-id', n); made.push(n); } });
    demote(clone); place(doc, clone, t, op.position || 'after'); return [made[0]];
  }
  const el = q(doc, op.design_id || ''); if (!el) return null;
  if (!op.op) { if (op.at && op.style) scopedPaint(doc, op.design_id || '', op.at, op.style); else paint(el, op); return null; }
  if (op.op === 'image') { if (el.tagName === 'IMG') { if (op.data_url) el.setAttribute('src', op.data_url); if (op.alt !== undefined) el.setAttribute('alt', op.alt); } return null; }
  if (op.op === 'delete') { el.remove(); return null; }
  if (op.op === 'duplicate') {
    const taken = takenIds(doc); const clone = el.cloneNode(true) as HTMLElement;
    [clone, ...clone.querySelectorAll<HTMLElement>('[data-design-id]')].forEach((c) => { if (c.dataset.designId) c.setAttribute('data-design-id', copyId(c.dataset.designId, taken)); });
    demote(clone); el.after(clone); return [clone.dataset.designId as string];
  }
  if (op.op === 'move') { const t = q(doc, op.target_id || ''); if (t && !el.contains(t) && t !== el) place(doc, el, t, op.position || 'after'); return null; }
  return null;
}
export function replay(doc: Document, ops: Op[]) { for (const o of ops) applyOp(doc, o); }

/* ---------- log operations ---------- */
const plain = (o: Op) => !o.op;
export function commit(v: string, screen: string, op: Op) {
  const ops = [...logOf(v, screen)];
  const at = editStore.get().at; if (plain(op) && op.style && !op.at && at) op = { ...op, at }; // "this width only": style changes become media rules
  if (plain(op)) { // merge into the trailing run of plain edits so a slider drag is one undo step per element
    const same = (o: Op) => plain(o) && o.design_id === op.design_id && o.at === op.at;
    let i = ops.length - 1; while (i >= 0 && plain(ops[i]) && !same(ops[i])) i--;
    if (i >= 0 && same(ops[i])) { ops[i] = { ...ops[i], style: { ...ops[i].style, ...op.style }, ...(op.text !== undefined ? { text: op.text } : {}) }; if (!Object.keys(ops[i].style || {}).length) delete ops[i].style; }
    else ops.push(op);
  } else ops.push(op);
  setLog(v, screen, ops, []);
  const made = frame.doc ? applyOp(frame.doc, op) : null;
  if (made) select(made);
  else if (op.op === 'delete') select(editStore.get().sel.filter((x) => x !== op.design_id));
  bump();
}
export const styleOf = (v: string, screen: string, ids: string[], style: Record<string, string>) => ids.forEach((id) => commit(v, screen, { design_id: id, style }));
export const canUndo = (v: string, screen: string) => logOf(v, screen).length > 0;
export const canRedo = (v: string, screen: string) => redoOf(v, screen).length > 0;
const reload = () => { try { frame.doc?.defaultView?.location.reload(); } catch { /* frame gone */ } };
export function undo(v: string, screen: string) {
  const ops = [...logOf(v, screen)]; const last = ops.pop(); if (!last) return;
  setLog(v, screen, ops, [...redoOf(v, screen), last]); reload(); bump();
}
export function redo(v: string, screen: string) {
  const r = [...redoOf(v, screen)]; const next = r.pop(); if (!next) return;
  setLog(v, screen, [...logOf(v, screen), next], r); if (frame.doc) { const made = applyOp(frame.doc, next); if (made) select(made); } bump();
}
export function resetElements(v: string, screen: string, ids: string[]) {
  setLog(v, screen, logOf(v, screen).filter((o) => !(plain(o) && ids.includes(o.design_id || ''))), []); reload(); bump();
}
export function discard(v: string) {
  editStore.set((s) => { const l = { ...s.logs }; delete l[v]; const r = { ...s.redo }; delete r[v]; return { logs: l, redo: r, sel: [] }; });
  persist(v); reload(); bump();
}
export const select = (ids: string[]) => editStore.set({ sel: ids });

export function payload(v: string) {
  ensureLoaded(v); const out: Record<string, Op[]> = {};
  for (const [screen, ops] of Object.entries(editStore.get().logs[v] || {})) if (ops.length) out[screen] = ops;
  return out;
}
export const countEdits = (v: string) => Object.values(payload(v)).reduce((n, l) => n + l.length, 0);

export function hexOf(css: string): string {
  const m = css.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/); if (!m) return /^#[0-9a-f]{6}$/i.test(css) ? css : '#000000';
  if (m[4] !== undefined && Number(m[4]) === 0) return '#ffffff';
  return '#' + [m[1], m[2], m[3]].map((x) => Number(x).toString(16).padStart(2, '0')).join('');
}
export const isLeaf = (el: HTMLElement | null) => !!el && el.children.length === 0 && !VOID.has(el.tagName);
export const isVoid = (el: HTMLElement | null) => !!el && VOID.has(el.tagName);
export function siblingId(id: string, dir: 'prev' | 'next'): string | null {
  let s = elOf(id)?.[dir === 'prev' ? 'previousElementSibling' : 'nextElementSibling'] as HTMLElement | null | undefined;
  while (s && !s.dataset.designId) s = s[dir === 'prev' ? 'previousElementSibling' : 'nextElementSibling'] as HTMLElement | null;
  return s?.dataset.designId || null;
}
