// End-to-end for the designer tools: spread, rules-vs-free pairs, rule-break log, audit with review documents,
// style extraction, realistic states, set-aside decision log, responsive preview.
//   STUDIO_SEED_FIXTURES=1 STUDIO_FOLDER_ROOTS=/tmp STUDIO_STORAGE=$(mktemp -d) PORT=5198 python3 apps/api/server.py   then   STUDIO_URL=http://localhost:5198 node tests/tools.mjs
import { chromium } from '@playwright/test';
import assert from 'node:assert/strict';
import fs from 'node:fs'; import os from 'node:os'; import path from 'node:path';
const origin = process.env.STUDIO_URL || 'http://localhost:5198';
async function api(p, data) { const r = await fetch(origin + '/api/' + p, data ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) } : {}); const x = await r.json(); assert.ok(r.ok, p + ': ' + x.message); return x; }
const until = async (fn, what, ms = 90000) => { const end = Date.now() + ms; for (;;) { const x = await fn(); if (x) return x; assert.ok(Date.now() < end, 'timed out waiting for ' + what); await new Promise(r => setTimeout(r, 400)); } };
const docs = fs.mkdtempSync(path.join(os.tmpdir(), 'review-'));
fs.writeFileSync(path.join(docs, 'legal.md'), '# Legal & compliance\n- [ ] Must include "Representative APR"\n- [ ] Never say "guaranteed approval"\n- [ ] Legal has approved the footer wording\n');
const brand = fs.mkdtempSync(path.join(os.tmpdir(), 'brand-'));
fs.writeFileSync(path.join(brand, 'DESIGN.md'), '# Acme Design\n\nBe calm and plain-spoken.\n\n## Principles\n- Explain why sensitive details are requested\n- Never use red for errors alone\n');
fs.writeFileSync(path.join(brand, 'rules.md'), '# Rules\n- [ ] **CTA-001** Headlines must be under 8 words\n- Avoid jargon\n');
fs.writeFileSync(path.join(brand, 'tokens.json'), JSON.stringify({ accent: '#0f766e', color: { surface: { $value: '#fafafa' } } }));
const browser = await chromium.launch({ executablePath: process.env.CHROME_PATH || '/usr/bin/google-chrome', headless: true });
const page = await (await browser.newContext({ viewport: { width: 1440, height: 900 } })).newPage(); const errors = [];
page.on('pageerror', e => errors.push('pageerror: ' + e.message)); page.on('console', m => { if (m.type() === 'error' && !/Failed to load resource/.test(m.text())) errors.push('console: ' + m.text()); });
const step = async (name, fn) => { try { await fn(); console.log('ok  ' + name); } catch (e) { console.error('FAIL ' + name + '\n' + e.message); await page.screenshot({ path: '/tmp/tools-fail.png', fullPage: true }).catch(() => {}); await browser.close(); process.exit(1); } };
let st = await api('state'); const project = st.project[0], board = st.board[0]; const base = `/projects/${project.id}`;

