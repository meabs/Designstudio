// Dialogs and imperative actions (ported from the old app.js action()/modal code).
import { useEffect, useRef, useState } from 'react';
import { useData, useUi, profileCtx, profilesOf, api, refresh, getData, ui, runnerOf, enabledRunners, img, live, jobRefUrl, checksOf, unresolvedReviews, prototypeOf, protoLive, dataStore, isDirty, ctxVersion, rescanAgents, referencesOf, ensureDraft } from '@/lib/store';
import { askRunner } from '@/assist';
import { navigate, getCurrent, nav, boardPath, parseRoute, useCurrent } from '@/lib/router';
import { uuid, fmtHash, esc } from '@/lib/format';
import { findingsForHandoff, handoffBrief, parseSources, boardResearch, researchJobs } from '@/lib/research';
import { elementAt } from '@/lib/dom';
import { openDialog, confirmDialog, closeDialog, toast, Tag, Note, Field } from '@/components/app/feedback';
import { RefPicker } from '@/components/app/refs';
import { EstimateBox } from '@/components/app/progress';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Ic } from '@/components/app/icons';
import { LivePreview, GenProfiles } from '@/tools';
import { frameOf, MAX_SCREENS, TARGETS } from '@/lib/frame';
import { cn } from '@/lib/utils';

const parseLines = (t: string) => t.split('\n').map((x) => x.trim()).filter(Boolean);
export const nativeSelect = 'h-9 w-full rounded-lg border border-input bg-background px-3 text-sm shadow-xs/5 outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/24';
const checkRow = 'row flex items-center gap-2 text-sm font-normal';

export function RunnerChecklist({ name = 'runners' }: { name?: string }) {
  const rs = enabledRunners(); const defaults = new Set(rs.slice(0, 2).map((r) => r.id));
  if (!rs.length) return <p className="text-sm text-muted-foreground">No enabled runners. Enable one in Settings → Agents.</p>;
  return <>{rs.map((r) => <label key={r.id} className={checkRow}><input name={name} type="checkbox" value={r.id} defaultChecked={defaults.has(r.id)} className="size-4" />{r.name} <Tag>{r.type === 'fixture' ? 'Template fixture · offline' : 'Local agent'}</Tag></label>)}</>;
}

/* ---------- project / board ---------- */
export function newProject() {
  openDialog({ title: 'Create a project', submit: 'Create project', body: <><Field label="Project name" htmlFor="np-name"><Input id="np-name" name="name" required placeholder="Credit Card Application" /></Field><Field label="Purpose" htmlFor="np-desc"><Textarea id="np-desc" name="description" rows={3} /></Field></>,
    onSubmit: async (f) => { const created = await api('project', Object.fromEntries(f)); await refresh(); navigate('/projects/' + created.id + '/context'); } });
}
export function projectMenu() {
  const { p } = getCurrent(); if (!p) return;
  openDialog({ title: 'Project settings', submit: 'Save', body: <><Field label="Project name" htmlFor="pm-name"><Input id="pm-name" name="name" defaultValue={p.name} required /></Field><label className={checkRow}><input type="checkbox" name="archived" className="size-4" /> Archive project (hidden from the list; restorable)</label></>,
    onSubmit: async (f) => { await api('update-project', { id: p.id, name: f.get('name'), archived: !!f.get('archived') }); if (f.get('archived')) navigate('/projects'); } });
}
function TargetField({ id = 'nb-target' }: { id?: string }) {
  return <Field label="What are you designing?" htmlFor={id}><select id={id} name="target" defaultValue="website" className={nativeSelect}>{Object.entries(TARGETS).map(([k, t]) => <option key={k} value={k}>{t.label}{k === 'website' ? ' · 1440 wide' : k === 'mobile' ? ' · 390 × 844 phone' : ' · responsive, checked at both widths'}</option>)}</select></Field>;
}
export function newBoard() {
  const { p, r } = getCurrent();
  openDialog({ title: 'Create a screen board', submit: 'Create board', body: <><Field label="Board title" htmlFor="nb-title"><Input id="nb-title" name="title" required placeholder="Application Journey" /></Field><TargetField /><Field label="Design brief" htmlFor="nb-brief"><Textarea id="nb-brief" name="brief" required rows={3} /></Field><Field label={`Screens · one per line, 2–${MAX_SCREENS} screens`} htmlFor="nb-screens"><Textarea id="nb-screens" name="screens" rows={4} defaultValue={'Eligibility\nYour details\nReview'} /></Field></>,
    onSubmit: async (f) => { const screens = parseLines(String(f.get('screens'))); if (screens.length < 2 || screens.length > MAX_SCREENS) throw Error(`Choose 2–${MAX_SCREENS} screens`); const x = await api('board', { project_id: p.id, target: f.get('target'), title: f.get('title'), brief: f.get('brief'), screens }); await refresh(); navigate(boardPath(r, x)); } });
}

