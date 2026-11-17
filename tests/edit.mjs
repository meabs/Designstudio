// End-to-end for direct editing: select an element on the live screen, change text and style, save as a new child version.
//   STUDIO_SEED_FIXTURES=1 STUDIO_STORAGE=$(mktemp -d) PORT=5197 python3 apps/api/server.py   then   STUDIO_URL=http://localhost:5197 node tests/edit.mjs
import { chromium } from '@playwright/test';
import assert from 'node:assert/strict';
const origin = process.env.STUDIO_URL || 'http://localhost:5197';
async function api(p, data) { const r = await fetch(origin + '/api/' + p, data ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) } : {}); const x = await r.json(); assert.ok(r.ok, p + ': ' + x.message); return x; }
const until = async (fn, what, ms = 90000) => { const end = Date.now() + ms; for (;;) { const x = await fn(); if (x) return x; assert.ok(Date.now() < end, 'timed out waiting for ' + what); await new Promise(r => setTimeout(r, 400)); } };
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome', headless: true });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage(); const errors = [];
page.on('pageerror', e => errors.push('pageerror: ' + e.message)); page.on('console', m => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) errors.push('console: ' + m.text()); });
let failed = 0; const step = async (name, fn) => { try { await fn(); console.log('ok  ' + name); } catch (e) { failed++; console.error('FAIL ' + name + '\n' + e.message); await page.screenshot({ path: '/tmp/edit-fail.png', fullPage: true }).catch(() => {}); } };
const st0 = await api('state'); const project = st0.project[0], board = st0.board[0]; const fx = st0.runner.filter(r => r.type === 'fixture');
await api('generate', { project_id: project.id, board_id: board.id, brief: board.brief, runner_ids: [fx[0].id], idempotency_key: 'edit-' + Date.now() });
const parent = await until(async () => (await api('state')).variant.find(v => v.board_id === board.id), 'a version');
const review = `${origin}/projects/${project.id}/boards/${board.id}/review/${parent.id}`;
await step('edit tool shows the live screen and an edit panel', async () => {
  await page.goto(review); await page.locator('[data-tool="edit"]').click(); await page.locator('[data-edit-canvas] iframe').waitFor();
  await page.locator('[data-edit-panel]').waitFor();
});
await step('click selects an identified element; text and colour edit live', async () => {
  const box = await page.locator('[data-edit-canvas]').boundingBox();
  const frame = page.frameLocator('[data-edit-canvas] iframe'); const h = frame.locator('h1[data-design-id], h2[data-design-id], [data-design-id]').first(); const id = await h.getAttribute('data-design-id');
  const hb = await frame.locator(`[data-design-id="${id}"]`).evaluate(el => { const r = el.getBoundingClientRect(); return { x: r.left + r.width / 2, y: r.top + r.height / 2 }; });
  const k = box.width / (await page.locator('[data-edit-canvas] iframe').evaluate(f => f.offsetWidth));
  await page.mouse.click(box.x + hb.x * k, box.y + hb.y * k);
  await page.locator('[data-edit-selection]').waitFor(); const sel = await page.locator('[data-edit-selection]').getAttribute('data-edit-selection');
  assert.ok(sel, 'something is selected');
  const leaf = await page.locator('[data-edit-text]').count();
  if (leaf) { await page.locator('[data-edit-text]').fill('Edited by hand'); assert.match(await frame.locator(`[data-design-id="${sel}"]`).innerText(), /Edited by hand/); }
  await page.locator('[data-edit-prop="font-size"]').fill('31'); assert.equal(await frame.locator(`[data-design-id="${sel}"]`).evaluate(el => getComputedStyle(el).fontSize), '31px');
  await page.locator('[data-edit-save]').waitFor(); assert.ok(await page.locator('[data-edit-save]').isEnabled());
  page.__sel = sel;
});
await step('save creates a pending child version; the parent is untouched', async () => {
  await page.locator('[data-edit-save]').click();
  const child = await until(async () => (await api('state')).variant.find(v => v.parent_id === parent.id), 'child version');
  assert.equal(child.review_state, 'pending'); assert.equal(child.kind, 'edit'); assert.equal(child.version, parent.version + 1);
  assert.ok(child.changed_screens.length === 1);
  const html = await (await fetch(`${origin}/assets/variants/${child.id}/screens/${child.changed_screens[0]}.html`)).text(); assert.match(html, /font-size: 31px/);
  const orig = await (await fetch(`${origin}/assets/variants/${parent.id}/screens/${child.changed_screens[0]}.html`)).text(); assert.doesNotMatch(orig, /font-size: 31px/);
  await until(async () => (await fetch(`${origin}/assets/variants/${child.id}/thumbnails/${child.changed_screens[0]}.png`)).ok, 'new screenshot');
  await page.waitForURL(new RegExp(child.id));
  assert.ok(await page.locator('[data-edit-save]').isDisabled(), 'draft cleared');
});

