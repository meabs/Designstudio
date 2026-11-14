// Scripted tours of the real UI, one clip per scene. Run: node record/scenes.mjs <scene> (needs the demo data from build-demo).
import fs from 'node:fs'; import os from 'node:os'; import path from 'node:path';
import { session, api, ORIGIN } from './lib.mjs';
const ids = JSON.parse(fs.readFileSync(process.env.IDS || '/tmp/demo-ids.json'));
const P = ids.project, B = ids.board; const base = `/projects/${P}`; const board = `${base}/boards/${B}`;
const state = async () => api('state');
async function pick({ runner, profile, free, round } = {}) {
  const s = await state(); const jobBy = Object.fromEntries(s.job.map((j) => [j.id, j]));
  return s.variant.filter((v) => v.board_id === B && !v.parent_id).filter((v) => {
    const j = jobBy[v.job_id]; return (!runner || v.runner_name === runner) && (!profile || (v.profile_id || 'main') === (profile === 'main' ? 'main' : ids.loose)) && (free === undefined || !!(j.context.run_overrides?.free) === free);
  }).sort((a, b) => a.created_at - b.created_at);
}
const play = async (s, fn) => { await s.start(); await fn(s); const r = await s.stop(); console.log(s.name, r.frames, 'frames', r.errors.length ? r.errors : ''); };

