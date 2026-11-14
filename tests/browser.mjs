// End-to-end happy path plus failure handling, driven through the real UI.
// Run against a disposable server:  STUDIO_STORAGE=$(mktemp -d) PORT=5199 python3 apps/api/server.py
//   STUDIO_URL=http://localhost:5199 node tests/browser.mjs
// Uses fixture runners only; never calls a real coding agent.
import { chromium } from '@playwright/test';
import assert from 'node:assert/strict';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
const REF_DIR = process.env.REF_DIR || fileURLToPath(new URL('../fixtures/sample-project/references/', import.meta.url));
const refFile = n => path.join(REF_DIR, n);
const origin = process.env.STUDIO_URL || 'http://localhost:5173';
async function api(path, data) {
  const r = await fetch(origin + '/api/' + path, data ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) } : {});
  const x = await r.json(); assert.ok(r.ok, path + ': ' + x.message); return x;
}
const until = async (fn, what, ms = 90000) => { const end = Date.now() + ms; for (;;) { const x = await fn(); if (x) return x; assert.ok(Date.now() < end, 'timed out waiting for ' + what); await new Promise(r => setTimeout(r, 400)); } };
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome', headless: true });
const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, acceptDownloads: true });
const page = await ctx.newPage(); const errors = [];
page.on('pageerror', e => errors.push('pageerror: ' + e.message)); page.on('console', m => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) errors.push('console: ' + m.text()); });
const step = async (name, fn) => { try { await fn(); console.log('ok  ' + name); } catch (e) { console.error('FAIL ' + name + '\n' + e.message); await page.screenshot({ path: '/tmp/studio-fail.png', fullPage: true }).catch(() => {}); await browser.close(); process.exit(1); } };
const toastText = () => page.locator('#toast').textContent();
let project, board, parentVariant;

