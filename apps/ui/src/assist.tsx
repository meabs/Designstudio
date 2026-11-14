// Merge a part of another design, draft guidelines from a brief, ask a question about a pin, starter-guidelines warning.
import { useState } from 'react';
import { api, refresh, getData, ui, enabledRunners, ensureDraft, useData, variantsOf } from '@/lib/store';
import { getCurrent, nav, navigate, useCurrent } from '@/lib/router';
import { uuid } from '@/lib/format';
import { openDialog, toast, Tag, Note, Field, Panel } from '@/components/app/feedback';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { Ic } from '@/components/app/icons';
const nativeSelect = 'h-9 w-full rounded-lg border border-input bg-background px-3 text-sm shadow-xs/5 outline-none focus-visible:border-ring focus-visible:ring-[3px] focus-visible:ring-ring/24';

const agents = () => enabledRunners().filter((r: any) => r.type === 'cli');
export const STARTER = '# Design guidelines\n\nUse a neutral financial-services style.';
export const isStarter = (ctx: any) => !!ctx && String(ctx.markdown || '').startsWith(STARTER);

/* ---------- 1. starter-guidelines warning ---------- */
export function StarterBanner() {
  const { ctx } = useCurrent();
  if (!isStarter(ctx)) return null;
  return <Note kind="warn"><span id="starter-warning"><strong>These are still the starter guidelines.</strong> Every agent is told to be “neutral financial-services” in grey-green, so designs converge. Replace them with your own, or draft them from a short description below.</span></Note>;
}

/* ---------- 2. bring a part from another design ---------- */
export function mergeModal(v: any) {
  const { p, b, r } = getCurrent(); if (!b) return;
  const donors = variantsOf(b).filter((x: any) => x.id !== v.id && x.manifest && x.review_state !== 'reverted');
  if (!donors.length) return toast('Generate another design on this board first');
  const runners = agents(); const mine = runners.find((x: any) => x.id === v.runner_id) || runners[0];
  const Body = () => {
    const [d, setD] = useState(donors[0].id); const donor = donors.find((x: any) => x.id === d) || donors[0];
    return <>
      <p className="mb-3 text-xs text-muted-foreground">The agent rebuilds the part you describe inside <strong>{v.runner_name} v{v.version}</strong>, in this design’s own styling. It becomes a new revision; nothing is overwritten.</p>
      <Field label="Take it from" htmlFor="mg-donor"><select id="mg-donor" name="donor" className={nativeSelect} value={d} onChange={(e) => setD(e.target.value)}>{donors.map((x: any) => <option key={x.id} value={x.id}>{x.runner_name} v{x.version}{x.profile_name && x.profile_name !== 'Main' ? ` · ${x.profile_name}` : ''}</option>)}</select></Field>
      <div className="grid grid-cols-2 gap-3">
        <Field label="Screen to take it from" htmlFor="mg-ds"><select id="mg-ds" name="donor_screen" className={nativeSelect}>{donor.manifest.screens.map((s: any) => <option key={s.id} value={s.id}>{s.title}</option>)}</select></Field>
        <Field label="Put it on screen" htmlFor="mg-s"><select id="mg-s" name="screen" className={nativeSelect}>{v.manifest.screens.map((s: any) => <option key={s.id} value={s.id}>{s.title}</option>)}</select></Field>
      </div>
      <Field label="Which part?" htmlFor="mg-part"><Input id="mg-part" name="part" required maxLength={300} placeholder="e.g. the hero, the pricing table, the audit log" /></Field>
    </>;
  };
  openDialog({ title: 'Bring a part from another design', submit: 'Queue merge', body: <Body />, onSubmit: async (f) => {
    if (!mine) throw Error('Add a coding agent (Claude Code or Codex) in Settings → Agents first');
    await api('revise', { project_id: p.id, board_id: b.id, parent_id: v.id, brief: b.brief, runner_ids: [mine.id], merge: { donor_id: f.get('donor'), donor_screen: f.get('donor_screen'), screen: f.get('screen'), part: f.get('part') }, idempotency_key: uuid() });
    toast('Merge queued as a new revision'); await refresh(); navigate(nav(r, 'boards') + '/' + b.id);
  } });
}

/* ---------- 3. cut-off marker ---------- */
export function CutOff({ v, full }: { v: any; full?: boolean }) {
  if (!v?.cut_off) return null;
  return full
    ? <Note kind="warn"><span data-cut-off="1"><strong>Cut off at the time limit.</strong> The agent had written every screen but was still working when time ran out, so the last polish may be missing. Review it, then use Revise to finish anything that looks unfinished.</span></Note>
    : <Tag kind="warn" data-cut-off="1" title="The agent hit its time limit after writing every screen">Cut off</Tag>;
}

