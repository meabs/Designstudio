// Records the real Design Studio UI as high-quality clips: Chrome screencast frames -> ffmpeg (30 fps, h264).
import { chromium } from '@playwright/test';
import fs from 'node:fs'; import path from 'node:path'; import { execFileSync } from 'node:child_process';
export const ORIGIN = process.env.STUDIO_URL || 'http://localhost:5196';
export const OUT = path.resolve(process.env.CLIPS || new URL('../public/clips/', import.meta.url).pathname);
export const FFMPEG = process.env.FFMPEG || 'ffmpeg';
fs.mkdirSync(OUT, { recursive: true });
export const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
export const api = async (p, d) => { const r = await fetch(ORIGIN + '/api/' + p, d ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(d) } : {}); const x = await r.json(); if (!r.ok) throw new Error(p + ': ' + x.message); return x; };

const CURSOR = `(() => { const boot = () => { if (window.__cur) return; window.__cur = 1; const c = document.createElement('div'); c.id='__cur'; c.style.cssText='position:fixed;left:0;top:0;width:26px;height:26px;z-index:2147483647;pointer-events:none;transform:translate(-100px,-100px);transition:transform 0.05s linear;filter:drop-shadow(0 2px 3px rgba(0,0,0,.35))'; c.innerHTML='<svg width="26" height="26" viewBox="0 0 24 24"><path d="M5 3l14 8-6.2 1.6L9.6 19z" fill="#111" stroke="#fff" stroke-width="1.6" stroke-linejoin="round"/></svg>'; const r=document.createElement('div'); r.id='__rip'; r.style.cssText='position:fixed;left:0;top:0;width:34px;height:34px;margin:-17px 0 0 -17px;border-radius:50%;border:3px solid rgba(80,110,255,.9);z-index:2147483646;pointer-events:none;opacity:0;transform:scale(.3)'; document.documentElement.append(r,c);
 addEventListener('mousemove', e => { c.style.transform = 'translate(' + e.clientX + 'px,' + e.clientY + 'px)'; }, true);
 addEventListener('mousedown', e => { r.style.left=e.clientX+'px'; r.style.top=e.clientY+'px'; r.animate([{opacity:.9,transform:'scale(.3)'},{opacity:0,transform:'scale(1.6)'}],{duration:520,easing:'ease-out'}); }, true); }; document.readyState === 'loading' ? addEventListener('DOMContentLoaded', boot) : boot(); })();`;

export async function session(name, { width = 1536, height = 864, dsf = 1.25, mobile = false } = {}) {
  const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome', headless: true });
  const ctx = await browser.newContext({ viewport: { width, height }, deviceScaleFactor: dsf, ...(mobile ? { isMobile: true, hasTouch: true } : {}) });
  await ctx.addInitScript(CURSOR); await ctx.addInitScript(() => { try { localStorage.setItem('ds-promo', '1'); } catch {} });
  const page = await ctx.newPage(); const errors = [];
  page.on('pageerror', (e) => errors.push(e.message));
  const cdp = await ctx.newCDPSession(page); const dir = fs.mkdtempSync(path.join(OUT, `.${name}-`)); const frames = []; let n = 0;
  cdp.on('Page.screencastFrame', async (f) => { const file = path.join(dir, String(n++).padStart(6, '0') + '.jpg'); fs.writeFileSync(file, Buffer.from(f.data, 'base64')); frames.push({ file, t: f.metadata.timestamp }); try { await cdp.send('Page.screencastFrameAck', { sessionId: f.sessionId }); } catch {} });
  const w = Math.round(width * dsf), h = Math.round(height * dsf);
  const s = {
    page, ctx, errors, name,
    async start() { s.t0 = Date.now(); await cdp.send('Page.startScreencast', { format: 'jpeg', quality: 92, maxWidth: w, maxHeight: h, everyNthFrame: 1 }); },
    async stop() {
      await sleep(400); await cdp.send('Page.stopScreencast'); await ctx.close(); await browser.close();
      if (frames.length < 2) throw new Error('no frames captured for ' + name);
      // The screencast only emits frames when pixels change, so hold the last frame for however long the clip really ran.
      const wall = (Date.now() - s.t0) / 1000 - 0.4, seen = frames.at(-1).t - frames[0].t, tail = Math.max(0.1, wall - seen);
      const list = frames.map((f, i) => `file '${f.file}'\nduration ${Math.max(0.001, (frames[i + 1] ? frames[i + 1].t - f.t : tail)).toFixed(4)}`).join('\n') + `\nfile '${frames.at(-1).file}'\n`;
      fs.writeFileSync(path.join(dir, 'list.txt'), list); const out = path.join(OUT, name + '.mp4');
      execFileSync(FFMPEG, ['-v', 'error', '-y', '-f', 'concat', '-safe', '0', '-i', path.join(dir, 'list.txt'), '-vf', `fps=30,scale=${mobile ? w : 1920}:${mobile ? h : 1080}:flags=lanczos,format=yuv420p`, '-c:v', 'libx264', '-crf', '17', '-preset', 'medium', '-movflags', '+faststart', out]);
      fs.rmSync(dir, { recursive: true, force: true }); return { out, frames: frames.length, errors };
    },
    wait: sleep,
    async at(loc) { const b = await (typeof loc === 'string' ? page.locator(loc).first() : loc.first()).boundingBox(); if (!b) throw new Error('not visible: ' + loc); return { x: b.x + b.width / 2, y: b.y + b.height / 2, b }; },
    async move(loc, { dx = 0, dy = 0, steps = 28 } = {}) { const { x, y } = await s.at(loc); await page.mouse.move(x + dx, y + dy, { steps }); await sleep(150); },
    async click(loc, opts = {}) { const target = typeof loc === 'string' ? page.locator(loc).first() : loc.first(); await target.scrollIntoViewIfNeeded(); await s.move(target, opts); await sleep(180); await page.mouse.down(); await sleep(60); await page.mouse.up(); await sleep(opts.after ?? 450); },
    async type(loc, text, delay = 38) { const t = typeof loc === 'string' ? page.locator(loc).first() : loc.first(); await s.click(t, { after: 150 }); await t.pressSequentially(text, { delay }); await sleep(350); },
    async scroll(sel, to, ms = 900) { await page.evaluate(({ sel, to, ms }) => new Promise((res) => { const el = sel ? document.querySelector(sel) : document.scrollingElement; const from = el.scrollTop; const t0 = performance.now(); const tick = (t) => { const k = Math.min(1, (t - t0) / ms); el.scrollTop = from + (to - from) * (k < .5 ? 2 * k * k : 1 - Math.pow(-2 * k + 2, 2) / 2); k < 1 ? requestAnimationFrame(tick) : res(); }; requestAnimationFrame(tick); }), { sel, to, ms }); await sleep(200); },
    async goto(url) { await page.goto(url.startsWith('http') ? url : ORIGIN + url); await page.waitForLoadState('networkidle'); await sleep(900); },
  };
  return s;
}