/* ---------- generate (with per-run experiment overrides, conflict preview and estimate) ---------- */
function collectOverrides(f: FormData) {
  const rules: any[] = []; const suspend: string[] = [];
  for (const [k, val] of f.entries()) if (k.startsWith('mode:')) { const id = k.slice(5); if (val === 'suspend') suspend.push(id); else if (val === 'replace' && String(f.get('text:' + id) || '').trim()) rules.push({ id, description: f.get('text:' + id), justification: 'Run-only experiment' }); }
  if (String(f.get('new-id') || '').trim() && String(f.get('new-text') || '').trim()) rules.push({ id: f.get('new-id'), description: f.get('new-text'), justification: 'Run-only experiment' });
  return { rules, suspend, prose: f.get('prose') || '', free: f.get('free') || '' };
}
function ConflictBox({ projectId }: { projectId: string }) {
  const ref = useRef<HTMLDivElement>(null); const [ws, setWs] = useState<any[]>([]);
  useEffect(() => {
    const form = ref.current?.closest('form'); if (!form) return; let timer: number; let seq = 0;
    const run = async () => {
      const f = new FormData(form); const my = ++seq;
      try { const w = await api('conflict-preview', { project_id: projectId, brief: f.get('brief'), overrides: collectOverrides(f), reference_ids: f.getAll('references'), profile_id: f.getAll('profiles')[0] }); if (my === seq) setWs(w); } catch { if (my === seq) setWs([]); }
    };
    const onInput = () => { clearTimeout(timer); timer = window.setTimeout(run, 350); };
    form.addEventListener('input', onInput); form.addEventListener('change', run); run();
    return () => { form.removeEventListener('input', onInput); form.removeEventListener('change', run); clearTimeout(timer); };
  }, [projectId]);
  return <div id="conflicts" ref={ref} aria-live="polite">{ws.length ? <Note><strong>Heads-up before you generate</strong> (advisory, keyword-based; it cannot read images)<ConflictList ws={ws} /></Note> : null}</div>;
}
export function ConflictList({ ws }: { ws: any[] }) {
  return <>{ws.map((w, i) => <div key={i} className={cn('conflict mt-2 rounded-md border bg-background px-2.5 py-2 text-[13px]', !w.overridden && 'warn border-warning/40')}><strong>{w.id}</strong> · {w.overridden ? 'overridden for this run' : w.topic === 'brief' ? 'worth rewording' : 'may block your brief'}<br /><span className="text-xs text-muted-foreground">{w.message} {w.action}</span></div>)}</>;
}
export function OverrideList({ overrides }: { overrides: any[] }) {
  return <>{overrides.map((x, i) => x.winner
    ? <div key={i} className="conflict mt-2 rounded-md border bg-background px-2.5 py-2 text-[13px]"><strong>{x.id}</strong> · <em>{x.winner.scope}</em> overrides <em>{x.superseded.scope}</em><br /><span className="text-xs text-muted-foreground">Superseded: “{x.superseded.description}” → now “{x.winner.description}” · {x.justification}</span></div>
    : <div key={i} className="conflict mt-2 rounded-md border bg-background px-2.5 py-2 text-[13px]"><strong>{x.id}</strong> · suspended<br /><span className="text-xs text-muted-foreground">“{x.superseded.description}” · {x.justification}</span></div>)}</>;
}
function RuleMode({ rule }: { rule: any }) {
  const [mode, setMode] = useState('keep');
  return (
    <div className="mb-2 flex items-start gap-2">
      <select name={`mode:${rule.id}`} aria-label={`${rule.id} for this run`} value={mode} onChange={(e) => setMode(e.target.value)} className={cn(nativeSelect, 'w-auto')}><option value="keep">Keep</option><option value="suspend">Suspend</option><option value="replace">Replace</option></select>
      <div className="flex-1"><strong className="text-xs">{rule.id}</strong> <span className="text-xs text-muted-foreground">{rule.description}</span>{mode === 'replace' && <Input name={`text:${rule.id}`} placeholder="Replacement wording" className="mt-1" />}</div>
    </div>
  );
}
function useGenCtx() {
  const data = useData(); const { p, ctx } = useCurrent(); const gp = useUi((x) => x.genProfile);
  return (gp && profileCtx(data.project.find((x: any) => x.id === p.id), gp, data)) || ctx;
}
function GenCtx({ dirty, found }: { dirty: boolean; found: number }) {
  const c = useGenCtx(); const here = useCurrent().ctx; const det = c.effective_rules.filter((x: any) => x.verification === 'deterministic').length; const named = profilesOf(useCurrent().p).length > 1;
  return <>
      <Note>{named ? <><strong>{profilesOf(useCurrent().p).find((x: any) => x.id === (c.profile_id || 'main'))?.name}</strong> · </> : null}Context <strong>v{ctxVersion(c)}</strong> · <span className="font-mono">{c.hash.slice(0, 8)}</span> · {c.effective_rules.length} effective rules ({det} deterministic, {c.effective_rules.length - det} for designer review){found ? ` · ${found} research findings included` : ''}{dirty && c.id === here?.id && <><br /><strong>Unsaved guideline edits are not included.</strong> Save a version first.</>}</Note>
      {c.overrides.length > 0 && <details open className="mb-3"><summary className="cursor-pointer text-sm">{c.overrides.length} rule override{c.overrides.length === 1 ? '' : 's'} in force</summary><OverrideList overrides={c.overrides} /></details>}
  </>;
}
function GenRules() { const c = useGenCtx(); return <div key={c.id}>{c.effective_rules.map((x: any) => <RuleMode key={x.id} rule={x} />)}</div>; }
export function generateModal() {
  const { b, ctx, r } = getCurrent(); if (!b || !ctx) return;
  const key = uuid(); const dirty = isDirty(ctx); const found = boardResearch(b).length;
  const det = ctx.effective_rules.filter((x: any) => x.verification === 'deterministic').length;
  openDialog({ title: 'Generate independent variants', submit: 'Generate variants', wide: true,
    body: <>
      <p className="mb-3 text-muted-foreground">Every runner receives the same brief and the same immutable context snapshot, and cannot see the others’ output.</p>
      <GenProfiles projectId={ctx.project_id} initial={ctx.profile_id || 'main'} />
      <GenCtx dirty={dirty} found={found} />
      <Field label="Board brief" htmlFor="g-brief"><Textarea id="g-brief" name="brief" rows={3} defaultValue={b.brief} /></Field>
      <ConflictBox projectId={ctx.project_id} />
      <details className="exp mb-3"><summary className="cursor-pointer text-sm font-medium">Experiment for this run only</summary>
        <p className="my-2 text-xs text-muted-foreground">Layered above DESIGN.md and the rules for these jobs only. Recorded on each job, never saved to the project guidelines.</p>
        <div className="mb-3 rounded-md border bg-background p-2.5" id="free-mode">
          <div className="mb-1 text-xs font-medium">Free exploration · think without the rulebook</div>
          <label className={checkRow}><input type="radio" name="free" value="" defaultChecked className="size-4" /> Normal · follow the guidelines and rules</label>
          <label className={checkRow}><input type="radio" name="free" value="rules" className="size-4" /> Loosen · no rules or checks; guidelines and tokens are inspiration only</label>
          <label className={checkRow}><input type="radio" name="free" value="open" className="size-4" /> Fully open · ignore the guidelines, tokens and rules entirely; the brief leads</label>
        </div>
        <Field label="Run-only brief (takes precedence over DESIGN.md prose)" htmlFor="g-prose"><Textarea id="g-prose" name="prose" rows={3} placeholder="e.g. Experiment: ignore the calm tone; use three equal doors and a hand-drawn voice." /></Field>
        <div className="mb-1 text-xs font-medium">Rules for this run</div><GenRules />
        <div className="mb-1 mt-2 text-xs font-medium">Add a rule for this run</div><div className="flex gap-2"><Input name="new-id" placeholder="ID, e.g. EXP-1" /><Input name="new-text" placeholder="Rule wording" /></div>
      </details>
      <div className="mb-3 rounded-md border bg-background p-2.5" id="explore-options">
        <div className="mb-1 text-xs font-medium">Explore</div>
        <label className={checkRow}><input type="checkbox" name="spread" defaultChecked className="size-4" /> Spread: give each agent a different direction (calm, bold, dense, warm…) <span className="text-xs text-muted-foreground">(on by default so designs differ; untick for a strict like-for-like comparison)</span></label>
        {!b.blind && <label className={checkRow}><input type="checkbox" name="pair" className="size-4" /> Rules vs free: also run a free version of each, to compare side by side <span className="text-xs text-muted-foreground">(doubles the runs)</span></label>}
      </div>
      <div className="mb-1 text-xs font-medium">Reference images (optional)</div><RefPicker selected={b.reference_ids || []} projectId={ctx.project_id} />
      <div className="mb-1 text-xs font-medium">Runner configurations · select at least two</div><RunnerChecklist />
      <div className="mt-3"><EstimateBox board={b} /></div>
      <p className="text-xs text-muted-foreground">Template fixtures apply tokens and simple colour directives. Choose a local coding agent for broader design rules. Configure agents in <a href="/settings/agents" className="underline" onClick={(e) => { e.preventDefault(); closeDialog(); navigate('/settings/agents'); }}>Settings → Agents</a>.</p>
    </>,
    onSubmit: async (f) => {
      const runners = f.getAll('runners'); if (runners.length < 2) throw Error('Select at least two runner configurations');
      const ov = collectOverrides(f); const pair = f.get('pair') === 'on'; const profile_ids = f.getAll('profiles').map(String); if (getData().project.find((x) => x.id === ctx.project_id) && profilesOf(getData().project.find((x) => x.id === ctx.project_id)).length > 1 && !profile_ids.length) throw Error('Choose at least one guidelines profile');
      // With a pair, the free level applies to the free half only; the other half runs as configured.
      await api('generate', { project_id: ctx.project_id, board_id: b.id, brief: f.get('brief'), runner_ids: runners, reference_ids: f.getAll('references'), overrides: pair ? { ...ov, free: '' } : ov, spread: f.get('spread') === 'on', ...(profile_ids.length > 1 ? { profile_ids } : profile_ids.length ? { profile_id: profile_ids[0] } : {}), ...(pair ? { pair_free: ov.free || 'open' } : {}), idempotency_key: key });
      await refresh(); navigate(boardPath(r, b)); toast(pair ? 'Rules and free runs queued' : profile_ids.length > 1 ? `Runs queued under ${profile_ids.length} profiles` : 'Independent jobs queued');
    } });
}

