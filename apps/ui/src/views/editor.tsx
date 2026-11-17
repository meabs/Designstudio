import { useEffect, useRef, useState } from 'react';
import { useSel, useUi, live, live as liveUrl, api, refresh } from '@/lib/store';
import { hasPhoneView } from '@/lib/frame';
import { editStore, frame, elOf, select, commit, styleOf, undo, redo, canUndo, canRedo, resetElements, discard, replay, payload, countEdits, logOf, hexOf, isLeaf, isVoid, docOrder, siblingId, type Pos } from '@/lib/edit';
import { useCurrent, navigate, boardPath } from '@/lib/router';
import { Button } from '@/components/ui/button';
import { Ic } from '@/components/app/icons';
import { toast } from '@/components/app/feedback';

type Box = { x: number; y: number; w: number; h: number };
const boxOf = (el: HTMLElement | null, k: number): Box | null => { if (!el) return null; const r = el.getBoundingClientRect(); return { x: r.left * k, y: r.top * k, w: r.width * k, h: r.height * k }; };
const useEditor = () => useSel(editStore, (s) => s);
const typing = (t: EventTarget | null) => !!(t as HTMLElement)?.closest?.('input,textarea,select,[contenteditable]') || !!document.querySelector('[data-slot=dialog-popup]');
const idUnder = (d: Document, x: number, y: number, skip: string[] = []) => {
  let c = d.elementFromPoint(x, y)?.closest('[data-design-id]') as HTMLElement | null;
  while (c && skip.some((s) => elOf(s)?.contains(c))) c = c.parentElement?.closest('[data-design-id]') as HTMLElement | null;
  return c?.dataset.designId || null;
};

/* Move the selection as a group, keeping its document order. */
export function moveGroup(v: string, screen: string, ids: string[], target: string, pos: Pos) {
  const order = docOrder(ids).filter((i) => i !== target); let anchor = target; let p: Pos = pos;
  for (const id of order) { commit(v, screen, { op: 'move', design_id: id, target_id: anchor, position: p }); if (pos === 'after') { anchor = id; p = 'after'; } }
}

