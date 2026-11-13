import { esc, icon, badge, renderMarkdown } from './lib.js';
import { S, route, nav, boardPath, live, protoLive, runnerOf, enabledRunners, current, checksOf, unresolvedReviews, prototypeOf, signature, variantsOf } from './store.js';
import { page, ensureDraft, isDirty, overrideList, renderResearchResults, runnerOptions, playerInfo, tokenPanel, refPicker } from './views.js';
import { findingsForHandoff, researchJobs, boardResearch, parseSources } from './research.js';

const $ = s => document.querySelector(s);
let toastTimer;

/* ---------- plumbing ---------- */
async function api(action, data) {
  const r = await fetch('/api/' + action, data ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) } : {});
  const x = await r.json(); if (!r.ok) throw Error(x.message || 'Request failed'); return x;
}
function toast(t) { const el = $('#toast'); el.textContent = t; el.style.display = 'block'; clearTimeout(toastTimer); toastTimer = setTimeout(() => el.style.display = 'none', 4500); }
async function refresh(render = true) { S.data = await api('state'); if (render) draw(); }
function go(path) { history.pushState({}, '', path); S.screen = '0'; S.activePin = ''; S.showBefore = false; S.fitPending = true; draw(); }
window.onpopstate = () => draw();

// Redraw without losing scroll position; skipped for the player so the running prototype is never reloaded.
function draw() {
  if (!S.data.project.length) return;
  const { r, b, v } = current();
  if (r.view === 'boards' && r.mode === 'review' && b && v && !r.variantId) history.replaceState({}, '', boardPath(b, 'review', v.id));
  const sel = ['.workspace', '.project-panel', '.inspector'], same = S.lastPath === location.pathname, pos = same ? sel.map(s => [s, $(s)?.scrollTop || 0]) : [];
  $('#app').innerHTML = page();
  pos.forEach(([s, t]) => { const e = $(s); if (e) e.scrollTop = t; });
  S.lastPath = location.pathname; S.drawnSig = signature();
  if (location.hash && !same) document.getElementById(location.hash.slice(1))?.scrollIntoView();
  if (r.view === 'prototypes') S.playerFile = null;
  if (S.fitPending && document.querySelector('.frames,.review-area')) { S.fitPending = false; const z = Math.max(ZMIN, Math.min(100, fitZoom())); if (z !== S.zoom) { S.zoom = z; return draw(); } }
  overlayRegions();
  if (S.scrollTo) { document.getElementById(S.scrollTo)?.scrollIntoView({ block: 'nearest', inline: 'center' }); S.scrollTo = ''; }
}
function updateResearch() {
  if (route().view !== 'research') return;
  const t = $('#research-results'); if (t) t.innerHTML = renderResearchResults(route().project.id);
  const b = $('[data-action="run-research"]'); if (b) b.disabled = S.busy || researchJobs(S.data, route().project.id).some(j => ['queued', 'running'].includes(j.status));
  S.drawnSig = signature();
}

function modal(title, body, submit, onSubmit, cls = '') {
  const d = $('#dialog'); d.className = cls;
  d.innerHTML = `<form id="modal-form"><div class="row between"><h2>${title}</h2><button type="button" class="ghost" id="close-dialog" aria-label="Close">${icon('x')}</button></div>${body}<div class="row" style="justify-content:flex-end;margin-top:24px"><button type="button" id="cancel-dialog">Cancel</button><button class="primary">${submit}</button></div></form>`;
  d.showModal(); $('#close-dialog').onclick = $('#cancel-dialog').onclick = () => d.close();
  $('#modal-form').onsubmit = async e => {
    e.preventDefault(); const btn = e.submitter; if (btn) btn.disabled = true;
    try { await onSubmit(new FormData(e.target)); d.close(); await refresh(); } catch (err) { toast(err.message); } finally { if (btn) btn.disabled = false; }
  };
}
function confirmDialog(title, body, submit, run) { modal(title, body, submit, async () => { await run(); }); }
function openLive(v, sid) {
  const d = $('#dialog'); d.className = 'wide';
  d.innerHTML = `<div class="row between"><h2>Live preview · ${esc(v.runner_name)} v${v.version}</h2><button class="ghost" id="close-dialog" aria-label="Close">${icon('x')}</button></div><iframe class="live-frame" title="Live preview of generated screen" sandbox="allow-scripts" src="${live(v, sid)}"></iframe><p class="tiny muted">Sandboxed preview. Interactions are mocked; nothing is submitted.</p>`;
  d.showModal(); $('#close-dialog').onclick = () => d.close(); d.addEventListener('close', () => { d.innerHTML = ''; }, { once: true });
}

// Resolve the stable element ID under a pin by loading the screen in a hidden, script-disabled frame at screenshot size.
function elementAt(v, screenId, x, y) {
  return new Promise(resolve => {
    const f = document.createElement('iframe'); let done = false;
    const finish = id => { if (done) return; done = true; f.remove(); resolve(id); };
    f.setAttribute('sandbox', 'allow-same-origin'); f.setAttribute('aria-hidden', 'true'); f.tabIndex = -1;
    f.style.cssText = 'position:fixed;left:-9999px;top:0;width:720px;height:960px;border:0;visibility:hidden';
    f.onload = () => { try { finish(f.contentDocument.elementFromPoint(x * 720, y * 960)?.closest('[data-design-id]')?.dataset.designId || null); } catch { finish(null); } };
    f.src = live(v, screenId); document.body.appendChild(f); setTimeout(() => finish(null), 4000);
  });
}