/* ---------- research handoff ---------- */
export function handoff(researchId: string) {
  const data = getData(); const { r, p } = getCurrent(); const research = data.research.find((x) => x.id === researchId); if (!research) return;
  const findings = findingsForHandoff(research); const boards = data.board.filter((b) => b.project_id === p.id); const key = uuid();
  const refIds = (data.job.find((j) => j.id === research.job_id)?.references || []).map((x: any) => x.id);
  openDialog({ title: 'Turn research into screens', submit: 'Continue', wide: true,
    body: <>
      <Note>{findings.length} findings will be copied into the board and supplied to every generation and revision. Source and verification labels are preserved.</Note>
      <details className="mb-3"><summary className="cursor-pointer text-sm">Included findings</summary>{findings.map((f: any) => <p key={f.id} className="my-1 text-sm">{f.title}</p>)}</details>
      <div className="mb-1 text-xs font-medium">Destination</div>
      <label className={checkRow}><input type="radio" name="dest" value="new" defaultChecked className="size-4" /> New board, and generate now</label>
      {boards.length > 0 && <><label className={checkRow}><input type="radio" name="dest" value="existing" className="size-4" /> Attach to an existing board (replaces its pinned findings; generate again to use them)</label><Field label="Existing board" htmlFor="h-board"><select id="h-board" name="board" className={nativeSelect}>{boards.map((b) => <option key={b.id} value={b.id}>{b.title}</option>)}</select></Field></>}
      <div className="mb-1 mt-3 text-xs font-medium">Reference images (optional)</div><RefPicker selected={refIds} projectId={p.id} />
      <Field label="New board title" htmlFor="h-title"><Input id="h-title" name="title" defaultValue="Research-led journey" /></Field>
      <TargetField id="h-target" /><Field label="Design brief" htmlFor="h-brief"><Textarea id="h-brief" name="brief" rows={3} defaultValue={handoffBrief(research.brief)} /></Field>
      <Field label={`Screens · one per line, 2–${MAX_SCREENS} screens`} htmlFor="h-screens"><Textarea id="h-screens" name="screens" rows={3} defaultValue={'Eligibility\nYour details\nReview'} /></Field>
      <div className="mb-1 text-xs font-medium">Compare agents · choose at least two configurations</div><RunnerChecklist /><div className="mt-3"><EstimateBox board={null} /></div>
    </>,
    onSubmit: async (f) => {
      if (f.get('dest') === 'existing') { const b = await api('board-research', { board_id: f.get('board'), research_id: research.id, finding_ids: findings.map((x: any) => x.id) }); await refresh(); navigate(boardPath(r, b)); toast('Findings attached. Generate variants to use them.'); return; }
      const screens = parseLines(String(f.get('screens'))); if (screens.length < 2 || screens.length > MAX_SCREENS) throw Error(`Choose 2–${MAX_SCREENS} screens`); if (f.getAll('runners').length < 2) throw Error('Select at least two runner configurations');
      const result = await api('research-board', { project_id: p.id, target: f.get('target'), research_id: research.id, finding_ids: findings.map((x: any) => x.id), title: f.get('title'), brief: f.get('brief'), screens, runner_ids: f.getAll('runners'), reference_ids: f.getAll('references'), idempotency_key: key });
      await refresh(); navigate(boardPath(r, result.board)); toast('Research carried forward. Screen generation started.');
    } });
}

