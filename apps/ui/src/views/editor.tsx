import { useEffect, useRef, useState } from 'react';
import { useSel, live, api, refresh } from '@/lib/store';
import { editStore, frame, elOf, select, setEdit, resetElement, discard, paintAll, payload, countEdits, draftOf, hexOf, isLeaf } from '@/lib/edit';
import { useCurrent, navigate, boardPath } from '@/lib/router';
import { Button } from '@/components/ui/button';
import { Ic } from '@/components/app/icons';
import { toast } from '@/components/app/feedback';

type Box = { x: number; y: number; w: number; h: number };
const boxOf = (el: HTMLElement | null, k: number): Box | null => { if (!el) return null; const r = el.getBoundingClientRect(); return { x: r.left * k, y: r.top * k, w: r.width * k, h: r.height * k }; };
const useEditor = () => useSel(editStore, (s) => s);

/* The live screen with hover and selection outlines. Scripts in the page stay off; the overlay takes every click so links never navigate. */
export function EditCanvas({ v, screen, fr, width }: { v: any; screen: string; fr: { w: number; h: number }; width: number }) {
  const ed = useEditor(); const ref = useRef<HTMLIFrameElement>(null); const [hover, setHover] = useState(''); const k = width / fr.w;
  useEffect(() => { frame.doc = null; frame.version = v.id; frame.screen = screen; }, [v.id, screen]);
  const onLoad = () => { const d = ref.current?.contentDocument || null; frame.doc = d; frame.version = v.id; frame.screen = screen; if (d) { paintAll(v.id, screen); editStore.set((s) => ({ tick: s.tick + 1 })); } };
  const pick = (e: React.MouseEvent) => {
    const d = frame.doc; if (!d) return null; const r = e.currentTarget.getBoundingClientRect();
    return (d.elementFromPoint((e.clientX - r.left) / k, (e.clientY - r.top) / k)?.closest('[data-design-id]') as HTMLElement | null)?.dataset.designId || null;
  };
  void ed.tick;
  const sel = boxOf(elOf(ed.sel), k); const hov = hover && hover !== ed.sel ? boxOf(elOf(hover), k) : null;
  return (
    <div className="editcanvas relative overflow-hidden rounded border bg-white" data-edit-canvas style={{ width, height: Math.round(fr.h * k) }}>
      <iframe ref={ref} key={`${v.id}:${screen}`} title="Editable screen" sandbox="allow-same-origin" src={live(v, screen)} onLoad={onLoad} tabIndex={-1}
        style={{ width: fr.w, height: fr.h, border: 0, transformOrigin: '0 0', transform: `scale(${k})`, background: '#fff', pointerEvents: 'none' }} />
      <div className="absolute inset-0 cursor-default" onMouseMove={(e) => setHover(pick(e) || '')} onMouseLeave={() => setHover('')}
        onClick={(e) => { e.stopPropagation(); select(pick(e) || ''); }}
        onDoubleClick={() => { document.getElementById('edit-text')?.focus(); }}>
        {hov && <div className="pointer-events-none absolute border border-sky-500/70" style={{ left: hov.x, top: hov.y, width: hov.w, height: hov.h }} />}
        {sel && <div className="pointer-events-none absolute border-2 border-sky-600" data-edit-selection={ed.sel} style={{ left: sel.x, top: sel.y, width: sel.w, height: sel.h }}><span className="absolute -top-5 left-0 whitespace-nowrap rounded bg-sky-600 px-1.5 text-[10px] text-white">{ed.sel}</span></div>}
      </div>
    </div>
  );
}

const Row = ({ k, children }: { k: string; children: React.ReactNode }) => <div className="flex min-h-8 items-center justify-between gap-3 text-[13px]"><span className="text-muted-foreground">{k}</span><span className="flex items-center gap-1.5">{children}</span></div>;
const inputCls = 'h-7 rounded-md border bg-background px-2 text-[13px]';

function ColorField({ label, prop, cs, tokens, set }: { label: string; prop: string; cs: CSSStyleDeclaration; tokens: string[]; set: (p: string, v: string) => void }) {
  const val = hexOf(cs.getPropertyValue(prop));
  return (
    <Row k={label}>
      {tokens.slice(0, 6).map((t) => <button key={t} type="button" title={`Token ${t}`} aria-label={`Use ${t}`} className="size-4 rounded border" style={{ background: t }} onClick={() => set(prop, t)} />)}
      <input type="color" aria-label={label} data-edit-prop={prop} value={val} onChange={(e) => set(prop, e.target.value)} className="size-7 cursor-pointer rounded border bg-background p-0.5" />
    </Row>
  );
}