// Outline the elements a revision changed. Geometry comes from a hidden, script-disabled frame at screenshot size.
function elementRects(v, screenId, ids) {
  const key = `${v.id}:${screenId}`; if (S.regionCache[key]) return Promise.resolve(S.regionCache[key]);
  return new Promise(resolve => {
    const f = document.createElement('iframe'); let done = false;
    const finish = r => { if (done) return; done = true; f.remove(); S.regionCache[key] = r; resolve(r); };
    f.setAttribute('sandbox', 'allow-same-origin'); f.setAttribute('aria-hidden', 'true'); f.tabIndex = -1; f.style.cssText = 'position:fixed;left:-9999px;top:0;width:720px;height:960px;border:0;visibility:hidden';
    f.onload = () => { try { const d = f.contentDocument, out = {}; d.querySelectorAll('[data-design-id]').forEach(el => { const r = el.getBoundingClientRect(); out[el.dataset.designId] = { x: r.left / 720, y: r.top / 960, w: r.width / 720, h: r.height / 960 }; }); finish(out); } catch { finish({}); } };
    f.src = live(v, screenId); document.body.appendChild(f); setTimeout(() => finish({}), 4000);
  });
}
async function overlayRegions() {
  const box = document.querySelector('[data-region-ids]'); if (!box) return;
  const v = S.data.variant.find(x => x.id === box.dataset.regionVariant), ids = box.dataset.regionIds.split(',').filter(Boolean); if (!v || !ids.length) return;
  const rects = await elementRects(v, box.dataset.regionScreen, ids), host = document.querySelector('[data-region-ids]'); if (!host || host !== box) return;
  box.innerHTML = ids.filter(id => rects[id] && rects[id].y < 1).map(id => { const r = rects[id]; return `<div class="region" style="left:${r.x * 100}%;top:${r.y * 100}%;width:${r.w * 100}%;height:${Math.min(r.h, 1 - r.y) * 100}%"><span>${esc(id)}</span></div>`; }).join('');
}

/* ---------- context drafts ---------- */
async function saveDraft() {
  const { p } = current(); let tokens;
  try { tokens = JSON.parse(S.draft.tokens); } catch { throw Error('Tokens must be valid JSON'); }
  const c = await api('context', { project_id: p.id, markdown: S.draft.markdown, tokens, rules: S.draft.rules.map(({ version, ...r }) => r) });
  S.draftFor = ''; await refresh(false); return c;
}
function syncDirty() {
  const { ctx } = current(), dirty = isDirty(ctx), tokenOk = !$('#token-err')?.textContent;
  const save = $('[data-action="save-context"]'), discard = $('[data-action="discard-draft"]'), b = $('#dirty-badge');
  if (save) save.disabled = !dirty || !tokenOk; if (discard) discard.disabled = !dirty;
  if (b) { b.className = 'badge ' + (dirty ? 'warn' : 'success'); b.textContent = dirty ? 'Unsaved changes' : 'Saved · version ' + (ctx.version || ''); }
}
function nextGuidanceId() { const n = Math.max(0, ...S.draft.rules.map(r => +(/^GUIDANCE-(\d+)$/.exec(r.id)?.[1] || 0))); return 'GUIDANCE-' + String(n + 1).padStart(3, '0'); }
function ruleModal(index = null) {
  const editing = index !== null, r = editing ? S.draft.rules[index] : { scope: 'project', severity: 'warning', verification: 'human_review', parameters: { max: 1 } };
  const opt = (v, cur, label = v) => `<option value="${v}" ${v === cur ? 'selected' : ''}>${label}</option>`;
  modal(editing ? 'Edit rule ' + esc(r.id) : 'Add a design rule', `<label for="r-id">Stable rule ID</label><input id="r-id" name="id" required pattern="[A-Za-z0-9_\\-]+" value="${esc(r.id || '')}" ${editing ? 'readonly' : ''} placeholder="COPY-002"><label for="r-desc">Description</label><input id="r-desc" name="description" required value="${esc(r.description || '')}"><div class="formgrid"><div><label for="r-scope">Scope</label><select id="r-scope" name="scope">${['workspace', 'project', 'job'].map(x => opt(x, r.scope)).join('')}</select></div><div><label for="r-sev">Severity</label><select id="r-sev" name="severity">${['error', 'warning', 'info'].map(x => opt(x, r.severity)).join('')}</select></div></div><label for="r-ver">Verification</label><select id="r-ver" name="verification">${opt('human_review', r.verification, 'Designer review')}${opt('deterministic', r.verification, 'Deterministic · primary action count')}${opt('advisory_model', r.verification, 'Advisory model opinion (never shown as verified)')}</select><label for="r-max">Maximum primary actions (deterministic only)</label><input id="r-max" name="max" type="number" min="0" value="${r.parameters?.max ?? 1}"><label for="r-just">Justification when overriding a broader rule (optional)</label><input id="r-just" name="justification" value="${esc(r.justification || '')}">`, 'Save rule', f => {
    const id = f.get('id').trim(), dup = S.draft.rules.some((x, i) => x.id === id && x.scope === f.get('scope') && i !== index);
    if (!/^[A-Za-z0-9_-]+$/.test(id)) throw Error('Rule IDs may only contain letters, numbers, - and _'); if (dup) throw Error('A rule with this ID already exists in this scope');
    const rule = { ...r, id, description: f.get('description').trim(), scope: f.get('scope'), severity: f.get('severity'), verification: f.get('verification'), enabled: r.enabled !== false };
    if (rule.verification === 'deterministic') { rule.check = 'primary_action_count'; rule.parameters = { max: Number(f.get('max')) }; } else { delete rule.check; delete rule.parameters; }
    if (f.get('justification').trim()) rule.justification = f.get('justification').trim(); else delete rule.justification;
    if (editing) S.draft.rules[index] = rule; else S.draft.rules.push(rule);
  });
}