/* ---------- approve, pins, rules ---------- */
export function approveModal() {
  const { v, b, r } = getCurrent(); if (!v || !b) return;
  const checks = checksOf(v); const failed = checks.filter((c: any) => c.outcome === 'fail'); const open = unresolvedReviews(v);
  openDialog({ title: 'Approve & build prototype', submit: 'Approve & build', body: <>
    <p>Approve <strong>{v.runner_name} v{v.version}</strong> of “{b.title}”.</p>
    <ul className="my-2 list-disc pl-5 text-xs text-muted-foreground"><li>Approval pins this exact version. It stays immutable; later changes create new versions.</li><li>A static click-through bundle is built from it and opens in the player.</li>{v.review_state === 'pending' && <li>This revision will be accepted.</li>}{b.blind && !b.revealed && <li><strong>Approving counts as your blind choice and reveals runner identities.</strong></li>}</ul>
    {failed.length > 0 && <Note kind="warn"><strong>{failed.length} deterministic check{failed.length === 1 ? '' : 's'} failed:</strong> {failed.map((c: any) => c.check).join('; ')}.</Note>}
    {open.length > 0 && <Note kind="warn">{open.length} item{open.length === 1 ? '' : 's'} still need designer review.</Note>}
    <Field label="Why this one? (optional, kept in the decision log)" htmlFor="ap-note"><Textarea id="ap-note" name="note" rows={2} placeholder="e.g. Clearest first step, calmest tone" /></Field></>,
  onSubmit: async (f) => { const res = await api('approve', { id: v.id, note: f.get('note') }); await refresh(); navigate(nav(r, 'prototypes') + '/' + res.prototype.id); toast('Approved and locked. Prototype built.'); } });
}
export async function pinModal(x: number, y: number, view: 'd' | 'm' = 'd') {
  const { v, b } = getCurrent(); if (!v || !b) return; const screen = ui.get().screen; const fr = frameOf(b, view); const el = await elementAt(v, screen, x, y, fr);
  openDialog({ title: 'Add screen feedback', submit: 'Add comment', body: <>
    <p className="mb-2 text-xs text-muted-foreground">{b.screens[Number(screen)]} · <span id="pin-anchor">{el ? `anchored to element “${el}”` : 'no stable element here; using coordinates'}</span></p>
    {askRunner(v) && <div className="mb-3 flex flex-wrap gap-x-5 gap-y-1" id="pin-mode"><label className={checkRow}><input type="radio" name="mode" value="change" defaultChecked className="size-4" /> Ask for a change</label><label className={checkRow}><input type="radio" name="mode" value="ask" className="size-4" /> Ask the agent a question (nothing is changed)</label></div>}
    <Field label="What should change? (or your question)" htmlFor="pin-comment"><Textarea id="pin-comment" name="comment" rows={4} required autoFocus placeholder="Move the explanatory text below the heading." /></Field>
    <div className="grid grid-cols-2 gap-3"><Field label="Horizontal position %" htmlFor="pin-x"><Input id="pin-x" name="x" type="number" min={0} max={100} defaultValue={Math.round(x * 100)} /></Field><Field label="Vertical position %" htmlFor="pin-y"><Input id="pin-y" name="y" type="number" min={0} max={100} defaultValue={Math.round(y * 100)} /></Field></div></>,
  onSubmit: async (f) => {
    if (f.get('mode') === 'ask') { await api('ask-pin', { variant_id: v.id, screen, element_id: el || '', question: f.get('comment'), runner_id: askRunner(v).id }); ui.set({ inspTab: 'comments' }); toast('Question sent. The answer appears under Comments.'); return; }
    const nx = Number(f.get('x')) / 100; const ny = Number(f.get('y')) / 100; const moved = Math.abs(nx - x) > 0.006 || Math.abs(ny - y) > 0.006;
    const created = await api('annotation', { variant_id: v.id, screen, view, x: nx, y: ny, comment: f.get('comment'), element_id: moved ? await elementAt(v, screen, nx, ny, fr) : el });
    ui.set({ activePin: created.id, inspTab: 'comments' });
  } });
}
export function pinEdit(id: string) {
  const pin = getData().annotation.find((x) => x.id === id); if (!pin) return;
  openDialog({ title: 'Edit feedback', submit: 'Save', body: <Field label="Comment" htmlFor="pe-c"><Textarea id="pe-c" name="comment" rows={4} required defaultValue={pin.comment} /></Field>, onSubmit: (f) => api('annotation-update', { id: pin.id, comment: f.get('comment') }) });
}
export const pinDelete = (id: string) => confirmDialog('Delete this pin?', <p>The feedback pin will be removed. Pins already used in a revision cannot be deleted.</p>, 'Delete pin', () => api('annotation-delete', { id }));