/* The live screen with hover, selection and drop outlines. Scripts in the page stay off; the overlay takes every pointer event so links never navigate. */
export function EditCanvas({ v, screen, fr, width }: { v: any; screen: string; fr: { w: number; h: number }; width: number }) {
  const ed = useEditor(); const ref = useRef<HTMLIFrameElement>(null); const [hover, setHover] = useState(''); const k = width / fr.w;
  const [drop, setDrop] = useState<{ id: string; pos: Pos } | null>(null); const drag = useRef<{ x: number; y: number; id: string; on: boolean; free: boolean; base: Record<string, { l: number; t: number }> } | null>(null);
  const [inline, setInline] = useState('');
  const size = useRef<{ x: number; y: number; w: number; h: number; dir: string; id: string } | null>(null);
  useEffect(() => { frame.doc = null; frame.version = v.id; frame.screen = screen; }, [v.id, screen]);
  const onLoad = () => { const d = ref.current?.contentDocument || null; frame.doc = d; frame.version = v.id; frame.screen = screen; if (d) { replay(d, logOf(v.id, screen)); editStore.set((s) => ({ tick: s.tick + 1, sel: s.sel.filter((i) => !!elOf(i)) })); } };
  const at = (e: { clientX: number; clientY: number; currentTarget: Element }, skip: string[] = []) => {
    const d = frame.doc; if (!d) return null; const r = e.currentTarget.getBoundingClientRect(); const x = (e.clientX - r.left) / k, y = (e.clientY - r.top) / k;
    const id = idUnder(d, x, y, skip); return id ? { id, y } : null;
  };
  const dropAt = (e: React.PointerEvent, skip: string[]) => {
    const hit = at(e, skip); if (!hit) return null; const el = elOf(hit.id)!; const r = el.getBoundingClientRect();
    const pos: Pos = e.altKey && !isVoid(el) ? 'inside' : hit.y < r.top + r.height / 2 ? 'before' : 'after'; return { id: hit.id, pos };
  };

  const onDown = (e: React.PointerEvent) => {
    e.stopPropagation(); const hit = at(e); if (!hit) { if (!e.shiftKey) select([]); drag.current = null; return; }
    (e.currentTarget as Element).setPointerCapture(e.pointerId);
    if (e.shiftKey) select(ed.sel.includes(hit.id) ? ed.sel.filter((i) => i !== hit.id) : [...ed.sel, hit.id]);
    else if (!ed.sel.includes(hit.id)) select([hit.id]);
    const moving = editStore.get().sel.includes(hit.id) ? editStore.get().sel : [hit.id]; const base: Record<string, { l: number; t: number }> = {};
    for (const i of moving) { const s = elOf(i)?.style; base[i] = { l: parseFloat(s?.left || '0') || 0, t: parseFloat(s?.top || '0') || 0 }; }
    drag.current = { x: e.clientX, y: e.clientY, id: hit.id, on: false, free: editStore.get().free || e.ctrlKey || e.metaKey, base };
  };
  const onMove = (e: React.PointerEvent) => {
    const d = drag.current;
    if (d && (e.buttons & 1)) {
      if (!d.on && Math.hypot(e.clientX - d.x, e.clientY - d.y) > 5) d.on = true;
      if (d.on && d.free) { // free position: an offset from the element's normal place, so the flow around it is untouched
        const dx = Math.round((e.clientX - d.x) / k), dy = Math.round((e.clientY - d.y) / k);
        for (const [i, b] of Object.entries(d.base)) commit(v.id, screen, { design_id: i, style: { position: 'relative', left: `${b.l + dx}px`, top: `${b.t + dy}px` } });
        return;
      }
      if (d.on) { const moving = editStore.get().sel.includes(d.id) ? editStore.get().sel : [d.id]; setDrop(dropAt(e, moving)); return; }
    }
    setHover(at(e)?.id || '');
  };
  const onUp = (e: React.PointerEvent) => {
    const d = drag.current; drag.current = null; const dr = drop; setDrop(null);
    if (!d) return;
    if (d.on && d.free) return;
    if (d.on) { const moving = editStore.get().sel.includes(d.id) ? editStore.get().sel : [d.id]; const t = dr || dropAt(e, moving); if (t) moveGroup(v.id, screen, moving, t.id, t.pos); return; }
    if (!e.shiftKey && editStore.get().sel.length > 1 && editStore.get().sel.includes(d.id)) select([d.id]); // plain click inside a multi-selection narrows it
  };

  /* Double-click a text element to type on the canvas. Enter or clicking away keeps the text, Escape cancels. */
  const startInline = (id: string) => {
    const el = elOf(id); const doc = frame.doc; if (!el || !doc || !isLeaf(el)) return false;
    const before = el.textContent ?? ''; let cancelled = false; select([id]); setInline(id);
    try { el.setAttribute('contenteditable', 'plaintext-only'); if (el.contentEditable !== 'plaintext-only') el.setAttribute('contenteditable', 'true'); } catch { el.setAttribute('contenteditable', 'true'); }
    const noNav = (ev: Event) => ev.preventDefault(); // a click on a link while typing must not navigate the frame
    const key = (ev: KeyboardEvent) => { if (ev.key === 'Enter' && !ev.shiftKey) { ev.preventDefault(); el.blur(); } else if (ev.key === 'Escape') { ev.preventDefault(); cancelled = true; el.blur(); } };
    const done = () => {
      el.removeEventListener('keydown', key); doc.removeEventListener('click', noNav, true); el.removeAttribute('contenteditable'); setInline(''); ref.current?.blur(); window.focus(); // give the keys (Ctrl+Z) back to the editor
      const now = (el.textContent ?? '').replace(/\n/g, ' '); if (cancelled) el.textContent = before; else if (now !== before) commit(v.id, screen, { design_id: id, text: now }); else el.textContent = before;
    };
    el.addEventListener('keydown', key); doc.addEventListener('click', noNav, true); el.addEventListener('blur', done, { once: true });
    el.focus(); const r = doc.createRange(); r.selectNodeContents(el); const s = doc.defaultView!.getSelection(); s?.removeAllRanges(); s?.addRange(r);
    return true;
  };
  const sizeDown = (dir: string, id: string) => (e: React.PointerEvent) => {
    e.stopPropagation(); const el = elOf(id); if (!el) return; (e.currentTarget as Element).setPointerCapture(e.pointerId);
    const r = el.getBoundingClientRect(); size.current = { x: e.clientX, y: e.clientY, w: r.width, h: r.height, dir, id };
  };
  const sizeMove = (e: React.PointerEvent) => {
    const s = size.current; if (!s || !(e.buttons & 1)) return; e.stopPropagation(); const style: Record<string, string> = { 'box-sizing': 'border-box' };
    if (s.dir.includes('e')) style.width = `${Math.max(8, Math.round(s.w + (e.clientX - s.x) / k))}px`;
    if (s.dir.includes('s')) style.height = `${Math.max(8, Math.round(s.h + (e.clientY - s.y) / k))}px`;
    commit(v.id, screen, { design_id: s.id, style });
  };
  const sizeUp = (e: React.PointerEvent) => { e.stopPropagation(); size.current = null; };

  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (typing(e.target)) return; const sel = editStore.get().sel.filter((i) => !!elOf(i)); const mod = e.ctrlKey || e.metaKey; const kk = e.key.toLowerCase();
      if (mod && kk === 'z') { e.preventDefault(); e.shiftKey ? redo(v.id, screen) : undo(v.id, screen); return; }
      if (mod && kk === 'y') { e.preventDefault(); redo(v.id, screen); return; }
      if (!sel.length) return;
      if (kk === 'delete' || kk === 'backspace') { e.preventDefault(); docOrder(sel).reverse().forEach((id) => commit(v.id, screen, { op: 'delete', design_id: id })); return; }
      if (mod && kk === 'd') { e.preventDefault(); docOrder(sel).reverse().forEach((id) => commit(v.id, screen, { op: 'duplicate', design_id: id })); return; }
      if (e.altKey && (kk === 'arrowup' || kk === 'arrowdown') && sel.length === 1) { e.preventDefault(); nudge(v.id, screen, sel[0], kk === 'arrowup' ? 'prev' : 'next'); return; }
      if (kk === 'escape') select([]);
    };
    document.addEventListener('keydown', key); return () => document.removeEventListener('keydown', key);
  }, [v.id, screen]);

  void ed.tick;
  const sels = ed.sel.map((i) => ({ id: i, b: boxOf(elOf(i), k) })).filter((x) => x.b); const hov = hover && !ed.sel.includes(hover) ? boxOf(elOf(hover), k) : null;
  const db = drop ? boxOf(elOf(drop.id), k) : null;
  return (
    <div className="editcanvas relative overflow-hidden rounded border bg-white" data-edit-canvas style={{ width, height: Math.round(fr.h * k) }}>
      <iframe ref={ref} key={`${v.id}:${screen}`} title="Editable screen" sandbox="allow-same-origin" src={live(v, screen)} onLoad={onLoad} tabIndex={-1}
        style={{ width: fr.w, height: fr.h, border: 0, transformOrigin: '0 0', transform: `scale(${k})`, background: '#fff', pointerEvents: inline ? 'auto' : 'none' }} />
      <div className="absolute inset-0 cursor-default touch-none" data-edit-surface style={{ pointerEvents: inline ? 'none' : undefined }} onPointerDown={onDown} onPointerMove={onMove} onPointerUp={onUp} onPointerLeave={() => setHover('')}
        onDoubleClick={(e) => { const hit = at(e); if (hit && startInline(hit.id)) return; document.getElementById('edit-text')?.focus(); }}>
        {hov && <div className="pointer-events-none absolute border border-sky-500/70" style={{ left: hov.x, top: hov.y, width: hov.w, height: hov.h }} />}
        {sels.map(({ id, b }) => <div key={id} className="pointer-events-none absolute border-2 border-sky-600" data-edit-selection={id} style={{ left: b!.x, top: b!.y, width: b!.w, height: b!.h }}>{sels.length === 1 && <span className="absolute -top-5 left-0 whitespace-nowrap rounded bg-sky-600 px-1.5 text-[10px] text-white">{id}</span>}</div>)}
        {sels.length === 1 && (!isVoid(elOf(sels[0].id)) || elOf(sels[0].id)?.tagName === 'IMG') ? ([['e', 'cursor-ew-resize', { left: sels[0].b!.x + sels[0].b!.w - 5, top: sels[0].b!.y + sels[0].b!.h / 2 - 5 }], ['s', 'cursor-ns-resize', { left: sels[0].b!.x + sels[0].b!.w / 2 - 5, top: sels[0].b!.y + sels[0].b!.h - 5 }], ['se', 'cursor-nwse-resize', { left: sels[0].b!.x + sels[0].b!.w - 5, top: sels[0].b!.y + sels[0].b!.h - 5 }]] as const).map(([dir, cur, pos]) =>
          <div key={dir} data-edit-handle={dir} className={`absolute size-2.5 rounded-sm border-2 border-sky-600 bg-white ${cur}`} style={pos} onPointerDown={sizeDown(dir, sels[0].id)} onPointerMove={sizeMove} onPointerUp={sizeUp} />) : null}
        {drop && db && (drop.pos === 'inside'
          ? <div className="pointer-events-none absolute border-2 border-dashed border-emerald-600 bg-emerald-500/10" data-drop={`${drop.id}:inside`} style={{ left: db.x, top: db.y, width: db.w, height: db.h }} />
          : <div className="pointer-events-none absolute h-0.5 bg-emerald-600" data-drop={`${drop.id}:${drop.pos}`} style={{ left: db.x, width: db.w, top: drop.pos === 'before' ? db.y : db.y + db.h }} />)}
      </div>
    </div>
  );
}