await step('create project and land on context', async () => {
  await page.goto(origin + '/projects'); await page.getByRole('button', { name: 'New project' }).click();
  await page.locator('#np-name').fill('E2E ' + Date.now()); await page.getByRole('button', { name: 'Create project' }).click();
  await page.getByRole('heading', { name: 'Design context' }).waitFor();
  project = (await api('state')).project.at(-1);
});
await step('context: preview, tokens table, stable rules, versioned save, dedupe, diff', async () => {
  const url = page.url(); assert.match(url, /\/context$/);
  await page.locator('#guidelines').fill('# Rules\n\n- Use **calm** copy\n- Explain why we ask');
  assert.match(await page.locator('#md-preview').innerHTML(), /<h2>Rules<\/h2>.*<strong>calm<\/strong>/s);
  await page.getByRole('button', { name: 'Add rule' }).click(); await page.locator('#r-id').fill('CTA-001'); await page.locator('#r-desc').fill('Job-level: still one primary action'); await page.locator('#r-scope').selectOption('job'); await page.locator('#r-just').fill('Stricter for this journey'); await page.locator('#r-ver').selectOption('deterministic'); await page.getByRole('button', { name: 'Save rule' }).click();
  await page.locator('#effective .conflict').getByText('overrides').waitFor();
  await page.locator('#quick-rules').fill('Use friendly tone\nAvoid jargon'); await page.getByRole('button', { name: 'Add instructions as rules' }).click();
  await page.locator('#rules table.rules').getByText('GUIDANCE-002', { exact: true }).waitFor();
  assert.ok(await page.locator('#token-table .swatch').count() > 0, 'token swatches');
  await page.locator('#tokens-json').fill('{"accent":"#aa3355"'); assert.match(await page.locator('#token-err').textContent(), /valid flat JSON/); assert.ok(await page.locator('[data-action="save-context"]').isDisabled());
  await page.locator('#tokens-json').fill('{"accent":"#aa3355","ink":"#202b24"}'); assert.equal(await page.locator('#token-err').textContent(), '');
  await page.locator('[data-action="save-context"]').click(); await page.getByText('Saved · version 2').waitFor();
  assert.ok(await page.locator('[data-action="save-context"]').isDisabled(), 'no-op save disabled');
  const state = await api('state'); const versions = state.context.filter(c => c.project_id === project.id); assert.equal(versions.length, 2);
  await page.locator('#versions summary').nth(0).click(); await page.locator('#versions details[open] .diff').first().waitFor();
});
await step('references: upload, validate, select for research', async () => {
  await page.goto(`${origin}/projects/${project.id}/research`); await page.locator('#research-refs [data-ref-upload]').setInputFiles(['brand-moodboard.png', 'competitor-form.png', 'flow-sketch.png'].map(refFile));
  await until(async () => (await page.locator('#research-refs .refitem').count()) === 3, 'three references in picker');
  assert.equal((await api('state')).reference.filter(r => r.project_id === project.id).length, 3);
  await page.locator('#research-refs .refitem').nth(2).locator('input').uncheck(); assert.equal(await page.locator('#research-refs input[name=references]:checked').count(), 2);
  const bad = await fetch(origin + '/api/reference-upload', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ project_id: project.id, name: 'x', data: Buffer.from('<svg onload=alert(1)>').toString('base64') }) }); assert.equal(bad.status, 400);
});
await step('research: empty question rejected, URL source kept as supplied, references sent', async () => {
  await page.getByRole('button', { name: 'Run research' }).click(); await until(async () => /question/i.test(await toastText()), 'toast');
  await page.locator('#research-brief').fill('Clear eligibility patterns'); await page.locator('#sources').fill('https://example.org/reference\nA pasted excerpt');
  await page.getByRole('button', { name: 'Run research' }).click();
  await page.getByText('Research ready', { exact: false }).first().waitFor(); await page.getByText('Synthetic · Unverified').first().waitFor();
  assert.ok(await page.locator('.research-result a[href="https://example.org/reference"]').count() === 1);
  const rj = (await api('state')).job.find(j => j.type === 'research' && j.project_id === project.id); assert.equal(rj.references.length, 2); assert.equal(await page.locator('.research-result .refthumb').count(), 2);
});
await step('research → new board with two fixture runners preselected', async () => {
  await page.locator('[data-handoff]').click();
  assert.equal(await page.locator('#modal-form input[name="runners"]:checked').count(), 2); assert.equal(await page.locator('#modal-form input[name="references"]:checked').count(), 2, 'research references preselected');
  await page.locator('#h-title').fill('Application Journey'); await page.getByRole('button', { name: 'Continue' }).click();
  await page.getByRole('heading', { name: 'Application Journey' }).waitFor(); board = (await api('state')).board.find(b => b.project_id === project.id);
  await page.getByText('research findings carried into this board', { exact: false }).waitFor();
  assert.equal(board.reference_ids.length, 2);
});
await step('two variants generate without credentials; screenshots render; no polling flicker', async () => {
  await until(async () => (await api('state')).variant.filter(v => v.board_id === board.id).length === 2, 'two variants');
  await page.locator('.variant').nth(1).waitFor(); await page.waitForFunction(() => [...document.querySelectorAll('.thumbnail img')].length >= 6 && [...document.querySelectorAll('.thumbnail img')].every(i => i.complete && i.naturalWidth > 0));
  await page.locator('.workspace').evaluate(e => { e.scrollTop = 120; }); await new Promise(r => setTimeout(r, 4200));
  assert.ok(await page.locator('.workspace').evaluate(e => e.scrollTop) >= 100 || await page.locator('.workspace').evaluate(e => e.scrollHeight <= e.clientHeight), 'scroll position must survive polling');
  const vs = (await api('state')).variant.filter(v => v.board_id === board.id); parentVariant = vs.find(v => v.style === 'b');
  assert.ok(vs.some(v => v.validation.some(x => x.outcome === 'fail')), 'deliberate rule failure visible');
});
await step('references reach every agent job, its task text, and the variant inspector', async () => {
  const st = await api('state'), jobs = st.job.filter(j => j.board_id === board.id && j.type === 'generate_board'); assert.equal(jobs.length, 2);
  for (const j of jobs) { assert.equal(j.references.length, 2); const task = await (await fetch(`${origin}/assets/jobs/${j.id}/TASK.md`)).text(); assert.match(task, /Reference images/); assert.match(task, new RegExp('references/' + j.references[0].file.replace('.', '\\.'))); const img = await fetch(`${origin}/assets/jobs/${j.id}/references/${j.references[0].file}`); assert.equal(img.status, 200); assert.equal(img.headers.get('content-type'), 'image/png'); }
  assert.equal(jobs[0].input_hash, jobs[1].input_hash, 'identical shared input incl. references');
  const v = st.variant.find(x => x.board_id === board.id && x.style === 'b'); assert.equal(v.references.length, 2); assert.ok(v.validation.some(x => /Reference images/.test(x.check) && x.outcome === 'review'));
  await page.goto(`${origin}/projects/${project.id}/boards/${board.id}`); await page.locator('.fframe').first().click(); await page.locator('.refthumb').first().click(); await page.locator('#dialog img.lightbox').waitFor(); await page.locator('#close-dialog').click();
});
await step('compare: pick any pair, filmstrip', async () => {
  await page.goto(`${origin}/projects/${project.id}/boards/${board.id}/compare`); await page.locator('.compare-grid img').first().waitFor();
  assert.equal(await page.locator('[data-compare-side]').count(), 2); assert.ok(await page.locator('.filmstrip .film').count() >= 6);
});
let revisionId;
await step('review: variant route, pin with stable element anchor, edit & delete pin', async () => {
  await page.goto(`${origin}/projects/${project.id}/boards/${board.id}/review/${parentVariant.id}`); await page.locator('#pin-area img').waitFor();
  const box = await page.locator('#pin-area img').boundingBox(); await page.locator('#pin-area').click({ position: { x: box.width * .5, y: box.height * .17 } });
  await page.locator('#pin-comment').waitFor(); assert.match(await page.locator('#pin-anchor').textContent(), /anchored to element “heading”|no stable element/);
  await page.locator('#pin-comment').fill('Move the explanatory text below the heading.'); await page.locator('#modal-form').getByRole('button', { name: 'Add comment' }).click();
  await page.locator('.pin').first().waitFor(); await page.getByRole('tab', { name: /Comments/ }).click(); await page.locator('.pop').waitFor();
  await page.locator('[data-pin-edit]').first().click(); await page.locator('#pe-c').fill('Move the explanatory text below the heading, please.'); await page.locator('#modal-form').getByRole('button', { name: 'Save' }).click(); await page.getByText('please.').first().waitFor();
  await page.locator('#pin-area').click({ position: { x: 20, y: 20 } }); await page.locator('#pin-comment').fill('temp'); await page.locator('#modal-form').getByRole('button', { name: 'Add comment' }).click();
  await page.locator('.pinrow', { hasText: 'temp' }).locator('[data-pin-delete]').click(); await page.locator('#modal-form').getByRole('button', { name: 'Delete pin' }).click(); await until(async () => (await page.locator('[data-pin-delete]').count()) === 1, 'pin deleted');
  const ann = (await api('state')).annotation.filter(a => a.variant_id === parentVariant.id); assert.equal(ann.length, 1); assert.ok(ann[0].element_id === 'heading' || ann[0].element_id === null);
});
await step('revise → child version pending; parent untouched; changed screens flagged; revert then re-revise and accept', async () => {
  await page.getByRole('button', { name: /Revise selection \(1 pin\)/ }).click(); await page.locator('.variant').first().waitFor();
  const child = await until(async () => (await api('state')).variant.find(v => v.parent_id === parentVariant.id), 'revision'); revisionId = child.id;
  assert.ok(child.revision_scope['0'], 'revision records its scope'); assert.ok(child.changed_regions['0'].elements.length > 0, 'changed regions recorded');
  assert.equal(child.review_state, 'pending'); assert.equal(child.references.length, 2, 'revisions inherit the board references'); assert.deepEqual(child.changed_screens, ['0']);
  await page.goto(`${origin}/projects/${project.id}/boards/${board.id}`); await page.locator(`[data-variant="${child.id}"]`).waitFor();
  await page.locator(`[data-variant="${child.id}"] [data-revert]`).click(); await page.locator('#modal-form').getByRole('button', { name: 'Revert revision' }).click();
  await until(async () => (await api('state')).variant.find(v => v.id === child.id).review_state === 'reverted', 'reverted'); await page.waitForFunction(id => !document.querySelector(`[data-variant="${id}"]`), child.id);
  assert.equal((await api('state')).variant.find(v => v.id === parentVariant.id).review_state ?? null, null, 'parent untouched');
  await page.goto(`${origin}/projects/${project.id}/boards/${board.id}/review/${parentVariant.id}`); await page.locator('#pin-area img').waitFor();
  await page.locator('#pin-area').click({ position: { x: 100, y: 200 } }); await page.locator('#pin-comment').fill('Make the button label clearer.'); await page.locator('#modal-form').getByRole('button', { name: 'Add comment' }).click(); await page.locator('.pin:not(.applied)').first().waitFor();
  await page.getByRole('button', { name: /Revise selection/ }).click();
  const child2 = await until(async () => (await api('state')).variant.find(v => v.parent_id === parentVariant.id && v.id !== child.id), 'second revision'); revisionId = child2.id;
  await page.goto(`${origin}/projects/${project.id}/boards/${board.id}/compare?left=${parentVariant.id}&right=${child2.id}`); await page.getByText('Changed in this screen').waitFor();
  await page.goto(`${origin}/projects/${project.id}/boards/${board.id}/review/${child2.id}`); await page.locator('.regions .region').first().waitFor(); assert.ok(await page.locator('.regions .region').count() >= 1, 'changed regions outlined'); await page.getByRole('button', { name: /Before \(v/ }).click(); await page.locator('#pin-area img').waitFor();
  await page.getByRole('button', { name: /Accept revision/ }).click(); await until(async () => (await api('state')).variant.find(v => v.id === child2.id).review_state === 'accepted', 'accepted');
});
await step('checks: deterministic evidence separate; human review can be completed', async () => {
  await page.goto(`${origin}/projects/${project.id}/boards/${board.id}/review/${parentVariant.id}`);
  await page.getByRole('tab', { name: /Checks/ }).click(); await page.getByText('Failed deterministic checks').waitFor(); await page.getByText('Needs designer review').first().waitFor();
  const before = await page.locator('[data-review-check][data-decision="accepted"]').count(); assert.ok(before > 0);
  await page.locator('[data-review-check][data-decision="accepted"]').first().click(); await page.getByText('Reviewed · OK').first().waitFor();
});
await step('approve → locked, prototype built, player controls work', async () => {
  await page.goto(`${origin}/projects/${project.id}/boards/${board.id}/review/${revisionId}`); await page.getByRole('button', { name: /Approve & build prototype/ }).click();
  await page.locator('#modal-form').getByRole('button', { name: 'Approve & build' }).click(); await page.locator('#player').waitFor();
  assert.match(page.url(), /\/prototypes\/[0-9a-f]{16}$/); const frame = page.frameLocator('#player');
  await frame.locator('[data-role="primary-action"]').first().waitFor(); assert.match(await page.locator('#player-info').textContent(), /screen 1 of 3/);
  await frame.locator('[data-role="primary-action"]').first().click(); await until(async () => /screen 2 of 3/.test(await page.locator('#player-info').textContent()), 'screen 2');
  await frame.getByText('Try a validation state').click(); await frame.locator('#error').waitFor({ state: 'visible' });
  await page.getByRole('button', { name: 'Default' }).click(); await frame.locator('#error').waitFor({ state: 'hidden' }); await page.getByRole('button', { name: 'Error' }).click(); await frame.locator('#error').waitFor({ state: 'visible' });
  await page.getByRole('button', { name: /Back/ }).first().click(); await until(async () => /screen 1 of 3/.test(await page.locator('#player-info').textContent()), 'back to screen 1');
  await page.getByRole('button', { name: 'Forward' }).click(); await until(async () => /screen 2 of 3/.test(await page.locator('#player-info').textContent()), 'forward');
  await page.locator('[data-device="mobile"]').click(); assert.equal(Math.round((await page.locator('#player').boundingBox()).width), 370); assert.match(await page.locator('#player-info').textContent(), /390px/);
  const [download] = await Promise.all([page.waitForEvent('download'), page.getByRole('link', { name: /Export ZIP/ }).click()]); assert.ok((await download.path()), 'zip downloaded');
  const st = await api('state'); assert.equal(st.prototype.filter(p => p.variant_id === revisionId).length, 1);
  await api('approve', { id: revisionId }); assert.equal((await api('state')).prototype.filter(p => p.variant_id === revisionId).length, 1, 'approval is idempotent');
});
await step('approved version is locked; other versions cannot be reverted over it', async () => {
  const r = await fetch(origin + '/api/revert-revision', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ id: revisionId }) }); assert.equal(r.status, 400);
  await page.goto(`${origin}/projects/${project.id}/boards/${board.id}/review/${revisionId}`); await page.locator('.lockline').getByText('Approved and locked').waitFor();
});
await step('share link: create, open read-only on the share port, expiry list, revoke', async () => {
  const cfg = await (await fetch(origin + '/api/config')).json(); if (!cfg.share_port) { console.log('skip share (start the server with STUDIO_SHARE_PORT to test)'); return; }
  const proto = (await api('state')).prototype.find(p => p.board_id === board.id); await page.goto(`${origin}/projects/${project.id}/prototypes/${proto.id}`); await page.getByRole('button', { name: /Share/ }).click();
  await page.locator('#share-exp').selectOption('1'); await page.locator('#modal-form').getByRole('button', { name: 'Create link' }).click(); await page.locator('[data-share-input]').waitFor();
  const link = await page.locator('[data-share-input]').first().inputValue(); assert.match(link, /\/s\/[A-Za-z0-9_-]{20,}\/$/); const shareOrigin = new URL(link).origin;
  const viewer = await ctx.newPage(); await viewer.goto(link); await viewer.getByText('Read-only share').waitFor(); await viewer.frameLocator('#f').locator('[data-role="primary-action"]').first().waitFor();
  await until(async () => /screen 1 of 3/.test(await viewer.locator('#info').textContent()), 'viewer info'); await viewer.frameLocator('#f').locator('[data-role="primary-action"]').first().click(); await until(async () => /screen 2 of 3/.test(await viewer.locator('#info').textContent()), 'viewer navigation');
  assert.equal((await fetch(shareOrigin + '/api/state')).status, 404); assert.equal((await fetch(shareOrigin + '/')).status, 404);
  await page.locator('[data-share-revoke]').first().click(); await until(async () => (await fetch(link)).status === 410, 'revoked link gone'); await viewer.close();
});
await step('mix screens from different versions into a new immutable version', async () => {
  await page.goto(`${origin}/projects/${project.id}/boards/${board.id}`); await page.getByRole('button', { name: /Mix screens/ }).click(); await page.locator('.mixgrid').waitFor();
  const before = (await api('state')).variant.length; await page.locator('#modal-form').getByRole('button', { name: 'Create mixed version' }).click();
  const m = await until(async () => (await api('state')).variant.find(v => v.kind === 'mix' && v.board_id === board.id), 'mixed version'); assert.equal((await api('state')).variant.length, before + 1);
  assert.equal(m.manifest.screens.length, 3); assert.ok(new Set(m.mix_sources.map(x => x.variant_id)).size >= 2, 'screens from at least two versions');
  assert.ok(!m.validation.some(c => c.outcome === 'fail' && /Package|Token/.test(c.check)), 'mix passes package checks'); assert.ok(m.validation.some(c => c.check === 'Mixed provenance'));
  await page.locator(`[data-variant="${m.id}"]`).waitFor(); await page.locator(`[data-variant="${m.id}"] .thumbnail img`).first().waitFor();
  await page.waitForFunction(id => [...document.querySelectorAll(`[data-variant="${id}"] .thumbnail img`)].every(i => i.complete && i.naturalWidth > 0), m.id); await page.getByText('Mixed version').first().waitFor();
  await page.locator(`[data-variant="${m.id}"] .fname .muted`).first().waitFor();
});
await step('failure handling: cancel, timeout/failed card, retry, partial failure leaves other variants usable', async () => {
  const st = await api('state'); const fixtures = st.runner.filter(r => r.type === 'fixture');
  const slow = await api('runner', { type: 'cli', name: 'Slow CLI', executable: '/bin/sleep', args: ['60'], timeout: 120 }), bad = await api('runner', { type: 'cli', name: 'Failing CLI', executable: '/bin/false', args: [] });
  const jobs = await api('generate', { project_id: project.id, board_id: board.id, brief: board.brief, runner_ids: [fixtures[0].id, slow.id, bad.id], idempotency_key: 'e2e-' + Date.now() });
  await page.goto(`${origin}/projects/${project.id}/boards/${board.id}`);
  await page.locator('.job-card', { hasText: 'Slow CLI' }).getByRole('button', { name: /Cancel/ }).click();
  await until(async () => (await api('state')).job.find(j => j.id === jobs[1].id).status === 'cancelled', 'cancelled');
  await until(async () => (await api('state')).job.find(j => j.id === jobs[2].id).status === 'failed', 'failed');
  await page.locator('.job-card', { hasText: 'Failing CLI' }).getByRole('button', { name: /Retry/ }).waitFor();
  await page.locator('.job-card', { hasText: 'Failing CLI' }).getByRole('button', { name: /Retry/ }).click();
  const retried = await until(async () => (await api('state')).job.find(j => j.retry_of === jobs[2].id), 'retry job'); assert.equal(retried.input_hash, jobs[2].input_hash);
  await until(async () => (await api('state')).variant.some(v => v.job_id === jobs[0].id), 'fixture variant still produced');
  await api('delete-runner', { id: slow.id }); await api('delete-runner', { id: bad.id });
});
await step('settings: automatic retries and sandbox persist on a local agent runner', async () => {
  const r = await api('runner', { type: 'cli', name: 'Sandboxed CLI', executable: '/bin/true', args: [], timeout: 30, auto_retries: 0, sandbox: null }); const cfg = await (await fetch(origin + '/api/config')).json();
  await page.goto(origin + '/settings/agents'); const row = page.locator(`[data-runner="${r.id}"]`); await row.locator('[data-runner-retries]').fill('2');
  if (cfg.bwrap) await row.locator('[data-runner-sandbox]').check(); await row.getByRole('button', { name: 'Save' }).click();
  await until(async () => (await api('state')).runner.find(x => x.id === r.id).auto_retries === 2, 'retries saved'); assert.equal((await api('state')).runner.find(x => x.id === r.id).sandbox, cfg.bwrap ? 'bwrap' : null);
  await api('delete-runner', { id: r.id });
});
await step('settings: edit, disable, test runners', async () => {
  await page.goto(origin + '/settings/agents'); const row = page.locator('[data-runner]').first(); await row.locator('[data-runner-name]').fill('Studio A renamed'); await row.getByRole('button', { name: 'Save' }).click();
  await until(async () => (await api('state')).runner.some(r => r.name === 'Studio A renamed'), 'renamed'); await page.locator('[data-runner]').first().getByRole('button', { name: 'Test' }).click(); await page.getByText('Fixture ready').first().waitFor();
});
await step('references page: notes persist, delete keeps job copies', async () => {
  await page.goto(`${origin}/projects/${project.id}/references`); await page.locator('.refcard').first().waitFor(); assert.equal(await page.locator('.refcard').count(), 3);
  await page.locator('[data-ref-note]').first().fill('Use this tone, not the colours'); await page.locator('[data-ref-note]').first().blur(); await until(async () => (await api('state')).reference.some(r => r.note === 'Use this tone, not the colours'), 'note saved');
  const third = (await api('state')).reference.at(-1); await page.locator(`[data-ref-delete="${third.id}"]`).click(); await page.locator('#modal-form').getByRole('button', { name: 'Delete image' }).click(); await until(async () => (await page.locator('.refcard').count()) === 2, 'deleted');
  const j = (await api('state')).job.find(x => x.board_id === board.id && x.type === 'generate_board'); assert.equal((await fetch(`${origin}/assets/jobs/${j.id}/references/${j.references[0].file}`)).status, 200);
});
await step('history: lineage and job outputs; persistence after reload', async () => {
  await page.goto(`${origin}/projects/${project.id}/history`); await page.getByRole('heading', { name: 'Lineage', exact: true }).waitFor(); assert.ok(await page.locator('ul.lineage li').count() >= 3); await page.getByText('envelope.json').first().waitFor();
  await page.reload(); await page.getByRole('heading', { name: 'Lineage', exact: true }).waitFor(); const st = await api('state'); assert.ok(st.variant.some(v => v.approved)); assert.ok(st.annotation.some(a => a.status === 'applied'));
});
await step('blind A/B: identities hidden in UI and API until a choice, then revealed and recorded', async () => {
  const st = await api('state'), fx = st.runner.filter(r => r.type === 'fixture').slice(0, 2), names = fx.map(r => r.name);
  const nb = await api('board', { project_id: project.id, title: 'Blind test', brief: 'Compare two approaches', screens: ['One', 'Two'] });
  await api('generate', { project_id: project.id, board_id: nb.id, brief: nb.brief, runner_ids: fx.map(r => r.id), idempotency_key: 'blind-' + Date.now() });
  await until(async () => (await api('state')).variant.filter(v => v.board_id === nb.id).length === 2, 'blind variants');
  await page.goto(`${origin}/projects/${project.id}/boards/${nb.id}`); await page.locator('.fframe').first().waitFor();
  await page.getByRole('button', { name: /Blind compare: off/ }).click(); await page.locator('.blindbar').waitFor();
  const html = await page.content(); for (const n of names) assert.ok(!html.includes(n), 'runner name leaked into the page: ' + n);
  assert.ok(html.includes('Option '), 'neutral labels shown'); const raw = JSON.stringify(await api('state')); for (const n of names) assert.ok(!JSON.stringify((await api('state')).variant.filter(v => v.board_id === nb.id)).includes(n), 'runner name leaked via API: ' + n);
  await page.goto(`${origin}/projects/${project.id}/boards/${nb.id}/compare`); await page.locator('[data-compare-side]').first().waitFor(); assert.ok(!(await page.content()).includes(names[0]) && !(await page.content()).includes(names[1]), 'compare view is blind too');
  await page.goto(`${origin}/projects/${project.id}/boards/${nb.id}`); await page.locator('[data-blind-pick]').first().click(); await page.locator('#bp-r').fill('clearer'); await page.locator('#modal-form').getByRole('button', { name: 'Choose and reveal' }).click();
  await page.locator('.blindbar.revealed').waitFor(); assert.match(await page.locator('.blindbar.revealed').textContent(), /You preferred Option [A-Z], which was (Studio|Exploration)/);
  const b = (await api('state')).board.find(x => x.id === nb.id); assert.ok(b.revealed && b.blind_choice.reason === 'clearer'); assert.ok((await api('state')).variant.some(v => names.includes(v.runner_name)), 'names visible after reveal');
});
await step('per-job experiment overrides: conflict preview, run-only prose, nothing saved to the project', async () => {
  const before = (await api('state')); const ctxBefore = before.project.find(x => x.id === project.id).context_id, nCtx = before.context.length;
  await page.goto(`${origin}/projects/${project.id}/boards/${board.id}`); await page.locator('[data-action="generate"]').first().click();
  await page.locator('#g-brief').fill('Show three equal action buttons on the first screen');
  await page.locator('#conflicts .conflict.warn').first().waitFor(); assert.match(await page.locator('#conflicts').textContent(), /CTA-001/);
  await page.locator('details.exp > summary').click(); await page.locator('#g-prose').fill('EXPERIMENT: three equal doors, playful voice');
  await page.locator('select[name="mode:CTA-001"]').selectOption('replace'); await page.locator('input[name="text:CTA-001"]').fill('Up to three equal actions on the entry screen');
  await page.waitForFunction(() => ![...document.querySelectorAll('#conflicts .conflict.warn')].some(e => e.textContent.includes('CTA-001')), null, { timeout: 5000 }); // replacing the rule resolves the warning
  const fx = (await api('state')).runner.filter(r => r.type === 'fixture'); for (const r of fx) { const cb = page.locator(`input[name="runners"][value="${r.id}"]`); if (!(await cb.isChecked())) await cb.check(); }
  await page.locator('#modal-form button.primary').click(); await page.locator('#dialog').waitFor({ state: 'hidden' });
  const st = await api('state'); const jobs = st.job.filter(j => j.board_id === board.id && j.context?.run_overrides?.prose); assert.ok(jobs.length >= 2);
  for (const j of jobs) { assert.match(j.instruction, /RUN-ONLY EXPERIMENT BRIEF/); assert.equal(j.context.effective_rules.find(r => r.id === 'CTA-001').description, 'Up to three equal actions on the entry screen'); }
  assert.equal(new Set(jobs.map(j => j.input_hash)).size, 1);
  assert.equal(st.project.find(x => x.id === project.id).context_id, ctxBefore); assert.equal(st.context.length, nCtx, 'overrides must not create project context versions');
  await until(async () => (await api('state')).variant.filter(v => jobs.some(j => j.id === v.job_id)).length >= 2, 'override variants');
  const ov = (await api('state')).variant.find(v => jobs.some(j => j.id === v.job_id)); await page.goto(`${origin}/projects/${project.id}/boards/${board.id}/review/${ov.id}`); await page.locator('#pin-area img').waitFor();
  await page.getByText('Run-only experiment overrides').first().waitFor();
});
await step('boards list, archive & restore', async () => {
  await page.goto(`${origin}/projects/${project.id}/boards`); await page.getByRole('heading', { name: 'Boards', exact: true }).waitFor(); assert.ok(await page.locator('.project-card').count() >= 1);
});
assert.deepEqual(errors, [], 'no browser console exceptions');
await browser.close(); console.log('browser workflow passed');
