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
await step('no console errors', async () => { assert.deepEqual(errors, []); });
await browser.close(); process.exit(failed ? 1 : 0);