/* ---------- board / research modals ---------- */
const parseScreens = t => t.split('\n').map(x => x.trim()).filter(Boolean);
function runnerChecklist(name = 'runners') {
  const rs = enabledRunners(), defaults = new Set(rs.slice(0, 2).map(r => r.id));
  return rs.map(r => `<label class="row"><input name="${name}" type="checkbox" style="width:auto" value="${r.id}" ${defaults.has(r.id) ? 'checked' : ''}>${esc(r.name)} ${badge(r.type === 'fixture' ? 'Template fixture · offline' : 'Local agent')}</label>`).join('') || '<p class="muted">No enabled runners. Enable one in Settings → Agents.</p>';
}
function handoff(researchId) {
  const research = S.data.research.find(r => r.id === researchId), findings = findingsForHandoff(research), p = route().project, boards = S.data.board.filter(b => b.project_id === p.id), key = crypto.randomUUID();
  modal('Turn research into screens', `<div class="inline-note">${findings.length} findings will be copied into the board and supplied to every generation and revision. Source and verification labels are preserved.</div><details><summary>Included findings</summary>${findings.map(f => `<p>${esc(f.title)}</p>`).join('')}</details>
  <label>Destination</label><label class="row"><input type="radio" name="dest" value="new" checked style="width:auto"> New board, and generate now</label>${boards.length ? `<label class="row"><input type="radio" name="dest" value="existing" style="width:auto"> Attach to an existing board (replaces its pinned findings; generate again to use them)</label><label for="h-board">Existing board</label><select id="h-board" name="board">${boards.map(b => `<option value="${b.id}">${esc(b.title)}</option>`).join('')}</select>` : ''}
  <label>Reference images (optional)</label>${refPicker(new Set((S.data.job.find(j => j.id === research.job_id)?.references || []).map(r => r.id)), p.id)}<label for="h-title">New board title</label><input id="h-title" name="title" value="Research-led journey"><label for="h-brief">Design brief</label><textarea id="h-brief" name="brief" rows="3">${esc(research.brief)}</textarea><label for="h-screens">Screens · one per line, 2–5 screens</label><textarea id="h-screens" name="screens" rows="3">Eligibility\nYour details\nReview</textarea><label>Compare agents · choose at least two configurations</label>${runnerChecklist()}`, 'Continue', async f => {
    if (f.get('dest') === 'existing') { const b = await api('board-research', { board_id: f.get('board'), research_id: research.id, finding_ids: findings.map(x => x.id) }); await refresh(false); go(boardPath(b)); toast('Findings attached. Generate variants to use them.'); return; }
    const screens = parseScreens(f.get('screens')); if (screens.length < 2 || screens.length > 5) throw Error('Choose 2–5 screens'); if (f.getAll('runners').length < 2) throw Error('Select at least two runner configurations');
    const result = await api('research-board', { project_id: p.id, research_id: research.id, finding_ids: findings.map(x => x.id), title: f.get('title'), brief: f.get('brief'), screens, runner_ids: f.getAll('runners'), reference_ids: f.getAll('references'), idempotency_key: key });
    await refresh(false); go(boardPath(result.board)); toast('Research carried forward. Screen generation started.');
  });
}
function generateModal() {
  const { b, ctx } = current(), key = crypto.randomUUID(), dirty = isDirty(ctx), found = boardResearch(b).length;
  const det = ctx.effective_rules.filter(r => r.verification === 'deterministic').length;
  modal('Generate independent variants', `<p class="muted">Every runner receives the same brief and the same immutable context snapshot, and cannot see the others’ output.</p>
  <div class="inline-note">Context <strong>v${ctx.version || '?'}</strong> · <span class="mono">${esc(ctx.hash.slice(0, 8))}</span> · ${ctx.effective_rules.length} effective rules (${det} deterministic, ${ctx.effective_rules.length - det} for designer review)${found ? ` · ${found} research findings included` : ''}${dirty ? '<br><strong>Unsaved guideline edits are not included.</strong> Save a version first.' : ''}</div>
  ${ctx.overrides.length ? `<details open><summary>${ctx.overrides.length} rule override${ctx.overrides.length === 1 ? '' : 's'} in force</summary>${overrideList(ctx.overrides)}</details>` : ''}
  <label for="g-brief">Board brief</label><textarea id="g-brief" name="brief" rows="3">${esc(b.brief)}</textarea><label>Reference images (optional)</label>${refPicker(new Set(b.reference_ids || []), ctx.project_id)}<label>Runner configurations · select at least two</label>${runnerChecklist()}<p class="tiny muted">Template fixtures apply tokens and simple colour directives. Choose a local coding agent for broader design rules. Configure agents in <a href="/settings/agents" style="color:#4f52c9">Settings → Agents</a>.</p>`, 'Generate variants', async f => {
    const runners = f.getAll('runners'); if (runners.length < 2) throw Error('Select at least two runner configurations');
    await api('generate', { project_id: ctx.project_id, board_id: b.id, brief: f.get('brief'), runner_ids: runners, reference_ids: f.getAll('references'), idempotency_key: key });
    await refresh(false); go(boardPath(b)); toast('Independent jobs queued');
  });
}
function approveModal() {
  const { v, b } = current(), checks = checksOf(v), failed = checks.filter(c => c.outcome === 'fail'), open = unresolvedReviews(v);
  modal('Approve & build prototype', `<p>Approve <strong>${esc(v.runner_name)} v${v.version}</strong> of “${esc(b.title)}”.</p><ul class="tiny"><li>Approval pins this exact version. It stays immutable; later changes create new versions.</li><li>A static click-through bundle is built from it and opens in the player.</li>${v.review_state === 'pending' ? '<li>This revision will be accepted.</li>' : ''}${b.blind && !b.revealed ? '<li><strong>Approving counts as your blind choice and reveals runner identities.</strong></li>' : ''}</ul>${failed.length ? `<div class="inline-note warn"><strong>${failed.length} deterministic check${failed.length === 1 ? '' : 's'} failed:</strong> ${failed.map(c => esc(c.check)).join('; ')}.</div>` : ''}${open.length ? `<div class="inline-note warn">${open.length} item${open.length === 1 ? '' : 's'} still need designer review.</div>` : ''}`, 'Approve & build', async () => {
    const res = await api('approve', { id: v.id }); await refresh(false); go(nav('prototypes') + '/' + res.prototype.id); toast('Approved and locked. Prototype built.');
  });
}
async function pinModal(x, y) {
  const { v, b } = current(), el = await elementAt(v, S.screen, x, y);
  modal('Add screen feedback', `<p class="tiny muted">${esc(b.screens[Number(S.screen)])} · <span id="pin-anchor">${el ? `anchored to element “${esc(el)}”` : 'no stable element here; using coordinates'}</span></p><label for="pin-comment">What should change?</label><textarea id="pin-comment" name="comment" rows="4" required autofocus placeholder="Move the explanatory text below the heading."></textarea><div class="formgrid"><div><label for="pin-x">Horizontal position %</label><input id="pin-x" name="x" type="number" min="0" max="100" value="${Math.round(x * 100)}"></div><div><label for="pin-y">Vertical position %</label><input id="pin-y" name="y" type="number" min="0" max="100" value="${Math.round(y * 100)}"></div></div>`, 'Add comment', async f => {
    const nx = Number(f.get('x')) / 100, ny = Number(f.get('y')) / 100, moved = Math.abs(nx - x) > .006 || Math.abs(ny - y) > .006;
    const created = await api('annotation', { variant_id: v.id, screen: S.screen, x: nx, y: ny, comment: f.get('comment'), element_id: moved ? await elementAt(v, S.screen, nx, ny) : el });
    S.activePin = created.id; S.inspTab = 'comments';
  });
}

