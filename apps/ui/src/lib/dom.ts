import { live } from './store';
// Hidden, script-disabled frames at screenshot size, used to resolve geometry and stable element ids.
type Fr = { w: number; h: number };
function hiddenFrame<T>(v: any, screenId: string, read: (doc: Document) => T, fallback: T, fr: Fr = { w: 720, h: 960 }): Promise<T> {
  return new Promise((resolve) => {
    const f = document.createElement('iframe'); let done = false;
    const finish = (r: T) => { if (done) return; done = true; f.remove(); resolve(r); };
    f.setAttribute('sandbox', 'allow-same-origin'); f.setAttribute('aria-hidden', 'true'); f.tabIndex = -1;
    f.style.cssText = 'position:fixed;left:-9999px;top:0;width:' + fr.w + 'px;height:' + fr.h + 'px;border:0;visibility:hidden';
    f.onload = () => { try { finish(read(f.contentDocument as Document)); } catch { finish(fallback); } };
    f.src = live(v, screenId); document.body.appendChild(f); setTimeout(() => finish(fallback), 4000);
  });
}
export const elementAt = (v: any, screenId: string, x: number, y: number, fr: Fr = { w: 720, h: 960 }) =>
  hiddenFrame<string | null>(v, screenId, (d) => (d.elementFromPoint(x * fr.w, y * fr.h)?.closest('[data-design-id]') as HTMLElement | null)?.dataset.designId || null, null, fr);
const rectCache: Record<string, Record<string, { x: number; y: number; w: number; h: number }>> = {};
export async function elementRects(v: any, screenId: string, fr: Fr = { w: 720, h: 960 }) {
  const key = `${v.id}:${screenId}:${fr.w}x${fr.h}`; if (rectCache[key]) return rectCache[key];
  const out = await hiddenFrame(v, screenId, (d) => {
    const o: Record<string, { x: number; y: number; w: number; h: number }> = {};
    d.querySelectorAll<HTMLElement>('[data-design-id]').forEach((el) => { const r = el.getBoundingClientRect(); o[el.dataset.designId as string] = { x: r.left / fr.w, y: r.top / fr.h, w: r.width / fr.w, h: r.height / fr.h }; });
    return o;
  }, {}, fr);
  rectCache[key] = out; return out;
}
export const FRAME_W = 260; export const FLOW_W = 44; export const ZMIN = 25; export const ZMAX = 200;
export function fitZoom(mode: string) {
  const c = document.querySelector('.canvas') as HTMLElement | null; if (!c) return 100;
  if (mode === 'review') return Math.floor(((window.innerHeight - 320) * 0.75) / 560 * 100);
  const frames = Math.max(1, ...[...document.querySelectorAll('.frames')].map((f) => f.querySelectorAll('.fframe').length));
  return Math.floor((c.clientWidth - 90) / (frames * FRAME_W + (frames - 1) * FLOW_W + 48) * 100);
}