// ---- layout editing, undo/redo, multi-select, persistence ----
const canvas = page.locator('[data-edit-canvas]'); const frameLoc = page.frameLocator('[data-edit-canvas] iframe');
const scale = async () => (await canvas.boundingBox()).width / (await page.locator('[data-edit-canvas] iframe').evaluate(f => f.offsetWidth));
const centre = async (id, fy = 0.5) => { const r = await frameLoc.locator(`[data-design-id="${id}"]`).evaluate(el => { const b = el.getBoundingClientRect(); return { x: b.left, y: b.top, w: b.width, h: b.height }; }); const k = await scale(), c = await canvas.boundingBox(); return { x: c.x + (r.x + r.w / 2) * k, y: c.y + (r.y + r.h * fy) * k }; };
const click = async (id, shift) => { const p = await centre(id); if (shift) await page.keyboard.down('Shift'); await page.mouse.click(p.x, p.y); if (shift) await page.keyboard.up('Shift'); };
const order = async () => frameLoc.locator('[data-design-id]').evaluateAll(els => els.map(e => e.dataset.designId));
const visibleLeaves = async () => frameLoc.locator('[data-design-id]').evaluateAll(els => els.filter(e => e.children.length === 0 && e.getBoundingClientRect().height > 4).map(e => e.dataset.designId));
const fresh = async () => { await page.goto(review.replace(parent.id, (await api('state')).variant.filter(v => v.board_id === board.id && !v.parent_id)[0].id)); await page.locator('[data-tool="edit"]').click(); await page.locator('[data-edit-canvas] iframe').waitFor(); await page.waitForTimeout(600); };
await step('duplicate, then undo and redo', async () => {
  await fresh(); const leaves = await visibleLeaves(); const a = leaves[0]; const before = await order();
  await click(a); await page.locator('[data-edit-duplicate]').click(); const after = await order(); assert.equal(after.length, before.length + 1); assert.ok(after.includes(a + '-copy'));
  assert.ok(await page.locator(`[data-edit-selection="${a}-copy"]`).count(), 'copy is selected');
  await page.locator('[data-edit-undo]').click(); await page.waitForTimeout(700); assert.deepEqual(await order(), before);
  await page.locator('[data-edit-redo]').click(); await page.waitForTimeout(300); assert.ok((await order()).includes(a + '-copy'));
  await page.keyboard.press('Control+z'); await page.waitForTimeout(700); assert.deepEqual(await order(), before);
});
await step('delete with the keyboard; multi-select edits style on every element', async () => {
  const leaves = await visibleLeaves(); const [a, b] = leaves; await click(a); await click(b, true);
  assert.equal(await page.locator('[data-edit-selection]').count(), 2); await page.locator('[data-edit-prop="font-size"]').fill('27');
  for (const id of [a, b]) assert.equal(await frameLoc.locator(`[data-design-id="${id}"]`).evaluate(el => getComputedStyle(el).fontSize), '27px');
  await page.locator('[data-edit-prop="font-size"]').evaluate(e => e.blur()); await page.keyboard.press('Delete'); const o = await order(); assert.ok(!o.includes(a) && !o.includes(b));
  await page.locator('[data-edit-discard]').click(); await page.waitForTimeout(700); assert.ok((await order()).includes(a), 'discard restores the original');
});
await step('drag reorders siblings and shows a drop line', async () => {
  await fresh();
  const pair = await frameLoc.locator('[data-design-id]').evaluateAll(els => { for (const e of els) { let s = e.nextElementSibling; while (s && !s.dataset.designId) s = s.nextElementSibling; if (s && e.getBoundingClientRect().height > 4 && s.getBoundingClientRect().height > 4) return [e.dataset.designId, s.dataset.designId]; } return null; });
  assert.ok(pair, 'a pair of identified siblings'); const [a, b] = pair; const from = await centre(a), to = await centre(b, 0.9);
  await page.mouse.move(from.x, from.y); await page.mouse.down(); await page.mouse.move((from.x + to.x) / 2, (from.y + to.y) / 2, { steps: 4 }); await page.mouse.move(to.x, to.y, { steps: 4 });
  assert.ok(await page.locator('[data-drop]').count(), 'drop indicator visible'); await page.mouse.up();
  const o = await order(); assert.ok(o.indexOf(b) < o.indexOf(a), 'a now follows b');
});
await step('draft survives a reload, and saving replays structural edits on the server', async () => {
  const k = await page.locator('[data-edit-save]').textContent(); assert.match(k, /\(\d+\)/);
  await page.reload(); await page.locator('[data-tool="edit"]').click(); await page.locator('[data-edit-canvas] iframe').waitFor(); await page.waitForTimeout(700);
  assert.match(await page.locator('[data-edit-save]').textContent(), /\(\d+\)/, 'draft restored');
  const live = await order(); await click((await visibleLeaves())[0]); await page.locator('[data-edit-add="button"]').click(); assert.ok((await order()).some(i => i.startsWith('new-button-')));
  const want = await order();
  const before = (await api('state')).variant.length; await page.locator('[data-edit-save]').click();
  const child = await until(async () => (await api('state')).variant.find(v => v.parent_id && v.kind === 'edit' && v.changes.some(c => /added button/.test(c))), 'structural child');
  assert.ok(child.changes.some(c => /moved/.test(c)), 'move recorded'); assert.equal((await api('state')).variant.length, before + 1);
  const html = await (await fetch(`${origin}/assets/variants/${child.id}/screens/${child.changed_screens[0]}.html`)).text();
  const ids = [...html.matchAll(/data-design-id="([^"]+)"/g)].map(m => m[1]); assert.deepEqual(ids, want, 'server HTML matches what the browser showed');
  void live;
  assert.ok(!(child.validation.find(c => c.check.startsWith('Manual edit scope')) || { outcome: 'pass' }).outcome.includes('fail'), 'scope check passes');
});
await step('resize handles and free move change size and offset live', async () => {
  await fresh(); const a = (await visibleLeaves())[0]; await click(a);
  const w0 = await frameLoc.locator(`[data-design-id="${a}"]`).evaluate(el => el.getBoundingClientRect().width);
  const h = await page.locator('[data-edit-handle="e"]').boundingBox(); await page.mouse.move(h.x + 4, h.y + 4); await page.mouse.down(); await page.mouse.move(h.x - 36, h.y + 4, { steps: 5 }); await page.mouse.up();
  const w1 = await frameLoc.locator(`[data-design-id="${a}"]`).evaluate(el => el.getBoundingClientRect().width); assert.ok(w1 < w0 - 20, `narrower ${w0} -> ${w1}`);
  await page.locator('[data-edit-free]').click(); const p = await centre(a); await page.mouse.move(p.x, p.y); await page.mouse.down(); await page.mouse.move(p.x + 30, p.y + 20, { steps: 5 }); await page.mouse.up();
  const s = await frameLoc.locator(`[data-design-id="${a}"]`).evaluate(el => ({ pos: el.style.position, l: el.style.left, t: el.style.top })); assert.equal(s.pos, 'relative'); assert.ok(parseFloat(s.l) > 10 && parseFloat(s.t) > 5, JSON.stringify(s));
  await page.locator('[data-edit-free]').click();
});
await step('duplicating the primary action does not add a second one; images and components insert', async () => {
  await fresh(); const prim = await frameLoc.locator('[data-role="primary-action"][data-design-id]').first().getAttribute('data-design-id'); assert.ok(prim, 'fixture has an identified primary action');
  await click(prim); await page.locator('[data-edit-duplicate]').click();
  assert.equal(await frameLoc.locator('[data-role="primary-action"]').count(), 1, 'the copy is not a primary action');
  const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAQAAAAEAQMAAACTPww9AAAAA1BMVEUAAACnej3aAAAAAXRSTlMAQObYZgAAAApJREFUCNdjYAAAAAIAAeIhvDMAAAAASUVORK5CYII=', 'base64');
  await page.locator('[data-edit-image-input]').setInputFiles({ name: 'dot.png', mimeType: 'image/png', buffer: png }); await page.waitForTimeout(500);
  assert.ok((await order()).includes('new-image-1'), 'image inserted'); assert.ok(await page.locator('[data-edit-handle="se"]').count(), 'image can be resized');
  await page.locator('[data-edit-alt]').fill('A dot'); await page.locator('[data-edit-alt]').blur(); assert.equal(await frameLoc.locator('[data-design-id="new-image-1"]').getAttribute('alt'), 'A dot');
  await page.locator('[data-edit-component] summary').click(); const opts = await page.locator('[data-edit-source-element] option').allTextContents(); assert.ok(opts.length > 2, 'elements listed');
  await page.locator('[data-edit-source-element]').selectOption({ index: 1 }); await click('new-image-1'); const n0 = (await order()).length; await page.locator('[data-edit-insert-component]').click(); 
  assert.ok((await order()).length > n0, 'component inserted');
  await page.waitForTimeout(1200); const root = (await api('state')).variant.filter(v => v.board_id === board.id && !v.parent_id)[0].id; const d = await api('draft-get', { variant_id: root }); assert.ok(Object.values(d.logs).flat().length >= 3, 'the studio holds the draft too');
  const want = await order(); await page.locator('[data-edit-save]').click();
  const child = await until(async () => (await api('state')).variant.find(v => v.parent_id && v.changes.some(c => /added image/.test(c))), 'image child');
  const html = await (await fetch(`${origin}/assets/variants/${child.id}/screens/${child.changed_screens[0]}.html`)).text();
  assert.deepEqual([...html.matchAll(/data-design-id="([^"]+)"/g)].map(m => m[1]), want, 'server HTML matches the browser');
  const src = html.match(/data-design-id="new-image-1" src="([^"]+)"/)[1]; assert.ok((await fetch(`${origin}/assets/variants/${child.id}/screens/${src}`)).ok, 'image file is served');
  assert.equal([...html.matchAll(/data-role="primary-action"/g)].length, 1);
  await page.waitForTimeout(1200); assert.equal(Object.keys((await api('draft-get', { variant_id: root })).logs).length, 0, 'draft cleared on save');
});
await step('no console errors', async () => { assert.deepEqual(errors, []); });
await browser.close(); process.exit(failed ? 1 : 0);