/* ---------- actions ---------- */
async function action(name) {
  const { p, b, v, ctx, vs } = current();
  switch (name) {
    case 'new-project': return modal('Create a project', '<label for="np-name">Project name</label><input id="np-name" name="name" required placeholder="Credit Card Application"><label for="np-desc">Purpose</label><textarea id="np-desc" name="description" rows="3"></textarea>', 'Create project', async f => { const created = await api('project', Object.fromEntries(f)); await refresh(false); go('/projects/' + created.id + '/context'); });
    case 'project-menu': return modal('Project settings', `<label for="pm-name">Project name</label><input id="pm-name" name="name" value="${esc(p.name)}" required><label><input type="checkbox" name="archived" style="width:auto"> Archive project (hidden from the list; restorable)</label>`, 'Save', async f => { await api('update-project', { id: p.id, name: f.get('name'), archived: !!f.get('archived') }); if (f.get('archived')) go('/projects'); });
    case 'new-board': return modal('Create a screen board', '<label for="nb-title">Board title</label><input id="nb-title" name="title" required placeholder="Application Journey"><label for="nb-brief">Design brief</label><textarea id="nb-brief" name="brief" required rows="3"></textarea><label for="nb-screens">Screens · one per line, 2–5 screens</label><textarea id="nb-screens" name="screens" rows="4">Eligibility\nYour details\nReview</textarea>', 'Create board', async f => { const screens = parseScreens(f.get('screens')); if (screens.length < 2 || screens.length > 5) throw Error('Choose 2–5 screens'); const x = await api('board', { project_id: p.id, title: f.get('title'), brief: f.get('brief'), screens }); await refresh(false); go(boardPath(x)); });
    case 'generate': if (!b) return toast('Create a board first'); if (route().view === 'context' && isDirty(ctx)) { await saveDraft(); toast('Saved your guideline edits as a new version'); } return generateModal();
    case 'save-context': { const c = await saveDraft(); toast('Saved context version ' + (c.version || '')); draw(); return; }
    case 'discard-draft': S.draftFor = ''; return draw();
    case 'add-rule': return ruleModal();
    case 'quick-rules': { const lines = parseScreens($('#quick-rules').value); if (!lines.length) return toast('Enter at least one instruction'); lines.forEach(description => S.draft.rules.push({ id: nextGuidanceId(), description, scope: 'project', severity: 'warning', verification: 'human_review', enabled: true })); return draw(); }
    case 'apply-rules-json': { let rules; try { rules = JSON.parse($('#rules-json').value); if (!Array.isArray(rules)) throw 0; } catch { return toast('Rules JSON must be a valid array'); } S.draft.rules = rules; return draw(); }
    case 'run-research': {
      if (S.busy || researchJobs(S.data, p.id).some(j => ['queued', 'running'].includes(j.status))) return;
      const brief = $('#research-brief').value.trim(); if (!brief) return toast('Enter a research question first');
      S.busy = true; updateResearch();
      try { await api('research', { project_id: p.id, brief, sources: parseSources($('#sources').value), reference_ids: [...document.querySelectorAll('#research-refs input[name=references]:checked')].map(i => i.value), runner_ids: [$('#research-runner').value], idempotency_key: crypto.randomUUID() }); await refresh(false); } finally { S.busy = false; updateResearch(); }
      return;
    }
    case 'review': S.tool = 'comment'; if (v) go(boardPath(b, 'review', v.id)); return;
    case 'revise': {
      const ids = S.data.annotation.filter(a => a.variant_id === v.id && a.status !== 'applied' && a.selected !== false).map(a => a.id); if (!ids.length) return toast('Select at least one open pin');
      await api('revise', { project_id: p.id, board_id: b.id, parent_id: v.id, brief: b.brief, runner_ids: v.runner_id ? [v.runner_id] : undefined, annotation_ids: ids, scope_mode: S.regionOnly ? 'region' : 'screen', idempotency_key: crypto.randomUUID() });
      toast('Revision queued; the parent version is preserved'); await refresh(false); go(boardPath(b)); return;
    }
    case 'approve': if (!v) return toast('Generate a variation first'); return approveModal();
    case 'preview': { const proto = prototypeOf(vs.find(x => x.approved)); if (!proto) return toast('Approve a board variation before previewing'); go(nav('prototypes') + '/' + proto.id); return; }
    case 'exit-player': { const proto = S.data.prototype.find(x => x.id === route().prototypeId); const board = S.data.board.find(x => x.id === proto?.board_id); go(board ? boardPath(board) : nav('boards')); return; }
    case 'restart': { const proto = S.data.prototype.find(x => x.id === route().prototypeId); $('#player').src = protoLive(proto, proto.start_screen_id); return; }
    case 'zoom-in': return setZoom(S.zoom + 10);
    case 'zoom-out': return setZoom(S.zoom - 10);
    case 'zoom-reset': return setZoom(100);
    case 'zoom-fit': return setZoom(fitZoom());
    case 'toggle-reverted': S.showReverted = !S.showReverted; return draw();
    case 'show-before': S.showBefore = true; return draw();
    case 'show-after': S.showBefore = false; return draw();
    case 'scan-agents': S.agents = await api('local-agents'); toast('Installed agents refreshed'); return draw();
    case 'add-local-runner': if (!$('#local-agent').value) return toast('Choose an installed coding agent'); await api('local-runner', { agent: $('#local-agent').value, model: $('#local-model').value.trim() }); toast('Local agent configuration added'); break;
  }
  await refresh();
}