/* ---------- 4. draft guidelines from a company brief ---------- */
export function DraftPanel() {
  const { p, ctx } = useCurrent(); const data = useData(); const runners = agents(); const [brief, setBrief] = useState(''); const [rid, setRid] = useState(''); const [busy, setBusy] = useState(false); const [gone, setGone] = useState<string[]>([]);
  const jobs = data.job.filter((j: any) => j.type === 'guidelines_draft' && j.project_id === p.id && !gone.includes(j.id)).sort((a: any, b: any) => b.created_at - a.created_at);
  const job = jobs[0]; const active = job && ['queued', 'running'].includes(job.status); const failed = job && ['failed', 'timed_out', 'cancelled'].includes(job.status); const draft = job?.status === 'succeeded' ? job.draft : null;
  const go = async () => { setBusy(true); try { await api('draft-guidelines', { project_id: p.id, runner_id: rid || runners[0]?.id, brief }); await refresh(); toast('Agent is drafting your guidelines'); } catch (e: any) { toast(e.message); } finally { setBusy(false); } };
  const load = () => {
    ensureDraft(ctx); const dd = ui.get().draft as any;
    ui.set({ draft: { ...dd, markdown: draft.markdown, tokens: JSON.stringify({ ...JSON.parse(dd.tokens || '{}'), ...draft.tokens }, null, 2), rules: draft.rules.map((r: any) => ({ id: r.id, description: r.description, scope: 'project', severity: r.severity, verification: 'advisory', enabled: true })) } });
    setGone([...gone, job.id]); toast('Loaded into your draft. Review it, then press Save new version.');
  };
  return (
    <Panel id="draft-panel" title="Draft guidelines with an agent">
      <p className="mb-3 text-xs text-muted-foreground">Describe the company, audience and feel in a few sentences. An agent writes a first DESIGN.md, tokens and rules for you to edit. It is a draft: nothing is saved until you review it and press Save new version.</p>
      {!runners.length ? <p className="text-xs text-muted-foreground">Add Claude Code or Codex in Settings → Agents to use this.</p> : <>
        <Textarea id="draft-brief" rows={4} value={brief} onChange={(e) => setBrief(e.target.value)} placeholder="e.g. Relay Ops sells AI agents that run IT operations to IT directors at 500–5,000 person companies. They distrust AI hype; we want a precise, technical, dark interface with proof over adjectives." />
        <div className="mt-2 flex flex-wrap items-center gap-2"><select aria-label="Agent" className={nativeSelect + ' !w-auto'} value={rid || runners[0].id} onChange={(e) => setRid(e.target.value)}>{runners.map((r: any) => <option key={r.id} value={r.id}>{r.name}</option>)}</select>
          <Button className="primary" data-action="draft-guidelines" disabled={busy || !!active || brief.trim().length < 20} onClick={go}><Ic name="spark" size={13} /> {active ? 'Drafting…' : 'Draft guidelines'}</Button></div></>}
      {failed && <p className="mt-3 text-xs text-destructive-foreground">The last draft did not finish: {job.events.at(-1)?.message}</p>}
      {draft && <div className="mt-4" id="draft-result">
        <p className="mb-2 text-xs text-muted-foreground">{draft.note}</p>
        <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Tokens</h3>
        <div className="mb-3 flex flex-wrap gap-1.5">{Object.entries(draft.tokens).map(([k, v]: any) => <span key={k} className="inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-xs">{/^#[0-9a-f]{3,8}$/i.test(v) && <span className="size-3 rounded-sm border" style={{ background: v }} />}<span className="font-mono">{k}</span> {v}</span>)}</div>
        <h3 className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Rules ({draft.rules.length})</h3>
        <ul className="mb-3 list-disc pl-5 text-[13px]">{draft.rules.map((r: any) => <li key={r.id}><span className="font-mono text-xs">{r.id}</span> · {r.description}</li>)}</ul>
        <details className="mb-3"><summary className="cursor-pointer text-xs font-medium">Guidelines text</summary><pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap rounded border p-2 text-xs">{draft.markdown}</pre></details>
        {draft.notes.length > 0 && <><h3 className="mb-1 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Check these assumptions</h3><ul className="mb-3 list-disc pl-5 text-[13px]">{draft.notes.map((n: string, i: number) => <li key={i}>{n}</li>)}</ul></>}
        <div className="flex gap-2"><Button className="primary" data-action="load-draft" onClick={load}><Ic name="download" size={13} /> Replace my draft with this</Button><Button variant="outline" onClick={() => setGone([...gone, job.id])}>Discard</Button></div></div>}
    </Panel>
  );
}

/* ---------- 5. ask a question about a pinned spot ---------- */
export const askRunner = (v: any) => { const r = agents(); return r.find((x: any) => x.id === v.runner_id) || r[0]; };
export function AskList({ v }: { v: any }) {
  const data = useData(); const jobs = data.job.filter((j: any) => j.type === 'pin_ask' && j.target_variant_id === v.id).sort((a: any, b: any) => b.created_at - a.created_at);
  if (!jobs.length) return null;
  return <div className="mt-4" id="ask-list"><h3 className="mb-2 text-[11px] font-semibold uppercase tracking-wide text-muted-foreground">Questions</h3>
    {jobs.map((j: any) => <div key={j.id} className="ask mb-2 rounded-lg border p-2 text-[13px]" data-ask={j.status}>
      <p className="font-medium">{j.question}</p><p className="text-[11px] text-muted-foreground">{getData().board.find((x) => x.id === j.board_id)?.screens[Number(j.screen)]}{j.element_id ? ` · ${j.element_id}` : ''}</p>
      {['queued', 'running'].includes(j.status) && <p className="mt-1 text-xs text-muted-foreground">The agent is reading the screen…</p>}
      {['failed', 'timed_out', 'cancelled'].includes(j.status) && <p className="mt-1 text-xs text-destructive-foreground">Could not answer: {j.events.at(-1)?.message}</p>}
      {j.answer && <><p className="mt-1.5">{j.answer.answer}</p>{j.answer.suggested_change && <p className="mt-1 text-xs"><strong>Suggestion:</strong> {j.answer.suggested_change}</p>}<p className="mt-1 text-[11px] text-muted-foreground">Agent opinion, unverified · confidence {j.answer.confidence}</p></>}
    </div>)}</div>;
}