function nudge(vid: string, screen: string, id: string, dir: 'prev' | 'next') {
  const sib = siblingId(id, dir); if (!sib) { toast(dir === 'prev' ? 'Already first among its siblings.' : 'Already last among its siblings.'); return; }
  commit(vid, screen, { op: 'move', design_id: id, target_id: sib, position: dir === 'prev' ? 'before' : 'after' });
}

const Row = ({ k, children }: { k: string; children: React.ReactNode }) => <div className="flex min-h-8 items-center justify-between gap-3 text-[13px]"><span className="text-muted-foreground">{k}</span><span className="flex items-center gap-1.5">{children}</span></div>;
const inputCls = 'h-7 rounded-md border bg-background px-2 text-[13px]';
const Tool = ({ label, icon, onClick, disabled, attr }: { label: string; icon: any; onClick: () => void; disabled?: boolean; attr: string }) =>
  <Button size="icon-xs" variant="outline" aria-label={label} title={label} disabled={disabled} {...{ [attr]: '' }} onClick={onClick}><Ic name={icon} size={13} /></Button>;

type Tok = [string, string]; // [token name, #hex]
const tokenValue = ([name, hex]: Tok) => `var(--${name}, ${hex})`; // the fallback keeps the page correct even where the token is not declared
function ColorField({ label, prop, cs, tokens, set }: { label: string; prop: string; cs: CSSStyleDeclaration; tokens: Tok[]; set: (p: string, v: string) => void }) {
  const val = hexOf(cs.getPropertyValue(prop)); const norm = (h: string) => h.toLowerCase().replace(/^#([0-9a-f])([0-9a-f])([0-9a-f])$/, '#$1$1$2$2$3$3');
  const used = tokens.find(([, hex]) => norm(hex) === val.toLowerCase()); const pick = (hex: string) => { const t = tokens.find(([, h]) => norm(h) === hex.toLowerCase()); set(prop, t ? tokenValue(t) : hex); };
  return (
    <Row k={label}>
      {used && <span data-edit-token-in-use className="mr-1 text-[11px] text-muted-foreground">{used[0]}</span>}
      {tokens.slice(0, 6).map((t) => <button key={t[0]} type="button" data-edit-token={t[0]} title={`Token ${t[0]} ${t[1]}`} aria-label={`Use token ${t[0]}`} className="size-4 rounded border" style={{ background: t[1] }} onClick={() => set(prop, tokenValue(t))} />)}
      <input type="color" aria-label={label} data-edit-prop={prop} value={val} onChange={(e) => pick(e.target.value)} className="size-7 cursor-pointer rounded border bg-background p-0.5" />
    </Row>
  );
}

/* Scale a picked image down so the whole draft stays small, as PNG when that fits, else JPEG. */
async function shrink(file: File): Promise<string> {
  const img = new Image(); // read as a data URL: the page's CSP allows data: images but not blob:
  const src = await new Promise<string>((ok, no) => { const r = new FileReader(); r.onload = () => ok(String(r.result)); r.onerror = () => no(Error('Could not read that file.')); r.readAsDataURL(file); });
  await new Promise((ok, no) => { img.onload = ok; img.onerror = () => no(Error('That file is not an image.')); img.src = src; });
  for (const max of [1200, 900, 640, 400]) {
    const k = Math.min(1, max / Math.max(img.width, img.height)); const c = document.createElement('canvas'); c.width = Math.max(1, Math.round(img.width * k)); c.height = Math.max(1, Math.round(img.height * k));
    const g = c.getContext('2d')!; g.fillStyle = '#fff'; if (file.type !== 'image/png') g.fillRect(0, 0, c.width, c.height); g.drawImage(img, 0, 0, c.width, c.height);
    for (const [type, q] of [['image/png', undefined], ['image/jpeg', 0.85]] as const) { const d = c.toDataURL(type, q); if (d.startsWith('data:' + type) && d.length < 880_000) return d; }
  }
  throw Error('That image is too large to add.');
}

type Piece = { id: string; label: string; html: string };
function FromScreen({ v, screen, ids }: { v: any; screen: string; ids: string[] }) {
  const screens: any[] = v.manifest?.screens || []; const [chosen, setSrc] = useState(''); const src = chosen || screen || screens[0]?.id || ''; const [pieces, setPieces] = useState<Piece[]>([]); const [pick, setPick] = useState('');
  useEffect(() => {
    let live_ = true; setPick('');
    fetch(liveUrl(v, src)).then((r) => r.text()).then((h) => {
      if (!live_) return; const d = new DOMParser().parseFromString(h, 'text/html');
      setPieces([...d.querySelectorAll<HTMLElement>('[data-design-id]')].filter((e) => !['HTML', 'BODY'].includes(e.tagName)).slice(0, 200).map((e) => ({ id: e.dataset.designId!, label: `${e.dataset.designId} · <${e.tagName.toLowerCase()}> ${(e.textContent || '').trim().replace(/\s+/g, ' ').slice(0, 28)}`, html: e.outerHTML })));
    }).catch(() => live_ && setPieces([]));
    return () => { live_ = false; };
  }, [v.id, src]);
  const go = () => { const p = pieces.find((x) => x.id === pick); if (!p || !ids.length) return; commit(v.id, screen, { op: 'component', source_screen: src, source_id: p.id, target_id: docOrder(ids).at(-1)!, position: 'after', html: p.html }); };
  return (
    <details className="mt-2.5 text-[13px]" data-edit-component>
      <summary className="cursor-pointer text-xs text-muted-foreground">Insert from another screen</summary>
      <div className="mt-1.5 flex flex-col gap-1.5">
        <select aria-label="Source screen" data-edit-source-screen className={inputCls} value={src} onChange={(e) => setSrc(e.target.value)}>{screens.map((s) => <option key={s.id} value={s.id}>{s.title}</option>)}</select>
        <select aria-label="Source element" data-edit-source-element className={inputCls} value={pick} onChange={(e) => setPick(e.target.value)}><option value="">Choose an element…</option>{pieces.map((p) => <option key={p.id} value={p.id}>{p.label}</option>)}</select>
        <Button size="xs" variant="outline" className="self-start" data-edit-insert-component disabled={!pick || !ids.length} onClick={go}><Ic name="plus" size={12} /> Insert after selection</Button>
        <p className="text-[11px] text-muted-foreground">Copies the element as it is in the saved version. Styles that come from a stylesheet only follow it if this screen has the same one.</p>
      </div>
    </details>
  );
}

export function EditPanel({ v, tokens }: { v: any; tokens: Record<string, any> }) {
  const ed = useEditor(); const { r, b } = useCurrent(); const [busy, setBusy] = useState(false); const view = useUi((s) => s.reviewView); const both = hasPhoneView(b);
  const scoped = both && ed.scope === 'view'; useEffect(() => { editStore.set({ at: scoped ? view : '' }); return () => editStore.set({ at: '' }); }, [scoped, view]);
  void ed.tick;
  const screen = frame.screen; const ids = ed.sel.filter((i) => !!elOf(i)); const el = elOf(ids[0] || ''); const n = countEdits(v.id); const one = ids.length === 1;
  const cs = el && frame.doc ? frame.doc.defaultView!.getComputedStyle(el) : null;
  const set = (p: string, val: string) => styleOf(v.id, screen, ids, { [p]: val });
  const px = (p: string) => Math.round(parseFloat(cs!.getPropertyValue(p)) || 0);
  const colors: Tok[] = Object.entries(tokens || {}).filter(([k, x]) => /^[\w-]+$/.test(k) && /^#[0-9a-f]{3,8}$/i.test(String(x))).map(([k, x]) => [k, String(x)]);
  const touched = logOf(v.id, screen).some((o) => !o.op && ids.includes(o.design_id || ''));
  const add = (kind: 'text' | 'button') => { if (!ids.length) return; commit(v.id, screen, { op: 'insert', target_id: docOrder(ids).at(-1)!, position: 'after', kind }); };
  const fileRef = useRef<HTMLInputElement>(null); const replaceRef = useRef<HTMLInputElement>(null);
  const addImage = async (f: File | undefined) => {
    if (!f || !ids.length) return; try { commit(v.id, screen, { op: 'insert', target_id: docOrder(ids).at(-1)!, position: 'after', kind: 'image', data_url: await shrink(f), alt: f.name.replace(/\.[^.]+$/, '').slice(0, 80) }); } catch (e: any) { toast(e.message); }
  };
  const replaceImage = async (f: File | undefined) => { if (!f || !one) return; try { commit(v.id, screen, { op: 'image', design_id: ids[0], data_url: await shrink(f) }); } catch (e: any) { toast(e.message); } };
  const save = async () => {
    setBusy(true);
    try { const res = await api('manual-edit', { variant_id: v.id, edits: payload(v.id) }); discard(v.id); await refresh(); toast(`Saved as v${res.version}. Accept or revert it like any revision.`); navigate(boardPath(r, b, 'review', res.id), { keepView: true }); }
    catch (e: any) { toast(e.message); } finally { setBusy(false); }
  };
  return (
    <div className="editpanel border-b px-4 py-3.5" data-edit-panel>
      <h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Edit</h3>
      <div className="mb-2.5 flex flex-wrap gap-1.5" role="toolbar" aria-label="Edit actions">
        <Tool attr="data-edit-undo" label="Undo (Ctrl+Z)" icon="undo" disabled={!canUndo(v.id, screen)} onClick={() => undo(v.id, screen)} />
        <Tool attr="data-edit-redo" label="Redo (Ctrl+Shift+Z)" icon="refresh" disabled={!canRedo(v.id, screen)} onClick={() => redo(v.id, screen)} />
        <span className="mx-0.5 w-px bg-border" />
        <Tool attr="data-edit-up" label="Move up (Alt+↑)" icon="back" disabled={!one} onClick={() => nudge(v.id, screen, ids[0], 'prev')} />
        <Tool attr="data-edit-down" label="Move down (Alt+↓)" icon="forward" disabled={!one} onClick={() => nudge(v.id, screen, ids[0], 'next')} />
        <Tool attr="data-edit-duplicate" label="Duplicate (Ctrl+D)" icon="layers" disabled={!ids.length} onClick={() => docOrder(ids).reverse().forEach((id) => commit(v.id, screen, { op: 'duplicate', design_id: id }))} />
        <Tool attr="data-edit-delete" label="Delete (Del)" icon="trash" disabled={!ids.length} onClick={() => docOrder(ids).reverse().forEach((id) => commit(v.id, screen, { op: 'delete', design_id: id }))} />
        <span className="mx-0.5 w-px bg-border" />
        <Button size="xs" variant="outline" data-edit-add="text" disabled={!ids.length} title="Add a text block after the selection" onClick={() => add('text')}><Ic name="plus" size={12} /> Text</Button>
        <Button size="xs" variant="outline" data-edit-add="button" disabled={!ids.length} title="Add a button after the selection" onClick={() => add('button')}><Ic name="plus" size={12} /> Button</Button>
        <Button size="xs" variant="outline" data-edit-add="image" disabled={!ids.length} title="Add a PNG or JPEG after the selection" onClick={() => fileRef.current?.click()}><Ic name="plus" size={12} /> Image</Button>
        <input ref={fileRef} type="file" accept="image/png,image/jpeg" hidden data-edit-image-input onChange={(e) => { void addImage(e.target.files?.[0]); e.target.value = ''; }} />
        <span className="mx-0.5 w-px bg-border" />
        <Button size="xs" variant={ed.free ? 'default' : 'outline'} aria-pressed={ed.free} data-edit-free title="Drag to offset an element from its place instead of reordering (or hold Ctrl while dragging)" onClick={() => editStore.set({ free: !ed.free })}>Free move</Button>
      </div>
      {both && <div className="mb-2 flex items-center gap-1.5 text-xs" role="group" aria-label="Where style changes apply">
        <span className="text-muted-foreground">Style changes apply to</span>
        {(['all', 'view'] as const).map((m) => <button key={m} type="button" data-edit-scope={m} aria-pressed={ed.scope === m} className={'h-6 rounded-md border px-2 ' + (ed.scope === m ? 'bg-foreground text-background' : 'bg-background')} onClick={() => editStore.set({ scope: m })}>{m === 'all' ? 'All widths' : view === 'm' ? 'Mobile only' : 'Desktop only'}</button>)}
      </div>}
      {scoped && <p className="mb-2 text-[11px] text-muted-foreground" data-edit-scope-note>{view === 'm' ? 'Applies at 600px wide and below.' : 'Applies above 600px wide.'} Switch the phone/desktop view above the canvas to check the other width.</p>}
      {!el || !cs ? <p className="text-xs text-muted-foreground">Click an element to edit it. Shift-click selects several; drag to reorder (hold Alt to drop inside); drag the handles to resize; double-click text to type. Changes stay in a draft until you save them as a new version; the original is never modified.</p> : (
        <div className="flex flex-col">
          <p className="mb-1.5 text-xs text-muted-foreground">{one ? `<${el.tagName.toLowerCase()}> · ${ids[0]}` : `${ids.length} elements selected`}</p>
          {one && isLeaf(el) && <textarea id="edit-text" data-edit-text aria-label="Text" rows={2} className="mb-1.5 w-full rounded-md border bg-background p-2 text-[13px]" value={el.textContent ?? ''} onChange={(e) => commit(v.id, screen, { design_id: ids[0], text: e.target.value })} />}
          <ColorField label="Text colour" prop="color" cs={cs} tokens={colors} set={set} />
          <ColorField label="Background" prop="background-color" cs={cs} tokens={colors} set={set} />
          <Row k="Font size"><input type="number" aria-label="Font size" data-edit-prop="font-size" min={8} max={120} className={inputCls + ' w-16'} value={px('font-size')} onChange={(e) => e.target.value && set('font-size', e.target.value + 'px')} /></Row>
          <Row k="Weight"><select aria-label="Weight" data-edit-prop="font-weight" className={inputCls} value={String(Math.round(Number(cs.fontWeight) / 100) * 100)} onChange={(e) => set('font-weight', e.target.value)}>{[300, 400, 500, 600, 700, 800].map((w) => <option key={w} value={w}>{w}</option>)}</select></Row>
          <Row k="Align">{(['left', 'center', 'right'] as const).map((a) => <button key={a} type="button" aria-pressed={cs.textAlign === a} data-edit-align={a} className={'h-7 rounded-md border px-2 text-xs ' + (cs.textAlign === a ? 'bg-foreground text-background' : 'bg-background')} onClick={() => set('text-align', a)}>{a}</button>)}</Row>
          {one && el.tagName === 'IMG' && <>
            <Row k="Alt text"><input key={ids[0]} aria-label="Alt text" data-edit-alt className={inputCls + ' w-36'} defaultValue={el.getAttribute('alt') || ''} onBlur={(e) => { if (e.target.value !== (el.getAttribute('alt') || '')) commit(v.id, screen, { op: 'image', design_id: ids[0], alt: e.target.value }); }} /></Row>
            <Row k="Picture"><Button size="xs" variant="outline" data-edit-replace-image onClick={() => replaceRef.current?.click()}>Replace…</Button><input ref={replaceRef} type="file" accept="image/png,image/jpeg" hidden onChange={(e) => { void replaceImage(e.target.files?.[0]); e.target.value = ''; }} /></Row>
          </>}
          <Row k="Width"><input type="number" aria-label="Width" data-edit-prop="width" min={0} max={3000} className={inputCls + ' w-20'} value={Math.round(el.getBoundingClientRect().width)} onChange={(e) => e.target.value && set('width', e.target.value + 'px')} /></Row>
          <Row k="Height"><input type="number" aria-label="Height" data-edit-prop="height" min={0} max={3000} className={inputCls + ' w-20'} value={Math.round(el.getBoundingClientRect().height)} onChange={(e) => e.target.value && set('height', e.target.value + 'px')} /></Row>
          <Row k="Radius"><input type="number" aria-label="Radius" data-edit-prop="border-radius" min={0} max={200} className={inputCls + ' w-16'} value={px('border-top-left-radius')} onChange={(e) => e.target.value && set('border-radius', e.target.value + 'px')} /></Row>
          <Row k="Padding"><input type="number" aria-label="Padding" data-edit-prop="padding" min={0} max={200} className={inputCls + ' w-16'} value={px('padding-top')} onChange={(e) => e.target.value && set('padding', e.target.value + 'px')} /></Row>
          <Row k="Opacity"><input type="range" aria-label="Opacity" data-edit-prop="opacity" min={0} max={1} step={0.05} value={Number(cs.opacity)} onChange={(e) => set('opacity', e.target.value)} /></Row>
          <Row k="Visible"><input type="checkbox" aria-label="Visible" data-edit-prop="display" checked={cs.display !== 'none'} onChange={(e) => set('display', e.target.checked ? '' : 'none')} /></Row>
          {touched && <Button size="xs" variant="outline" className="mt-2 self-start" data-edit-reset onClick={() => resetElements(v.id, screen, ids)}><Ic name="undo" size={12} /> Reset style and text</Button>}
        </div>
      )}
      <FromScreen v={v} screen={screen} ids={ids} />
      <div className="mt-3 flex items-center gap-2 border-t pt-3">
        <Button size="sm" className="primary" data-edit-save disabled={!n || busy} onClick={save}><Ic name="check" size={13} /> Save as new version{n ? ` (${n})` : ''}</Button>
        <Button size="sm" variant="outline" data-edit-discard disabled={!n || busy} onClick={() => discard(v.id)}>Discard</Button>
      </div>
      <p className="mt-1.5 text-[11px] text-muted-foreground">Drafts are kept in this browser and in the studio until saved, so they follow you to another browser. The studio re-runs its checks on the result.</p>
    </div>
  );
}