/* ---------- canvas: zoom, fit, keep-screen navigation ---------- */
const FRAME_W = 260, FLOW_W = 44, ZMIN = 25, ZMAX = 200;
function setZoom(z) { S.zoom = Math.round(Math.min(ZMAX, Math.max(ZMIN, z))); draw(); }
function fitZoom() {
  const c = $('.canvas'); if (!c) return 100; const r = route();
  if (r.mode === 'review') return Math.floor(((window.innerHeight - 320) * .75) / 560 * 100);
  const frames = Math.max(1, ...[...document.querySelectorAll('.frames')].map(f => f.querySelectorAll('.fframe').length));
  return Math.floor((c.clientWidth - 90) / (frames * FRAME_W + (frames - 1) * FLOW_W + 48) * 100);
}
function keepNav(path, scrollTo = '') { history.pushState({}, '', path); S.activePin = ''; S.showBefore = false; S.scrollTo = scrollTo; draw(); }

/* ---------- reference images ---------- */
const REF_TYPES = ['image/png', 'image/jpeg', 'image/webp', 'image/gif'], REF_MAX = 5_000_000;
const toBase64 = file => new Promise((res, rej) => { const r = new FileReader(); r.onload = () => res(String(r.result).split(',')[1]); r.onerror = rej; r.readAsDataURL(file); });
function rerenderPickers(newIds = []) {
  document.querySelectorAll('[data-ref-picker]').forEach(el => { const sel = new Set([...el.querySelectorAll('input[name=references]:checked')].map(i => i.value)); newIds.forEach(i => sel.add(i)); el.outerHTML = refPicker(sel); });
}
async function uploadRefs(files) {
  const p = route().project, ids = [];
  for (const f of files) {
    if (!REF_TYPES.includes(f.type)) { toast(`${f.name}: use PNG, JPEG, WebP or GIF`); continue; }
    if (f.size > REF_MAX) { toast(`${f.name} is larger than 5 MB`); continue; }
    try { ids.push((await api('reference-upload', { project_id: p.id, name: f.name.replace(/\.[^.]+$/, ''), data: await toBase64(f) })).id); } catch (err) { toast(err.message); }
  }
  if (!ids.length) return;
  await refresh(false); rerenderPickers(ids); if (route().view === 'references') draw(); toast(`${ids.length} reference image${ids.length === 1 ? '' : 's'} added`);
}
function openRef(value) {
  const [src, file, ...n] = value.split(':'), url = src === 'project' ? `/assets/projects/${route().project.id}/references/${file}` : `/assets/jobs/${src}/references/${file}`, d = $('#dialog');
  d.className = 'wide'; d.innerHTML = `<div class="row between"><h2>${esc(n.join(':'))}</h2><button class="ghost" id="close-dialog" aria-label="Close">${icon('x')}</button></div><img class="lightbox" src="${url}" alt="${esc(n.join(':'))}">`; d.showModal(); $('#close-dialog').onclick = () => d.close(); d.addEventListener('close', () => { d.innerHTML = ''; }, { once: true });
}

