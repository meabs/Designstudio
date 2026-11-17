// Direct-edit state: unsaved element edits per version and screen, applied live to the preview frame and sent to the studio as one new version.
import { createStore } from './store';

export type ElEdit = { style: Record<string, string>; text?: string };
type Drafts = Record<string, Record<string, Record<string, ElEdit>>>; // version -> screen -> design id -> edit

export const editStore = createStore({ sel: '', drafts: {} as Drafts, tick: 0 });
export const frame: { doc: Document | null; version: string; screen: string } = { doc: null, version: '', screen: '' };

export const EDITABLE = ['color', 'background-color', 'font-size', 'font-weight', 'text-align', 'border-radius', 'padding', 'opacity', 'display'] as const;

const bump = () => editStore.set((s) => ({ tick: s.tick + 1 }));
export const elOf = (id: string): HTMLElement | null => (id && frame.doc ? (frame.doc.querySelector(`[data-design-id="${CSS.escape(id)}"]`) as HTMLElement | null) : null);
export const select = (id: string) => editStore.set({ sel: id });
export const draftOf = (version: string, screen: string, id: string): ElEdit | undefined => editStore.get().drafts[version]?.[screen]?.[id];

export function setEdit(version: string, screen: string, id: string, patch: { style?: Record<string, string>; text?: string }) {
  editStore.set((s) => {
    const cur = s.drafts[version]?.[screen]?.[id] || { style: {} };
    const next: ElEdit = { style: { ...cur.style, ...(patch.style || {}) }, text: patch.text !== undefined ? patch.text : cur.text };
    return { drafts: { ...s.drafts, [version]: { ...s.drafts[version], [screen]: { ...s.drafts[version]?.[screen], [id]: next } } } };
  });
  paint(elOf(id), draftOf(version, screen, id));
  bump();
}

export function paint(el: HTMLElement | null, e?: ElEdit) {
  if (!el || !e) return;
  for (const [k, v] of Object.entries(e.style)) { if (v === '') el.style.removeProperty(k); else el.style.setProperty(k, v); }
  if (e.text !== undefined && el.children.length === 0) el.textContent = e.text;
}
export function paintAll(version: string, screen: string) {
  const m = editStore.get().drafts[version]?.[screen]; if (!m) return;
  for (const [id, e] of Object.entries(m)) paint(elOf(id), e);
}

export function resetElement(version: string, screen: string, id: string) {
  editStore.set((s) => { const sc = { ...s.drafts[version]?.[screen] }; delete sc[id]; return { drafts: { ...s.drafts, [version]: { ...s.drafts[version], [screen]: sc } } }; });
  bump();
  if (frame.doc) frame.doc.defaultView?.location.reload(); // simplest faithful reset: reload the original, then re-apply the remaining edits on load
}
export function discard(version: string) {
  editStore.set((s) => { const d = { ...s.drafts }; delete d[version]; return { drafts: d, sel: '' }; });
  if (frame.doc && frame.version === version) frame.doc.defaultView?.location.reload();
}

export function payload(version: string) {
  const out: Record<string, { design_id: string; style?: Record<string, string>; text?: string }[]> = {};
  for (const [screen, m] of Object.entries(editStore.get().drafts[version] || {})) {
    const list = Object.entries(m).map(([design_id, e]) => ({ design_id, ...(Object.keys(e.style).length ? { style: e.style } : {}), ...(e.text !== undefined ? { text: e.text } : {}) }))
      .filter((x) => x.style || x.text !== undefined);
    if (list.length) out[screen] = list;
  }
  return out;
}
export const countEdits = (version: string) => Object.values(payload(version)).reduce((n, l) => n + l.length, 0);

export function hexOf(css: string): string {
  const m = css.match(/rgba?\((\d+),\s*(\d+),\s*(\d+)(?:,\s*([\d.]+))?\)/); if (!m) return /^#[0-9a-f]{6}$/i.test(css) ? css : '#000000';
  if (m[4] !== undefined && Number(m[4]) === 0) return '#ffffff';
  return '#' + [m[1], m[2], m[3]].map((x) => Number(x).toString(16).padStart(2, '0')).join('');
}
export const isLeaf = (el: HTMLElement | null) => !!el && el.children.length === 0 && !['IMG', 'INPUT', 'HR', 'BR'].includes(el.tagName);