await step('guidelines: import DESIGN.md, rules and tokens from a folder into the draft, then save a version', async () => {
  const before = (await api('state')).context.length; await page.goto(`${origin}${base}/context`);
  await page.locator('#import-folder').fill(brand); await page.locator('[data-action="scan-folder"]').click(); await page.locator('#import-result').getByText('DESIGN.md').first().waitFor();
  const res = page.locator('#import-result'); assert.ok(await res.getByText('Headlines must be under 8 words').count()); assert.ok(await res.getByText('color-surface').count());
  await page.locator('[data-action="import-apply"]').click();
  assert.match(await page.locator('#guidelines').inputValue(), /Be calm and plain-spoken/); await page.locator('#rules table.rules').getByText('Headlines must be under 8 words').waitFor();
  assert.match(await page.locator('#tokens-json').inputValue(), /"color-surface": "#fafafa"/);
  assert.equal((await api('state')).context.length, before, 'nothing saved until you press save');
  await page.locator('[data-action="save-context"]').click(); await until(async () => (await api('state')).context.length === before + 1, 'saved version');
  const c = (await api('state')).context.at(-1); assert.ok(c.rules.some(r => r.description === 'Headlines must be under 8 words' && r.justification.startsWith('Imported from rules.md'))); assert.equal(c.tokens.accent, '#0f766e');
  assert.equal((await api('state')).project[0].guidelines_folder, fs.realpathSync(brand), 'folder remembered');
});
await step('guidelines: choose files in the browser (works away from this computer)', async () => {
  await page.goto(`${origin}${base}/context`); await page.locator('#import-files').setInputFiles([path.join(brand, 'DESIGN.md'), path.join(brand, 'tokens.json')]);
  await page.locator('#import-result').getByText('accent').first().waitFor(); assert.equal(await page.locator('#import-result').getByText('Principles').count(), 0);
});
await step('profiles: create from Main, edit independently, default stays Main', async () => {
  await page.goto(`${origin}${base}/context`); await page.locator('[data-action="new-profile"]').click(); await page.locator('#pf-name').fill('Loose'); await page.locator('#modal-form button[type=submit]').click();
  await page.locator('[data-profile][aria-pressed="true"]', { hasText: 'Loose' }).waitFor();
  await page.locator('#guidelines').fill('# LOOSE PROFILE\n\nBe playful.'); await page.locator('#quick-rules').fill('Only the loose rule'); await page.getByRole('button', { name: 'Add instructions as rules' }).click();
  await page.locator('[data-action="save-context"]').click(); await until(async () => (await api('state')).context.some(c => c.markdown.startsWith('# LOOSE PROFILE')), 'loose saved');
  st = await api('state'); const proj = st.project[0]; assert.equal(proj.profiles.length, 2); const main = st.context.find(c => c.id === proj.context_id); assert.ok(!main.markdown.startsWith('# LOOSE'), 'main untouched'); assert.equal(proj.profile_id, 'main');
  const loose = st.context.filter(c => c.profile_id === proj.profiles[1].id); assert.deepEqual(loose.map(c => c.version), [1, 2]);
  await page.locator('[data-profile="main"]').click(); assert.doesNotMatch(await page.locator('#guidelines').inputValue(), /LOOSE/);
  await page.locator('[data-profile]', { hasText: 'Loose' }).click(); assert.match(await page.locator('#guidelines').inputValue(), /LOOSE PROFILE/);
});
await step('targets: a website-and-mobile board with 8 screens, phone inset, view-scoped pins', async () => {
  await page.goto(`${origin}${base}/boards`); await page.locator('[data-action="new-board"]').first().click();
  await page.locator('#nb-title').fill('Cabin booking'); await page.locator('#nb-target').selectOption('both'); await page.locator('#nb-brief').fill('Book a mountain cabin');
  await page.locator('#nb-screens').fill(['Search', 'Results', 'Cabin', 'Dates', 'Guests', 'Extras', 'Pay', 'Confirmed'].join('\n')); await page.locator('#modal-form button[type=submit]').click();
  const nb = await until(async () => (await api('state')).board.find(b => b.title === 'Cabin booking'), 'new board'); assert.equal(nb.target, 'both'); assert.equal(nb.screens.length, 8);
  const fx = (await api('state')).runner.filter(r => r.type === 'fixture'); await api('generate', { project_id: project.id, board_id: nb.id, brief: nb.brief, runner_ids: fx.map(r => r.id), idempotency_key: 'tgt-' + Date.now() });
  const v = await until(async () => (await api('state')).variant.find(x => x.board_id === nb.id), 'variant', 120000);
  await page.goto(`${origin}${base}/boards/${nb.id}`); await page.locator('.phone-thumb').first().waitFor();
  assert.match(await page.locator('.fsize').first().textContent(), /1440 × 900 · phone view inset/);
  await page.goto(`${origin}${base}/boards/${nb.id}/review/${v.id}`); await page.locator('#pin-area img').waitFor();
  const pin = async (view) => { const box = await page.locator('#pin-area img').boundingBox(); await page.locator('#pin-area').click({ position: { x: box.width * .5, y: box.height * .2 } }); await page.locator('#pin-comment').fill('pin on ' + view); await page.locator('#modal-form').getByRole('button', { name: 'Add comment' }).click(); await page.locator('.pin').first().waitFor(); };
  await pin('desktop'); await page.locator('[data-review-view="m"]').click(); await page.waitForTimeout(500); assert.equal(await page.locator('.pin').count(), 0, 'desktop pin hidden on phone view');
  const wPhone = (await page.locator('#pin-area').boundingBox()).width; await pin('phone');
  const anns = (await api('state')).annotation.filter(a => a.variant_id === v.id); assert.deepEqual(anns.map(a => a.view).sort(), ['d', 'm']);
  await page.locator('[data-review-view="d"]').click(); await page.waitForTimeout(500); assert.equal(await page.locator('.pin').count(), 1); assert.ok((await page.locator('#pin-area').boundingBox()).width > wPhone * 1.5, 'desktop frame wider than phone frame');
  await page.goto(`${origin}${base}/boards/${nb.id}/review/${v.id}`); await page.getByRole('tab', { name: 'Design' }).click(); assert.match(await page.locator('.inspector').textContent(), /Width\s*1440/);
});
await step('settings: point the project at a folder of review documents', async () => {
  await page.goto(`${origin}${base}/settings/agents`); await page.locator('#review-folder').fill(docs); await page.locator('[data-action="save-review-folder"]').click();
  await page.getByText('legal.md').waitFor(); await page.getByText('3 criteria').waitFor();
});
await step('generate under two profiles: separate snapshots, profile tags on the board', async () => {
  const before = (await api('state')).job.length; await page.goto(`${origin}${base}/boards/${board.id}`); await page.getByRole('button', { name: /Generate/ }).first().click();
  await page.locator('#gen-profiles input[value]').nth(1).check(); await page.locator('input[name="runners"]').first().check(); await page.locator('input[name="runners"]').nth(1).check();
  await page.getByRole('button', { name: 'Generate variants' }).click();
  await until(async () => { const j = (await api('state')).job.slice(before); return j.length === 4 && j.every(x => x.status === 'succeeded'); }, 'profile jobs');
  const j = (await api('state')).job.slice(before); const names = [...new Set(j.map(x => x.context.profile_name))].sort(); assert.deepEqual(names, ['Loose', 'Main']);
  assert.equal(new Set(j.map(x => x.context.hash)).size, 2, 'two distinct guideline snapshots'); assert.ok(j.filter(x => x.context.profile_name === 'Loose').every(x => x.context.effective_rules.some(r => r.description === 'Only the loose rule')));
  await page.reload(); await page.locator('[data-profile-tag]', { hasText: 'Loose' }).first().waitFor();
});
await step('generate with Spread and Rules-vs-free creates four jobs with matching directions', async () => {
  const before = (await api('state')).job.length; await page.goto(`${origin}${base}/boards/${board.id}`); await page.getByRole('button', { name: /Generate/ }).first().click();
  await page.locator('input[name="spread"]').check(); await page.locator('input[name="pair"]').check();
  await page.locator('input[name="runners"]').first().check(); await page.locator('input[name="runners"]').nth(1).check();
  await page.getByRole('button', { name: 'Generate variants' }).click();
  await until(async () => { const s = await api('state'); const j = s.job.slice(before).filter(x => x.type === 'generate_board'); return j.length === 4 && j.every(x => x.status === 'succeeded'); }, 'four jobs');
  st = await api('state'); const jobs = st.job.slice(before).filter(x => x.type === 'generate_board'); const free = jobs.filter(x => x.context.run_overrides?.free === 'open'), norm = jobs.filter(x => !x.context.run_overrides?.free);
  assert.equal(free.length, 2); assert.equal(norm.length, 2); assert.deepEqual(free.map(x => x.angle).sort(), norm.map(x => x.angle).sort()); assert.equal(new Set(norm.map(x => x.angle)).size, 2);
});
let freeVar, normVar;
await step('free variant shows the rule-break log and a rules-vs-free compare', async () => {
  st = await api('state'); const jobById = Object.fromEntries(st.job.map(j => [j.id, j])); const vs = st.variant.filter(v => !v.parent_id && v.board_id === board.id);
  freeVar = vs.find(v => jobById[v.job_id].context.run_overrides?.free); normVar = vs.find(v => v.runner_id === freeVar.runner_id && !jobById[v.job_id].context.run_overrides?.free); assert.ok(freeVar.rule_breaks && !normVar.rule_breaks);
  await page.goto(`${origin}${base}/boards/${board.id}/review/${freeVar.id}`); await page.locator('#rule-breaks').waitFor();
  await page.locator('[data-action="compare-twin"]').first().click(); await page.waitForURL(/compare\?left=/); await page.getByText(/Free · fully open/).first().waitFor();
});
await step('audit: manual, runs accessibility checks and your documents', async () => {
  await page.goto(`${origin}${base}/boards/${board.id}/review/${normVar.id}`); await page.getByRole('tab', { name: /Audit/ }).click();
  assert.equal((await api('state')).variant.find(v => v.id === normVar.id).audits, undefined, 'no audit until asked');
  await page.locator('[data-action="run-audit"]').click(); await page.locator('#audit-panel').getByText('Representative APR').waitFor();
  const panel = page.locator('#audit-panel'); assert.ok(await panel.getByText(/Legal has approved the footer/).count()); assert.ok(await panel.getByText(/Legal & compliance/).count());
  await panel.locator('[data-audit-outcome="review"]').first().getByRole('button', { name: 'Mark OK' }).click(); await panel.getByText('Accepted').first().waitFor();
});
await step('agent reading of documents is manual, labelled unverified, and the template runner admits it cannot read', async () => {
  assert.equal((await api('state')).job.filter(j => j.type === 'audit_review').length, 0, 'never automatic');
  await page.locator('[data-action="audit-docs"]').click();
  await page.locator('#doc-review [data-doc-outcome="unclear"]').first().waitFor(); await page.locator('#doc-review').getByText('Agent opinion · unverified').waitFor();
  await page.locator('#doc-review').getByText(/fixture runner cannot read/).first().waitFor();
  assert.equal((await api('state')).variant.find(v => v.id === normVar.id).doc_reviews.length, 1);
});
await step('pull style into guidelines creates a new guideline version', async () => {
  const n = (await api('state')).context.length; await page.getByRole('tab', { name: 'Design' }).click(); await page.locator('[data-action="pull-style"]').click();
  await page.locator('#dialog input[type=checkbox]').first().waitFor(); const pick = page.locator('#dialog input[type=checkbox]:not([disabled])').first(); await pick.check();
  await pick.locator('xpath=..').locator('input[name^="name:"]').fill('brand-pulled'); await page.locator('#modal-form button[type=submit]').click();
  await until(async () => (await api('state')).context.length === n + 1, 'new context'); assert.ok((await api('state')).context.some(c => c.tokens['brand-pulled']));
});
await step('realistic states queue a revision with no pins', async () => {
  await page.locator('[data-action="add-states"]').click(); await page.getByRole('button', { name: 'Add states' }).click();
  const j = await until(async () => (await api('state')).job.find(x => x.type === 'revise_board' && x.parent_id === normVar.id), 'states job'); assert.equal(j.annotations.length, board.screens.length);
  await until(async () => (await api('state')).job.find(x => x.id === j.id).status === 'succeeded', 'states done');
});
await step('set aside records why, history shows the decision log', async () => {
  await page.goto(`${origin}${base}/boards/${board.id}/review/${freeVar.id}`); await page.locator('[data-action="set-aside"]').click(); await page.locator('#sa-note').fill('Too busy for a first step'); await page.locator('#modal-form button[type=submit]').click();
  await page.goto(`${origin}${base}/history`); await page.locator(`[data-decision-log="${board.id}"]`).getByText('Too busy for a first step').waitFor();
});
await step('approve records a reason too', async () => {
  await page.goto(`${origin}${base}/boards/${board.id}/review/${normVar.id}`); await page.locator('[data-action="approve"]').click(); await page.locator('#ap-note').fill('Clearest first step'); await page.locator('#modal-form button[type=submit]').click();
  await until(async () => (await api("state")).board.find(b => b.id === board.id).decisions?.some(d => d.decision === 'approved' && d.note === 'Clearest first step'), 'approve decision');
});
await step('live preview has phone/tablet/desktop widths', async () => {
  await page.goto(`${origin}${base}/boards/${board.id}`); await page.locator(`#frame-${normVar.id}-0`).dblclick();
  await page.locator('[data-preview-width="phone"]').click(); const w = await page.locator('iframe.live-frame').evaluate(e => e.getBoundingClientRect().width); assert.ok(w <= 391, 'phone width ' + w);
});
const agent = await api('runner', { type: 'cli', name: 'Scripted agent', executable: '/usr/bin/python3', args: [path.resolve(path.dirname(new URL(import.meta.url).pathname), 'fake_agent.py'), '{prompt}'], timeout: 60 });
await step('starter guidelines are flagged, and spread is on by default in the generate dialog', async () => {
  await page.goto(`${origin}${base}/context`); await page.locator('#starter-warning').waitFor();
  await page.goto(`${origin}${base}/boards/${board.id}`); await page.getByRole('button', { name: /Generate/ }).first().click(); assert.ok(await page.locator('input[name="spread"]').isChecked(), 'spread default'); await page.keyboard.press('Escape');
});
await step('draft guidelines from a brief; loading puts it in the draft, saves nothing', async () => {
  const n = (await api('state')).context.length; await page.goto(`${origin}${base}/context`);
  await page.locator('#draft-brief').fill('Relay Ops sells AI agents that run IT operations to IT directors.'); await page.locator('#draft-panel select').selectOption({ label: 'Scripted agent' }); await page.locator('[data-action="draft-guidelines"]').click();
  await page.locator('#draft-result').waitFor({ timeout: 60000 }); await page.locator('#draft-result').getByText('Assumed a dark theme').waitFor();
  await page.locator('[data-action="load-draft"]').click(); await page.getByText('Loaded into your draft').first().waitFor();
  assert.equal((await api('state')).context.length, n, 'nothing saved until Save new version'); assert.match(await page.locator('textarea').first().inputValue(), /Relay Ops/);
});
await step('ask a question about a pin changes nothing and shows a labelled answer', async () => {
  const before = JSON.stringify((await api('state')).variant.find(v => v.id === normVar.id).manifest);
  await page.goto(`${origin}${base}/boards/${board.id}/review/${normVar.id}`);   const box = await page.locator('#pin-area img').boundingBox(); await page.locator('#pin-area').click({ position: { x: box.width * .5, y: box.height * .2 } });
  await page.locator('#pin-comment').waitFor(); await page.locator('#pin-mode input[value="ask"]').check(); await page.locator('#pin-comment').fill('Why is this so small?');
  await page.locator('#modal-form').getByRole('button', { name: 'Add comment' }).click();
  const j = await until(async () => (await api('state')).job.find(x => x.type === 'pin_ask' && x.target_variant_id === normVar.id), 'ask job');
  await until(async () => (await api('state')).job.find(x => x.id === j.id).status === 'succeeded', 'ask done', 60000);
  assert.equal(JSON.stringify((await api('state')).variant.find(v => v.id === normVar.id).manifest), before, 'design untouched');
  await page.getByRole('tab', { name: 'Comments' }).click().catch(() => {}); await page.locator('#ask-list').getByText('Agent opinion, unverified').waitFor();
});
await step('developer hand-off downloads a zip with the guidelines beside the site', async () => {
  const proto = (await api('state')).prototype.at(-1); assert.ok(proto, 'an approved prototype exists');
  const buf = Buffer.from(await (await fetch(`${origin}/api/handoff/${proto.id}`)).arrayBuffer()); assert.equal(buf.subarray(0, 2).toString(), 'PK');
  assert.ok(buf.includes(Buffer.from('design/tokens.css')) && buf.includes(Buffer.from('README.md')));
});
await step('bring a part from another design queues a scoped revision with the donor staged', async () => {
  await page.goto(`${origin}${base}/boards/${board.id}/review/${normVar.id}`); await page.getByRole('tab', { name: 'Design' }).click(); await page.locator('[data-action="merge-part"]').click();
  await page.locator('#mg-donor').selectOption({ value: freeVar.id }); await page.locator('#mg-part').fill('the summary table'); await page.locator('#modal-form button[type=submit]').click();
  const j = await until(async () => (await api('state')).job.find(x => x.type === 'revise_board' && x.parent_id === normVar.id && x.instruction.includes('MERGE TASK')), 'merge job');
  assert.equal(Object.keys(j.scope).length, 1); assert.ok(j.instruction.includes('the summary table'));
  await until(async () => (await api('state')).job.find(x => x.id === j.id).status === 'succeeded', 'merge done', 60000);
});
assert.deepEqual(errors, [], errors.join('\n')); await browser.close(); console.log('designer tools workflow passed');