/* ---------- events ---------- */
const post = (a, d) => api(a, d);
async function onClick(e) {
  let a = e.target.closest('a');
  if (a && a.getAttribute('href')?.startsWith('/') && !a.target && !a.hasAttribute('download') && !a.href.includes('/api/export/')) { e.preventDefault(); return go(a.getAttribute('href')); }
  const t = e.target, q = sel => t.closest(sel), { b, v } = current(); let el;
  if ((el = q('[data-handoff]'))) return handoff(el.dataset.handoff);
  if ((el = q('[data-action]'))) return action(el.dataset.action);
  if ((el = q('[data-blind-toggle]'))) { await post('board-blind', { board_id: b.id, blind: el.dataset.blindToggle === 'true' }); toast(el.dataset.blindToggle === 'true' ? 'Blind mode on: runner identities are hidden' : 'Blind mode off'); return refresh(); }
  if ((el = q('[data-blind-pick]'))) { const id = el.dataset.blindPick, pv = S.data.variant.find(x => x.id === id); return modal('Choose this option', `<p>You are choosing <strong>${esc(pv.runner_name)} v${pv.version}</strong>. Runner identities will be revealed afterwards and your choice is recorded.</p><label for="bp-r">Why? (optional)</label><textarea id="bp-r" name="reason" rows="3" placeholder="e.g. clearer explanation of why we ask for income"></textarea>`, 'Choose and reveal', async f => { const board = await post('blind-choice', { board_id: b.id, variant_id: id, reason: f.get('reason') }); toast(`Revealed: ${board.blind_choice.label ? 'Option ' + board.blind_choice.label + ' was ' : ''}${board.blind_choice.runner_name}`); }); }
  if ((el = q('[data-blind-reveal]'))) return confirmDialog('Reveal runner identities?', '<p>Without choosing, the comparison ends and you will see which runner made each option. You cannot re-enable blind mode for this board afterwards.</p>', 'Reveal', async () => { await post('blind-choice', { board_id: b.id }); toast('Identities revealed'); });
  if ((el = q('[data-accept]'))) { await post('accept-revision', { id: el.dataset.accept }); toast('Revision accepted'); return refresh(); }
  if ((el = q('[data-revert]'))) { const id = el.dataset.revert, rv = S.data.variant.find(x => x.id === id); return confirmDialog('Revert this revision?', `<p>v${rv.version} stays in history (hidden by default) and the parent version becomes the working version again. Nothing is deleted.</p>`, 'Revert revision', async () => { await post('revert-revision', { id }); S.selectedVariant = rv.parent_id; toast('Reverted to the parent version'); }); }
  if ((el = q('[data-cancel-job]'))) { await post('cancel-job', { id: el.dataset.cancelJob }); toast('Cancelling…'); return refresh(); }
  if ((el = q('[data-retry-job]'))) { await post('retry-job', { id: el.dataset.retryJob }); toast('Retry queued with the same inputs'); return refresh(); }
  if ((el = q('[data-open-live]'))) return openLive(S.data.variant.find(x => x.id === el.dataset.openLive), el.dataset.screenId);
  if ((el = q('[data-review]'))) return go(boardPath(b, 'review', el.dataset.review));
  if ((el = q('[data-select-screen]'))) { if (S.screen === el.dataset.selectScreen && S.selectedVariant === el.dataset.selectVariant) return; S.screen = el.dataset.selectScreen; S.selectedVariant = el.dataset.selectVariant; return draw(); }
  if ((el = q('[data-screen]'))) { S.screen = el.dataset.screen; return draw(); }
  if ((el = q('[data-parent]'))) { S.selectedVariant = el.dataset.parent; return route().mode === 'review' ? go(boardPath(b, 'review', el.dataset.parent)) : draw(); }
  if ((el = q('[data-pin-edit]'))) { const pin = S.data.annotation.find(x => x.id === el.dataset.pinEdit); return modal('Edit feedback', `<label for="pe-c">Comment</label><textarea id="pe-c" name="comment" rows="4" required>${esc(pin.comment)}</textarea>`, 'Save', f => post('annotation-update', { id: pin.id, comment: f.get('comment') })); }
  if ((el = q('[data-pin-delete]'))) { const id = el.dataset.pinDelete; return confirmDialog('Delete this pin?', '<p>The feedback pin will be removed. Pins already used in a revision cannot be deleted.</p>', 'Delete pin', () => post('annotation-delete', { id })); }
  if ((el = q('[data-pin-focus]'))) { S.activePin = el.dataset.pinFocus; S.screen = el.dataset.pinScreen; return route().mode === 'review' ? draw() : go(boardPath(b, 'review', v.id)); }
  if ((el = q('[data-pin]'))) { S.activePin = el.dataset.pin; return draw(); }
  if ((el = q('[data-review-check]'))) { await post('review-check', { variant_id: v.id, index: Number(el.dataset.reviewCheck), decision: el.dataset.decision }); return refresh(); }
  if ((el = q('[data-test-runner]'))) { const id = el.dataset.testRunner, r = await post('test-runner', { id }); const out = $('#test-' + id); if (out) out.textContent = r.message; return toast(r.message); }
  if ((el = q('[data-save-runner]'))) { const id = el.dataset.saveRunner, row = el.closest('[data-runner]'), data = { id, name: row.querySelector('[data-runner-name]').value, enabled: row.querySelector('[data-runner-enabled]').checked }, model = row.querySelector('[data-runner-model]'); if (model) data.model = model.value; const env = row.querySelector('[data-runner-env]'); if (env) data.env_allowlist = env.value.split(/[\s,]+/).filter(Boolean); await post('update-runner', data); toast('Runner saved'); return refresh(); }
  if ((el = q('[data-delete-runner]'))) { const id = el.dataset.deleteRunner; return confirmDialog('Delete runner configuration?', `<p>${esc(runnerOf(id)?.name)} will be removed. Past jobs and variations keep their history.</p>`, 'Delete', () => post('delete-runner', { id })); }
  if ((el = q('[data-restore-project]'))) { await post('update-project', { id: el.dataset.restoreProject, archived: false }); return refresh(); }
  if ((el = q('[data-hist-filter]'))) { S.histFilter = el.dataset.histFilter; return draw(); }
  if ((el = q('[data-load-version]'))) { const c = S.data.context.find(x => x.id === el.dataset.loadVersion), cur = current().ctx; S.draft = { markdown: c.markdown, tokens: JSON.stringify(c.tokens, null, 2), rules: structuredClone(c.rules) }; S.draftFor = cur.id; toast(`Loaded v${c.version} into the editor. Save to create a new version.`); window.scrollTo(0, 0); $('#main')?.scrollTo(0, 0); return draw(); }
  if ((el = q('[data-rule-edit]'))) return ruleModal(Number(el.dataset.ruleEdit));
  if ((el = q('[data-rule-delete]'))) { S.draft.rules.splice(Number(el.dataset.ruleDelete), 1); return draw(); }
  if ((el = q('[data-device]'))) return setDevice(el.dataset.device);
  if ((el = q('[data-player]'))) return $('#player')?.contentWindow.postMessage({ cmd: el.dataset.player }, '*');
  if ((el = q('[data-player-state]'))) return $('#player')?.contentWindow.postMessage({ cmd: 'state', name: el.dataset.playerState }, '*');
  if ((el = q('[data-layer-variant]'))) { const id = el.dataset.layerVariant, sc = el.dataset.layerScreen; S.selectedVariant = id; if (sc !== undefined) S.screen = sc; const r = route(); return keepNav(r.mode === 'review' ? boardPath(b, 'review', id) : boardPath(b), r.mode === 'review' ? '' : `frame-${id}-${S.screen}`); }
  if ((el = q('[data-tool]'))) { S.tool = el.dataset.tool; return draw(); }
  if ((el = q('[data-insp-tab]'))) { S.inspTab = el.dataset.inspTab; return draw(); }
  if ((el = q('[data-pin-close]'))) { S.activePin = ''; return draw(); }
  if ((el = q('[data-ref-open]'))) return openRef(el.dataset.refOpen);
  if ((el = q('[data-ref-delete]'))) { const id = el.dataset.refDelete; return confirmDialog('Delete this reference image?', '<p>It is removed from the library. Jobs that already used it keep their own copy for history and retries.</p>', 'Delete image', () => post('reference-delete', { id })); }
  if (q('.pop')) return;
  if ((el = q('#pin-area')) && S.tool !== 'comment' && !S.showBefore) { if (S.activePin) { S.activePin = ''; draw(); } return; }
  if ((el = q('#pin-area')) && !S.showBefore) { const rect = el.getBoundingClientRect(); return pinModal(Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width)), Math.min(1, Math.max(0, (e.clientY - rect.top) / rect.height))); }
}
function setDevice(d) {
  S.device = d; const proto = S.data.prototype.find(x => x.id === route().prototypeId); if (!proto) return;
  $('.device').className = 'device ' + d; document.querySelectorAll('[data-device]').forEach(b => { b.classList.toggle('on', b.dataset.device === d); b.setAttribute('aria-pressed', b.dataset.device === d); });
  $('#player-info').innerHTML = playerInfo(proto, S.playerFile || proto.screens.find(s => s.id === proto.start_screen_id).file.split('/').pop());
}
document.addEventListener('click', async e => { try { await onClick(e); } catch (err) { toast(err.message); } });
// <img> errors do not bubble; catch them in the capture phase (inline handlers are blocked by the CSP).
document.addEventListener('error', e => { const i = e.target; if (i?.tagName !== 'IMG' || !i.dataset.fallback) return; const d = document.createElement('div'); d.className = 'nothumb'; d.textContent = i.dataset.fallback; i.replaceWith(d); }, true);
document.addEventListener('dblclick', e => { const el = e.target.closest('[data-select-screen]'); if (el) openLive(S.data.variant.find(x => x.id === el.dataset.selectVariant), el.dataset.selectScreen); });
document.addEventListener('keydown', e => {
  const typing = e.target.matches?.('input,textarea,select,[contenteditable]') || $('#dialog').open;
  if (!typing && !e.ctrlKey && !e.metaKey && !e.altKey && route().view === 'boards' && route().boardId) {
    const k = e.key; if (k === 'v' || k === 'V') { S.tool = 'move'; return draw(); } if (k === 'c' || k === 'C') { S.tool = 'comment'; return draw(); }
    if (k === '+' || k === '=') return setZoom(S.zoom + 10); if (k === '-') return setZoom(S.zoom - 10); if (k === '0') return setZoom(100); if (k === '1') return setZoom(fitZoom());
    if (k === 'Escape' && S.activePin) { S.activePin = ''; return draw(); }
  } if ((e.key === 'Enter' || e.key === ' ') && e.target.matches?.('[role=button]') && !e.target.closest('dialog')) { e.preventDefault(); if (e.target.id === 'pin-area' && !S.showBefore) pinModal(.5, .5); else e.target.click(); } });