export function EditPanel({ v, tokens }: { v: any; tokens: Record<string, any> }) {
  const ed = useEditor(); const { r, b } = useCurrent(); const [busy, setBusy] = useState(false);
  void ed.tick;
  const screen = frame.screen; const el = elOf(ed.sel); const n = countEdits(v.id);
  const cs = el && frame.doc ? frame.doc.defaultView!.getComputedStyle(el) : null;
  const set = (p: string, val: string) => setEdit(v.id, screen, ed.sel, { style: { [p]: val } });
  const px = (p: string) => Math.round(parseFloat(cs!.getPropertyValue(p)) || 0);
  const colors = Object.values(tokens || {}).filter((x) => /^#[0-9a-f]{3,8}$/i.test(String(x))).map(String);
  const save = async () => {
    setBusy(true);
    try { const res = await api('manual-edit', { variant_id: v.id, edits: payload(v.id) }); discard(v.id); await refresh(); toast(`Saved as v${res.version}. Accept or revert it like any revision.`); navigate(boardPath(r, b, 'review', res.id), { keepView: true }); }
    catch (e: any) { toast(e.message); } finally { setBusy(false); }
  };
  return (
    <div className="editpanel border-b px-4 py-3.5" data-edit-panel>
      <h3 className="mb-2.5 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Edit selection</h3>
      {!el || !cs ? <p className="text-xs text-muted-foreground">Click an element on the screen to edit its text, colours, type and spacing. Changes stay in a draft until you save them as a new version; the original is never modified.</p> : (
        <div className="flex flex-col">
          <p className="mb-1.5 text-xs text-muted-foreground">&lt;{el.tagName.toLowerCase()}&gt; · {ed.sel}</p>
          {isLeaf(el) && <textarea id="edit-text" data-edit-text aria-label="Text" rows={2} className="mb-1.5 w-full rounded-md border bg-background p-2 text-[13px]" value={draftOf(v.id, screen, ed.sel)?.text ?? el.textContent ?? ''} onChange={(e) => setEdit(v.id, screen, ed.sel, { text: e.target.value })} />}
          <ColorField label="Text colour" prop="color" cs={cs} tokens={colors} set={set} />
          <ColorField label="Background" prop="background-color" cs={cs} tokens={colors} set={set} />
          <Row k="Font size"><input type="number" aria-label="Font size" data-edit-prop="font-size" min={8} max={120} className={inputCls + ' w-16'} value={px('font-size')} onChange={(e) => e.target.value && set('font-size', e.target.value + 'px')} /></Row>
          <Row k="Weight"><select aria-label="Weight" data-edit-prop="font-weight" className={inputCls} value={String(Math.round(Number(cs.fontWeight) / 100) * 100)} onChange={(e) => set('font-weight', e.target.value)}>{[300, 400, 500, 600, 700, 800].map((w) => <option key={w} value={w}>{w}</option>)}</select></Row>
          <Row k="Align">{(['left', 'center', 'right'] as const).map((a) => <button key={a} type="button" aria-pressed={cs.textAlign === a} data-edit-align={a} className={'h-7 rounded-md border px-2 text-xs ' + (cs.textAlign === a ? 'bg-foreground text-background' : 'bg-background')} onClick={() => set('text-align', a)}>{a}</button>)}</Row>
          <Row k="Radius"><input type="number" aria-label="Radius" data-edit-prop="border-radius" min={0} max={200} className={inputCls + ' w-16'} value={px('border-top-left-radius')} onChange={(e) => e.target.value && set('border-radius', e.target.value + 'px')} /></Row>
          <Row k="Padding"><input type="number" aria-label="Padding" data-edit-prop="padding" min={0} max={200} className={inputCls + ' w-16'} value={px('padding-top')} onChange={(e) => e.target.value && set('padding', e.target.value + 'px')} /></Row>
          <Row k="Opacity"><input type="range" aria-label="Opacity" data-edit-prop="opacity" min={0} max={1} step={0.05} value={Number(cs.opacity)} onChange={(e) => set('opacity', e.target.value)} /></Row>
          <Row k="Visible"><input type="checkbox" aria-label="Visible" data-edit-prop="display" checked={cs.display !== 'none'} onChange={(e) => set('display', e.target.checked ? '' : 'none')} /></Row>
          {draftOf(v.id, screen, ed.sel) && <Button size="xs" variant="outline" className="mt-2 self-start" data-edit-reset onClick={() => resetElement(v.id, screen, ed.sel)}><Ic name="undo" size={12} /> Reset this element</Button>}
        </div>
      )}
      <div className="mt-3 flex items-center gap-2 border-t pt-3">
        <Button size="sm" className="primary" data-edit-save disabled={!n || busy} onClick={save}><Ic name="check" size={13} /> Save as new version{n ? ` (${n})` : ''}</Button>
        <Button size="sm" variant="outline" data-edit-discard disabled={!n || busy} onClick={() => discard(v.id)}>Discard</Button>
      </div>
      <p className="mt-1.5 text-[11px] text-muted-foreground">Edits are text and inline-style overrides on identified elements. The studio re-runs its checks on the result.</p>
    </div>
  );
}