export const scenes = {
  async board() {
    const s = await session('board'); await play(s, async (s) => {
      await s.goto('/projects'); await s.wait(1600); await s.click(s.page.getByText('Meridian Card Application').first(), { after: 1400 });
      if (!s.page.url().includes('/boards/' + B)) await s.goto(board); await s.wait(1200);
      await s.page.mouse.move(900, 420, { steps: 18 }); await s.wait(1500);
      await s.scroll('main.workspace', 520, 1800); await s.wait(1800); await s.scroll('main.workspace', 1100, 1800); await s.wait(1600);
      await s.scroll('main.workspace', 0, 1200); await s.wait(1200);
    });
  },
  async generate() {
    const s = await session('generate'); await play(s, async (s) => {
      await s.goto(board); await s.wait(1000); await s.click(s.page.getByRole('button', { name: /Generate variants/ }).first(), { after: 1400 });
      const dlg = s.page.locator('#dialog'); await s.wait(1200);
      await s.click(s.page.locator('summary', { hasText: 'Experiment for this run only' }), { after: 1200 });
      await s.click(s.page.locator('input[name="free"][value="rules"]'), { after: 900 }); await s.click(s.page.locator('input[name="free"][value="open"]'), { after: 1100 });
      await s.click(s.page.locator('input[name="free"][value=""]'), { after: 500 });
      await s.scroll('#dialog [data-slot=scroll-area-viewport]', 400, 1300).catch(() => {}); await s.wait(500);
      await s.click(s.page.locator('input[name="spread"]'), { after: 800 }); await s.click(s.page.locator('input[name="pair"]'), { after: 900 });
      await s.wait(900); await s.click(s.page.getByRole('button', { name: 'Cancel' }), { after: 800 });
    });
  },
  async compare() {
    const s = await session('compare'); const free = (await pick({ free: true }))[0]; await play(s, async (s) => {
      await s.goto(`${board}/review/${free.id}`); await s.wait(1400);
      await s.click(s.page.getByRole('tab', { name: 'Design' }), { after: 400 });
      await s.page.locator('#rule-breaks').scrollIntoViewIfNeeded(); await s.wait(2400);
      await s.click(s.page.locator('[data-action="compare-twin"]').first(), { after: 1800 });
      await s.wait(2200); await s.click(s.page.locator('.compare-grid').locator('xpath=..').locator('[data-screen="1"]').first(), { after: 2000 });
      await s.click(s.page.locator('[data-screen="2"]').first(), { after: 2200 });
    });
  },
  async guidelines() {
    const brand = process.env.BRAND || '/tmp/meridian/brand'; const s = await session('guidelines'); await play(s, async (s) => {
      await s.goto('/projects'); await s.wait(900); await s.click(s.page.getByRole('button', { name: 'New project' }), { after: 800 });
      await s.type('#np-name', 'Meridian Savings', 45); await s.wait(500); await s.click(s.page.getByRole('button', { name: 'Create project' }), { after: 1600 });
      await s.page.getByRole('heading', { name: 'Design context' }).waitFor(); await s.wait(900);
      await s.type('#import-folder', brand, 28); await s.click(s.page.locator('[data-action="scan-folder"]'), { after: 1600 });
      await s.page.locator('#import-result').waitFor(); await s.page.locator('#import-panel').scrollIntoViewIfNeeded(); await s.wait(2600);
      await s.click(s.page.locator('[data-action="import-apply"]'), { after: 1400 });
      await s.scroll('main.workspace', 700, 1600).catch(() => {}); await s.wait(1600); await s.scroll('main.workspace', 0, 800).catch(() => {});
      await s.click(s.page.locator('[data-action="save-context"]'), { after: 1400 });
      await s.click(s.page.locator('[data-action="new-profile"]'), { after: 900 }); await s.type('#pf-name', 'Looser tone', 45); await s.click(s.page.locator('#modal-form button[type=submit]'), { after: 1800 });
      await s.wait(1800);
    });
  },
  async review() {
    const v = (await pick({ runner: 'Claude Code', profile: 'main', free: false }))[0]; const s = await session('review'); await play(s, async (s) => {
      await s.goto(`${board}/review/${v.id}`); await s.page.locator('#pin-area img').waitFor(); await s.wait(1600);
      const b = await s.page.locator('#pin-area img').boundingBox();
      await s.page.mouse.move(b.x + b.width * 0.3, b.y + b.height * 0.5, { steps: 20 }); await s.wait(500);
      await s.page.mouse.move(b.x + b.width * 0.4, b.y + b.height * 0.2, { steps: 25 }); await s.wait(400);
      await s.page.mouse.down(); await s.wait(60); await s.page.mouse.up(); await s.page.locator('#pin-comment').waitFor(); await s.wait(900);
      await s.type('#pin-comment', 'Make this heading friendlier and explain why we ask before the first question.', 34); await s.wait(500);
      await s.click(s.page.locator('#modal-form').getByRole('button', { name: 'Add comment' }), { after: 1500 });
      await s.click(s.page.getByRole('tab', { name: /Comments/ }), { after: 1200 }); await s.wait(1000);
      await s.click(s.page.getByRole('button', { name: /Revise selection \(1 pin\)/ }), { after: 2600 });
    });
  },
  async revision() {
    const s0 = await state(); const kid = s0.variant.find((v) => v.parent_id && v.board_id === B); if (!kid) throw new Error('no revision yet');
    const s = await session('revision'); await play(s, async (s) => {
      await s.goto(`${board}/review/${kid.id}`); await s.page.locator('.regions .region').first().waitFor().catch(() => {}); await s.wait(2600);
      await s.click(s.page.getByRole('tab', { name: 'Design' }), { after: 800 }); await s.wait(1800);
      await s.click(s.page.locator('[data-accept]').first(), { after: 1800 }).catch(() => {}); await s.wait(1500);
    });
  },
  async audit() {
    const v = (await pick({ runner: 'Claude Code', profile: 'main', free: false }))[0]; const s = await session('audit'); await play(s, async (s) => {
      await s.goto(`${board}/review/${v.id}`); await s.wait(1200); await s.click(s.page.getByRole('tab', { name: /Audit/ }), { after: 900 }); await s.wait(1000);
      await s.click(s.page.locator('[data-action="run-audit"]'), { after: 1600 }); await s.page.locator('#audit-panel [data-audit-outcome]').first().waitFor(); await s.wait(1500);
      await s.scroll('.ibody', 340, 1600); await s.wait(1600); await s.scroll('.ibody', 760, 1800); await s.wait(1400);
      await s.page.locator('#doc-review').scrollIntoViewIfNeeded(); await s.wait(1500);
      await s.click(s.page.locator('[data-action="audit-docs"]'), { after: 1500 });
      await s.page.locator('#doc-review [data-doc-outcome]').first().waitFor({ timeout: 240000 }); await s.wait(1500); await s.scroll('.ibody', 99999, 2200); await s.wait(2600);
    });
  },
  async decisions() {
    const list = await pick({ runner: 'Codex', profile: 'main', free: false }); const keep = (await pick({ runner: 'Claude Code', profile: 'main', free: false }))[0];
    const s = await session('decisions'); await play(s, async (s) => {
      await s.goto(`${board}/review/${list[0].id}`); await s.wait(1200); await s.click(s.page.getByRole('tab', { name: 'Design' }), { after: 400 });
      await s.click(s.page.locator('[data-action="set-aside"]'), { after: 900 }); await s.type('#sa-note', 'Too dense for a first step', 40); await s.click(s.page.locator('#modal-form button[type=submit]'), { after: 1500 });
      await s.goto(`${board}/review/${keep.id}`); await s.wait(1200);
      await s.click(s.page.locator('[data-action="approve"]'), { after: 1000 }); await s.type('#ap-note', 'Clearest first step and the calmest tone', 38); await s.wait(500);
      await s.click(s.page.locator('#modal-form button[type=submit]'), { after: 2800 });
      await s.wait(1200);
    });
  },
  async player() {
    const proto = (await state()).prototype.at(-1); const s = await session('player'); await play(s, async (s) => {
      await s.goto(`${base}/prototypes/${proto.id}`); await s.page.locator('#player').waitFor(); await s.wait(2000);
      const f = s.page.frameLocator('#player'); await f.locator('[data-role="primary-action"]').first().waitFor();
      await s.click(f.locator('[data-role="primary-action"]').first(), { after: 2200 }); await s.click(f.locator('[data-role="primary-action"]').first(), { after: 2200 });
      await s.click(s.page.locator('[data-player-state="error"]'), { after: 1500 }).catch(() => {}); await s.click(s.page.locator('[data-device="mobile"]'), { after: 2400 }); await s.click(s.page.locator('[data-device="desktop"]'), { after: 1200 });
    });
  },
  async history() {
    const s = await session('history'); await play(s, async (s) => { await s.goto(`${base}/history`); await s.wait(1400); await s.page.locator('[data-decision-log]').first().scrollIntoViewIfNeeded(); await s.wait(3200); });
  },
  async phone() {
    const s = await session('phone', { width: 430, height: 932, dsf: 2, mobile: true }); await play(s, async (s) => {
      await s.goto(board); await s.wait(1800); await s.scroll(null, 380, 1800).catch(() => {}); await s.wait(1400);
      await s.scroll(null, 900, 1800).catch(() => {}); await s.wait(1200); await s.scroll(null, 0, 1000).catch(() => {}); await s.wait(500);
      const proto = s.page.getByRole('button', { name: /Preview prototype/ }).first(); await s.click(proto, { after: 1800 }).catch(() => {}); await s.wait(1600);
    });
  },
};
const which = process.argv.slice(2); if (!which.length) throw new Error('usage: node record/scenes.mjs <scene...>');
for (const n of which) { if (!scenes[n]) throw new Error('unknown scene ' + n); await scenes[n](); }