document.addEventListener('wheel', e => { if (!e.ctrlKey || !e.target.closest?.('.canvas')) return; e.preventDefault(); if (S.wheelBusy) return; S.wheelBusy = true; requestAnimationFrame(() => { S.wheelBusy = false; }); setZoom(S.zoom + (e.deltaY < 0 ? 10 : -10)); }, { passive: false });
document.addEventListener('dragover', e => { const z = e.target.closest?.('[data-dropzone]'); if (z) { e.preventDefault(); z.classList.add('over'); } });
document.addEventListener('dragleave', e => e.target.closest?.('[data-dropzone]')?.classList.remove('over'));
document.addEventListener('drop', e => { const z = e.target.closest?.('[data-dropzone]'); if (!z) return; e.preventDefault(); z.classList.remove('over'); uploadRefs([...e.dataTransfer.files]).catch(err => toast(err.message)); });
document.addEventListener('paste', e => { if (!document.querySelector('[data-dropzone]')) return; const files = [...(e.clipboardData?.files || [])].filter(f => f.type.startsWith('image/')); if (files.length) { e.preventDefault(); uploadRefs(files).catch(err => toast(err.message)); } });
document.addEventListener('input', e => {
  const f = e.target.dataset.draft; if (!f || !S.draft) return; S.draft[f] = e.target.value;
  if (f === 'markdown') $('#md-preview').innerHTML = renderMarkdown(e.target.value);
  if (f === 'tokens') { const t = tokenPanel(e.target.value); $('#token-table').innerHTML = t.table; $('#token-err').textContent = t.err; }
  syncDirty();
});
document.addEventListener('change', async e => {
  try {
    const t = e.target, d = t.dataset;
    if (t.matches('[data-region-only]')) { S.regionOnly = t.checked; return draw(); }
    if (t.matches('[data-show-regions]')) { S.showRegions = t.checked; return draw(); }
    if (t.matches('[data-ref-upload]')) { const files = [...t.files]; t.value = ''; return await uploadRefs(files); }
    if (t.matches('.refitem input')) return t.closest('.refitem').classList.toggle('on', t.checked);
    if (d.refName !== undefined || d.refNote !== undefined) { const id = d.refName ?? d.refNote; await post('reference-update', { id, [d.refName !== undefined ? 'name' : 'note']: t.value }); return refresh(false); }
    if (d.finding) { await post('finding', { id: d.finding, research_id: d.research, selected: t.checked }); await refresh(false); return updateResearch(); }
    if (d.pinSelect) { await post('annotation-update', { id: d.pinSelect, selected: t.checked }); return refresh(); }
    if (d.ruleToggle !== undefined) { S.draft.rules[Number(d.ruleToggle)].enabled = t.checked; return draw(); }
    if (d.reviewVariant !== undefined) return go(boardPath(current().b, 'review', t.value));
    if (d.compareSide) { const q = new URLSearchParams(location.search); q.set(d.compareSide, t.value); history.replaceState({}, '', location.pathname + '?' + q); return draw(); }
    if (t.id === 'token-file') { const file = t.files[0]; if (!file) return; if (file.size > 200000) throw Error('Token file is too large'); const parsed = JSON.parse(await file.text()); S.draft.tokens = JSON.stringify(parsed, null, 2); return draw(); }
    if (t.id === 'local-agent') { const a = S.agents.find(a => a.id === t.value); $('#agent-path').textContent = a?.executable || ''; $('#model-list').innerHTML = (a?.models || []).map(m => `<option value="${esc(m)}">`).join(''); $('#model-source').textContent = a?.model_source || ''; $('#local-model').value = ''; }
  } catch (err) { toast(err.message); }
});
// Player ↔ prototype pages: only messages from the player frame itself are trusted, and only used to update the info strip.
window.addEventListener('message', e => {
  const frame = $('#player'); if (!frame || e.source !== frame.contentWindow || e.data?.type !== 'screen') return;
  const proto = S.data.prototype.find(x => x.id === route().prototypeId); if (!proto) return;
  S.playerFile = String(e.data.file || '').replace(/[^\w.\-]/g, ''); $('#player-info').innerHTML = playerInfo(proto, S.playerFile);
});

/* ---------- boot & polling ---------- */
await refresh(false); S.agents = await api('local-agents');
if (location.pathname === '/') { const p = S.data.project.find(x => !x.archived), b = S.data.board.find(x => x.project_id === p?.id); history.replaceState({}, '', p ? `/projects/${p.id}/boards${b ? '/' + b.id : ''}` : '/projects'); }
draw();
setInterval(async () => {
  try {
    S.data = await api('state'); if (signature() === S.drawnSig) return;
    const view = route().view; if (view === 'prototypes' || $('#dialog').open) return;
    if (view === 'research') return updateResearch();
    const a = document.activeElement; if (a && $('#app').contains(a) && /^(INPUT|TEXTAREA|SELECT)$/.test(a.tagName)) return;
    draw();
  } catch { /* server briefly unavailable; try again next tick */ }
}, 1800);