export function ruleModal(index: number | null = null) {
  const draft = ui.get().draft; if (!draft) return; const editing = index !== null;
  const rule = editing ? draft.rules[index as number] : { scope: 'project', severity: 'warning', verification: 'human_review', parameters: { max: 1 } } as any;
  const sel = (name: string, id: string, vals: [string, string][], cur: string) => <select id={id} name={name} defaultValue={cur} className={nativeSelect}>{vals.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select>;
  openDialog({ title: editing ? 'Edit rule ' + rule.id : 'Add a design rule', submit: 'Save rule', body: <>
    <Field label="Stable rule ID" htmlFor="r-id"><Input id="r-id" name="id" required pattern="[A-Za-z0-9_\-]+" defaultValue={rule.id || ''} readOnly={editing} placeholder="COPY-002" /></Field>
    <Field label="Description" htmlFor="r-desc"><Input id="r-desc" name="description" required defaultValue={rule.description || ''} /></Field>
    <div className="grid grid-cols-2 gap-3"><Field label="Scope" htmlFor="r-scope">{sel('scope', 'r-scope', [['workspace', 'workspace'], ['project', 'project'], ['job', 'job']], rule.scope)}</Field><Field label="Severity" htmlFor="r-sev">{sel('severity', 'r-sev', [['error', 'error'], ['warning', 'warning'], ['info', 'info']], rule.severity)}</Field></div>
    <Field label="Verification" htmlFor="r-ver">{sel('verification', 'r-ver', [['human_review', 'Designer review'], ['deterministic', 'Deterministic · primary action count'], ['advisory_model', 'Advisory model opinion (never shown as verified)']], rule.verification)}</Field>
    <Field label="Maximum primary actions (deterministic only)" htmlFor="r-max"><Input id="r-max" name="max" type="number" min={0} defaultValue={rule.parameters?.max ?? 1} /></Field>
    <Field label="Justification when overriding a broader rule (optional)" htmlFor="r-just"><Input id="r-just" name="justification" defaultValue={rule.justification || ''} /></Field></>,
  onSubmit: (f) => {
    const d = ui.get().draft as any; const id = String(f.get('id')).trim(); const dup = d.rules.some((x: any, i: number) => x.id === id && x.scope === f.get('scope') && i !== index);
    if (!/^[A-Za-z0-9_-]+$/.test(id)) throw Error('Rule IDs may only contain letters, numbers, - and _'); if (dup) throw Error('A rule with this ID already exists in this scope');
    const nr: any = { ...rule, id, description: String(f.get('description')).trim(), scope: f.get('scope'), severity: f.get('severity'), verification: f.get('verification'), enabled: rule.enabled !== false };
    if (nr.verification === 'deterministic') { nr.check = 'primary_action_count'; nr.parameters = { max: Number(f.get('max')) }; } else { delete nr.check; delete nr.parameters; }
    if (String(f.get('justification')).trim()) nr.justification = String(f.get('justification')).trim(); else delete nr.justification;
    const rules = [...d.rules]; if (editing) rules[index as number] = nr; else rules.push(nr); ui.set({ draft: { ...d, rules } });
  } });
}

/* ---------- mix, share, blind, lightbox, live preview ---------- */
export function mixModal() {
  const { b, vs, r } = getCurrent(); if (!b) return; const usable = vs.filter((x) => x.review_state !== 'reverted'); if (usable.length < 2) return toast('Generate at least two versions to mix');
  openDialog({ title: 'Mix screens from different versions', submit: 'Create mixed version', wide: true, body: <>
    <p className="mb-3 text-muted-foreground">Pick the source of each screen. The result is a new version with its own checks; the originals are untouched.</p>
    <div className="mixgrid grid items-center gap-2" style={{ gridTemplateColumns: `110px repeat(${usable.length},1fr)` }}><span />{usable.map((x) => <strong key={x.id} className="mixhead text-xs">{x.runner_name} v{x.version}</strong>)}
      {b.screens.map((t: string, i: number) => [<span key={'r' + i} className="mixrow text-xs">{t}</span>, ...usable.map((x, k) => <label key={x.id + i} className="mixcell relative block cursor-pointer rounded-md border p-1 has-[:checked]:ring-2 has-[:checked]:ring-foreground"><input type="radio" name={`pick-${i}`} value={x.id} defaultChecked={k === i % usable.length} aria-label={`${t} from ${x.runner_name} v${x.version}`} className="absolute left-2 top-2 z-10 size-4" /><img src={img(x, String(i))} alt="" loading="lazy" className="w-full rounded" /></label>)])}
    </div></>,
  onSubmit: async (f) => { const picks: Record<string, any> = {}; b.screens.forEach((_: any, i: number) => { picks[String(i)] = f.get('pick-' + i); }); const m = await api('mix', { board_id: b.id, picks }); await refresh(); ui.set({ selectedVariant: m.id }); navigate(boardPath(r, b)); toast('Mixed version created'); } });
}
export function shareModal() {
  const data = getData(); const { r } = getCurrent(); const cfg = dataStore.get().config; const proto = data.prototype.find((x) => x.id === r.prototypeId); if (!proto) return;
  const base = `${location.protocol}//${location.hostname}:${cfg.share_port}`; const links = (proto.shares || []).filter((x: any) => !x.revoked);
  const stamp = (x: any) => (x.expires_at ? (x.expires_at * 1000 < Date.now() ? 'expired' : 'expires ' + new Date(x.expires_at * 1000).toLocaleString()) : 'no expiry');
  openDialog({ title: 'Share this prototype', submit: 'Create link', stay: true, body: <>
    {!cfg.share_port && <Note kind="warn">Sharing is off. Restart the studio with <code>STUDIO_SHARE_PORT=5180</code> to serve links. Only prototype bundles are exposed on that port; the studio itself stays local.</Note>}
    <p className="mb-3 text-muted-foreground">A link opens a read-only player for this exact approved build (v{proto.version}). Anyone with the link can view it until it expires or you revoke it. There is no other access control, so share it only with people you trust.</p>
    {links.length > 0 && <><h3 className="mb-1.5 mt-4 text-xs font-semibold">Active links</h3>{links.map((x: any) => { const url = `${base}/s/${x.token}/`; return (
      <div key={x.token} className="sharerow mb-2 flex flex-wrap items-center gap-2"><Input readOnly aria-label="Share link" value={url} data-share-input className="min-w-0 flex-1" /><span className="text-xs text-muted-foreground">{stamp(x)}</span>
        <button type="button" className="rounded-md border px-2 py-1 text-xs" data-share-copy={url} onClick={async () => { try { await navigator.clipboard.writeText(url); toast('Link copied'); } catch { (document.querySelector('[data-share-input]') as HTMLInputElement)?.select(); toast('Press Ctrl+C to copy the selected link'); } }}>Copy</button>
        <button type="button" className="rounded-md border px-2 py-1 text-xs" data-share-revoke={x.token} onClick={async () => { await api('share-revoke', { prototype_id: proto.id, token: x.token }); await refresh(); toast('Link revoked'); shareModal(); }}>Revoke</button></div>); })}
      {(location.hostname === 'localhost' || location.hostname === '127.0.0.1') && <p className="text-xs text-muted-foreground">To open a link on another device, replace “localhost” with this computer’s address.</p>}</>}
    <Field label="New link expires after" htmlFor="share-exp"><select id="share-exp" name="hours" defaultValue="24" className={nativeSelect}><option value="1">1 hour</option><option value="24">24 hours</option><option value="168">7 days</option><option value="720">30 days</option><option value="">Never</option></select></Field></>,
  onSubmit: async (f) => { if (!cfg.share_port) throw Error('Start the studio with STUDIO_SHARE_PORT set to enable sharing'); const h = f.get('hours'); await api('share-create', { prototype_id: proto.id, hours: h === '' ? null : Number(h) }); await refresh(); shareModal(); } });
}
export function blindPick(id: string) {
  const { b } = getCurrent(); const pv = getData().variant.find((x) => x.id === id); if (!pv || !b) return;
  openDialog({ title: 'Choose this option', submit: 'Choose and reveal', body: <><p>You are choosing <strong>{pv.runner_name} v{pv.version}</strong>. Runner identities will be revealed afterwards and your choice is recorded.</p><Field label="Why? (optional)" htmlFor="bp-r"><Textarea id="bp-r" name="reason" rows={3} placeholder="e.g. clearer explanation of why we ask for income" /></Field></>,
    onSubmit: async (f) => { const board = await api('blind-choice', { board_id: b.id, variant_id: id, reason: f.get('reason') }); toast(`Revealed: ${board.blind_choice.label ? 'Option ' + board.blind_choice.label + ' was ' : ''}${board.blind_choice.runner_name}`); } });
}
export function blindReveal() {
  const { b } = getCurrent(); if (!b) return;
  confirmDialog('Reveal runner identities?', <p>Without choosing, the comparison ends and you will see which runner made each option. You cannot re-enable blind mode for this board afterwards.</p>, 'Reveal', async () => { await api('blind-choice', { board_id: b.id }); toast('Identities revealed'); });
}
export function revertRevision(id: string) {
  const rv = getData().variant.find((x) => x.id === id); if (!rv) return;
  confirmDialog('Revert this revision?', <p>v{rv.version} stays in history (hidden by default) and the parent version becomes the working version again. Nothing is deleted.</p>, 'Revert revision', async () => { await api('revert-revision', { id }); ui.set({ selectedVariant: rv.parent_id }); toast('Reverted to the parent version'); });
}
export async function acceptRevision(id: string) { await api('accept-revision', { id }); toast('Revision accepted'); await refresh(); }
export const deleteRef = (id: string) => confirmDialog('Delete this reference image?', <p>It is removed from the library. Jobs that already used it keep their own copy for history and retries.</p>, 'Delete image', () => api('reference-delete', { id }));
export const deleteRunner = (id: string) => confirmDialog('Delete runner configuration?', <p>{runnerOf(id)?.name} will be removed. Past jobs and variations keep their history.</p>, 'Delete', () => api('delete-runner', { id }));
export function openRef(value: string) {
  const [src, file, ...n] = value.split(':'); const name = n.join(':'); const { p } = getCurrent();
  const url = src === 'project' ? `/assets/projects/${p.id}/references/${file}` : `/assets/jobs/${src}/references/${file}`;
  openDialog({ title: name, plain: true, wide: true, body: <img className="lightbox mx-auto max-h-[70vh] max-w-full rounded-md" src={url} alt={name} /> });
}
export function openLive(v: any, sid: string) {
  openDialog({ title: `Live preview · ${v.runner_name} v${v.version}`, plain: true, wide: true, className: 'live max-sm:h-dvh', body: <LivePreview v={v} sid={sid} /> });
}

/* ---------- job actions ---------- */
export const jobAction = async (kind: 'cancel' | 'dismiss' | 'retry', id: string) => {
  await api(kind + '-job', { id }); toast(kind === 'cancel' ? 'Cancelling…' : kind === 'dismiss' ? 'Dismissed; it stays in Job history' : 'Retry queued with the same inputs'); await refresh();
};

/* ---------- context drafts ---------- */
export async function saveDraft() {
  const { p } = getCurrent(); const d = ui.get().draft; if (!d) throw Error('Nothing to save'); let tokens: any;
  try { tokens = JSON.parse(d.tokens); } catch { throw Error('Tokens must be valid JSON'); }
  const c = await api('context', { project_id: p.id, profile_id: getCurrent().ctx?.profile_id || 'main', markdown: d.markdown, tokens, rules: d.rules.map(({ version, ...x }: any) => x) });
  ui.set({ draftFor: '' }); await refresh(); return c;
}

/* ---------- named actions (the old data-action switch) ---------- */
export async function runAction(name: string) {
  const { p, b, v, ctx, vs, r } = getCurrent();
  try {
    switch (name) {
      case 'new-project': return newProject();
      case 'project-menu': return projectMenu();
      case 'new-board': return newBoard();
      case 'generate': if (!b) return toast('Create a board first'); if (r.view === 'context' && isDirty(ctx)) { await saveDraft(); toast('Saved your guideline edits as a new version'); } return generateModal();
      case 'mix': return mixModal();
      case 'approve': if (!v) return toast('Generate a variation first'); return approveModal();
      case 'preview': { const proto = prototypeOf(vs.find((x) => x.approved)); if (!proto) return toast('Approve a board variation before previewing'); return navigate(nav(r, 'prototypes') + '/' + proto.id); }
      case 'review': ui.set({ tool: 'comment' }); if (v) navigate(boardPath(r, b, 'review', v.id)); return;
      case 'revise': {
        const ids = getData().annotation.filter((a) => a.variant_id === v.id && a.status !== 'applied' && a.selected !== false).map((a) => a.id); if (!ids.length) return toast('Select at least one open pin');
        const send = async (runner_ids?: string[]) => { await api('revise', { project_id: p.id, board_id: b.id, parent_id: v.id, brief: b.brief, runner_ids, annotation_ids: ids, scope_mode: ui.get().regionOnly ? 'region' : 'screen', idempotency_key: uuid() }); toast('Revision queued; the parent version is preserved'); await refresh(); navigate(boardPath(r, b)); };
        if (v.kind === 'mix') return openDialog({ title: 'Choose a runner for this revision', submit: 'Revise', body: <><p className="mb-2 text-muted-foreground">A mixed version has no single author, so pick which runner should apply your feedback.</p>{enabledRunners().map((x, i) => <label key={x.id} className={checkRow}><input type="radio" name="runner" value={x.id} defaultChecked={i === 0} className="size-4" /> {x.name}</label>)}</>, onSubmit: (f) => send([String(f.get('runner'))]) });
        return send(v.runner_id ? [v.runner_id] : undefined);
      }
      case 'scan-agents': await rescanAgents(); return toast('Installed agents refreshed');
    }
  } catch (err: any) { toast(err.message); }
}
void fmtHash; void esc; void jobRefUrl; void protoLive; void referencesOf; void parseSources; void researchJobs; void ensureDraft; void parseRoute; void unresolvedReviews;
