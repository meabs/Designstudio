import { useMemo, useState } from 'react';
import { Link, useCurrent, nav, boardPath } from '@/lib/router';
import { profilesOf, useData, useUi, ui, useConfig, useAgents, variantsOf, runnerOf, prototypeOf, referencesOf, activeJob, variantStatus, ctxVersion, rescanAgents, api, refresh, dataStore, jobRefUrl, refUrl } from '@/lib/store';
import { ago, fmtTime, fmtDuration, fmtHash, fmtBytes } from '@/lib/format';
import { boardResearch } from '@/lib/research';
import { Heading } from '@/components/app/chrome';
import { Tag, Panel, Content, Empty, Note, toast } from '@/components/app/feedback';
import { Ic } from '@/components/app/icons';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { uploadRefs } from '@/components/app/refs';
import { RefThumbs } from './board';
import { DecisionsPanel, ReviewDocsPanel } from '@/tools';
import { runAction, jobAction, deleteRef, deleteRunner, openRef, nativeSelect } from '@/actions';
import { cn } from '@/lib/utils';

/* ---------- projects home ---------- */
function projectStats(p: any, data: any) {
  const boards = data.board.filter((b: any) => b.project_id === p.id); const ids = new Set(boards.map((b: any) => b.id)); const vars = data.variant.filter((v: any) => ids.has(v.board_id)); const jobs = data.job.filter((j: any) => j.project_id === p.id);
  const last = Math.max(p.created_at || 0, ...jobs.map((j: any) => j.events.at(-1)?.time || j.created_at || 0), ...vars.map((v: any) => v.created_at || 0), ...boards.map((b: any) => b.created_at || 0));
  return { boards, vars, last, running: jobs.filter(activeJob).length, attention: jobs.filter((j: any) => ['failed', 'timed_out'].includes(j.status) && !j.retried_by && !j.dismissed).length, approved: vars.filter((v: any) => v.approved).length };
}
export function ProjectsView() {
  const data = useData(); const [q, setQ] = useState('');
  const live = data.project.filter((p) => !p.archived).map((p) => ({ p, st: projectStats(p, data) })).sort((a, b) => b.st.last - a.st.last); const archived = data.project.filter((p) => p.archived);
  const plural = (n: number, w: string) => `${n} ${w}${n === 1 ? '' : 's'}`;
  return (
    <>
      <Heading title="Projects" sub="A home for your design decisions, from the first rule to the final prototype." />
      <Content>
        <div className="mb-5 flex items-center justify-between gap-3.5"><span className="flex items-center gap-3.5"><span className="text-muted-foreground">{plural(live.length, 'project')}</span>{live.length > 5 && <Input type="search" data-project-filter placeholder="Filter projects" aria-label="Filter projects" className="w-60" value={q} onChange={(e) => setQ(e.target.value)} />}</span><Button className="primary" data-action="new-project" onClick={() => runAction('new-project')}><Ic name="plus" /> New project</Button></div>
        <div className="projects-grid grid grid-cols-[repeat(auto-fill,minmax(270px,1fr))] gap-4" id="project-grid">
          {live.filter(({ p }) => !q.trim() || (p.name + ' ' + p.description).toLowerCase().includes(q.trim().toLowerCase())).map(({ p, st }) => (
            <Link key={p.id} href={`/projects/${p.id}/boards`} data-project-card className="project-card card flex flex-col gap-2.5 rounded-xl border bg-card p-5 shadow-xs/5 transition-colors hover:border-foreground/25">
              <div className="flex items-center justify-between"><span className="agent-avatar grid size-8 place-items-center rounded-lg bg-muted"><Ic name="boards" /></span><span className="text-xs text-muted-foreground">Updated {ago(st.last)}</span></div>
              <h2 className="mt-1 text-base font-semibold">{p.name}</h2><p className="text-[13px] text-muted-foreground">{p.description}</p>
              <div className="flex flex-wrap gap-1.5"><Tag>{plural(st.boards.length, 'board')}</Tag>{st.vars.length > 0 && <Tag>{plural(st.vars.length, 'variant')}</Tag>}{st.approved > 0 && <Tag kind="success">{st.approved} approved</Tag>}{st.running > 0 && <Tag kind="warn">{st.running} running</Tag>}{st.attention > 0 && <Tag kind="fail">{st.attention} need attention</Tag>}</div>
            </Link>
          ))}
        </div>
        {archived.length > 0 && <details className="mt-7"><summary className="cursor-pointer text-muted-foreground">Archived ({archived.length})</summary><div className="projects-grid mt-3.5 grid grid-cols-[repeat(auto-fill,minmax(270px,1fr))] gap-4">{archived.map((p) => <div key={p.id} className="project-card card rounded-xl border bg-card p-5"><h2 className="font-semibold">{p.name}</h2><Button variant="outline" size="sm" className="mt-3" data-restore-project={p.id} onClick={async () => { await api('update-project', { id: p.id, archived: false }); await refresh(); }}>Restore</Button></div>)}</div></details>}
      </Content>
    </>
  );
}

/* ---------- boards list ---------- */
export function BoardsList() {
  const { r, boards } = useCurrent(); const data = useData();
  return (
    <>
      <Heading title="Boards" sub="Each board is one journey: a brief, 2–12 screens for a website, a mobile app or both, and the independent variations generated for it." right={<Button className="primary" data-action="new-board" onClick={() => runAction('new-board')}><Ic name="plus" /> New board</Button>} />
      <Content>
        {boards.length ? <div className="projects-grid grid grid-cols-[repeat(auto-fill,minmax(270px,1fr))] gap-4">{boards.map((b) => {
          const vs = variantsOf(b); const ap = vs.find((v) => v.approved); const jobs = data.job.filter((j) => j.board_id === b.id && activeJob(j)).length;
          return <Link key={b.id} href={boardPath(r, b)} className="project-card card flex flex-col gap-2.5 rounded-xl border bg-card p-5 shadow-xs/5 transition-colors hover:border-foreground/25"><span className="agent-avatar grid size-8 place-items-center rounded-lg bg-muted"><Ic name="boards" /></span><h2 className="text-base font-semibold">{b.title}</h2><p className="line-clamp-3 text-[13px] text-muted-foreground">{b.brief}</p><div className="flex flex-wrap gap-1.5"><Tag>{b.screens.length} screens</Tag><Tag>{vs.length} variations</Tag>{ap && <Tag kind="success">Approved v{ap.version}</Tag>}{jobs > 0 && <Tag kind="warn">{jobs} running</Tag>}{boardResearch(b).length > 0 && <Tag>{boardResearch(b).length} findings</Tag>}</div></Link>;
        })}</div> : <Empty title="No boards yet" text="Create a board to describe a journey and generate competing variations."><Button className="primary" data-action="new-board" onClick={() => runAction('new-board')}>Create a board</Button></Empty>}
      </Content>
    </>
  );
}

/* ---------- references ---------- */
export function ReferencesView() {
  const { p } = useCurrent(); const data = useData(); const refs = referencesOf(p.id); const [over, setOver] = useState(false);
  return (
    <>
      <Heading title="Reference images" sub="Visual context for agents: moodboards, competitor screens, sketches. Choose which ones to send when you run research or generate variations." right={<label className="button inline-flex h-8 cursor-pointer items-center gap-2 rounded-lg bg-primary px-3 text-sm font-medium text-primary-foreground"><Ic name="upload" size={13} /> Upload images<input type="file" accept="image/png,image/jpeg,image/webp,image/gif" multiple hidden data-ref-upload onChange={(e) => { const f = [...(e.target.files || [])]; e.target.value = ''; uploadRefs(f, p.id); }} /></label>} />
      <Content>
        <div data-dropzone tabIndex={0} className={cn('dropzone mb-5 grid place-items-center gap-1.5 rounded-xl border-[1.5px] border-dashed bg-background p-7 text-center', over && 'over border-foreground bg-muted')} onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)} onDrop={(e) => { e.preventDefault(); setOver(false); uploadRefs([...e.dataTransfer.files], p.id); }}
          ref={(el) => { if (!el) return; }}>
          <Ic name="image" size={22} /><strong>Drop images here, or paste from the clipboard</strong><span className="text-xs text-muted-foreground">PNG, JPEG, WebP or GIF · up to 5 MB each · stored locally in this project</span>
        </div>
        <PasteCatcher pid={p.id} />
        <div className="refpage grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-4">
          {refs.map((r) => (
            <div key={r.id} className="card refcard flex flex-col gap-2 rounded-xl border bg-card p-3">
              <button className="refbig overflow-hidden rounded-lg border p-0" data-ref-open={`project:${r.file}:${r.name}`} aria-label={`Enlarge ${r.name}`} onClick={() => openRef(`project:${r.file}:${r.name}`)}><img src={refUrl(r)} alt={r.name} loading="lazy" className="aspect-[4/3] w-full object-cover" /></button>
              <label className="sr-only" htmlFor={`rn-${r.id}`}>Name</label><Input id={`rn-${r.id}`} data-ref-name={r.id} defaultValue={r.name} onBlur={async (e) => { if (e.target.value !== r.name) { await api('reference-update', { id: r.id, name: e.target.value }); await refresh(); } }} />
              <label className="sr-only" htmlFor={`rt-${r.id}`}>Note for the agent</label><Textarea id={`rt-${r.id}`} rows={2} data-ref-note={r.id} defaultValue={r.note || ''} placeholder="Note for the agent, e.g. “use this card layout, not the colours”" onBlur={async (e) => { if (e.target.value !== (r.note || '')) { await api('reference-update', { id: r.id, note: e.target.value }); await refresh(); } }} />
              <div className="flex items-center justify-between"><span className="text-xs text-muted-foreground">{fmtBytes(r.size)} · {data.board.filter((b) => (b.reference_ids || []).includes(r.id)).length} boards</span><Button variant="ghost" size="icon-xs" data-ref-delete={r.id} aria-label={`Delete ${r.name}`} onClick={() => deleteRef(r.id)}><Ic name="trash" size={13} /></Button></div>
            </div>
          ))}
          {!refs.length && <Empty title="No references yet" text="Upload a few images to give agents visual direction." />}
        </div>
      </Content>
    </>
  );
}
import { useEffect } from 'react';
function PasteCatcher({ pid }: { pid: string }) {
  useEffect(() => {
    const paste = (e: ClipboardEvent) => { const files = [...(e.clipboardData?.files || [])].filter((f) => f.type.startsWith('image/')); if (files.length) { e.preventDefault(); uploadRefs(files, pid); } };
    document.addEventListener('paste', paste); return () => document.removeEventListener('paste', paste);
  }, [pid]); return null;
}

/* ---------- history ---------- */
const JOB_LABEL: Record<string, string> = { queued: 'Queued', running: 'Running', succeeded: 'Succeeded', failed: 'Failed', timed_out: 'Timed out', cancelled: 'Cancelled' };
const jobKind = (j: any) => (j.status === 'succeeded' ? 'success' : j.status === 'failed' ? 'fail' : ['timed_out', 'cancelled'].includes(j.status) ? 'warn' : '');
function Lineage({ v }: { v: any }) {
  const { r } = useCurrent(); const data = useData(); const [label, kind] = variantStatus(v);
  const kids = data.variant.filter((x) => x.parent_id === v.id).sort((a, b) => a.created_at - b.created_at); const pins = data.annotation.filter((a) => a.variant_id === v.id); const proto = prototypeOf(v); const c = data.context.find((x) => x.id === v.context_id); const board = data.board.find((b) => b.id === v.board_id);
  return <li><div className="lineage-node flex flex-wrap items-center gap-x-2 gap-y-1 py-1"><strong>{v.runner_name} v{v.version}</strong> <Tag kind={kind}>{label}</Tag> <span className="text-xs text-muted-foreground">job {v.job_id.slice(0, 6)} · context v{ctxVersion(c)} ({fmtHash(c?.hash)}) · {pins.length} pin{pins.length === 1 ? '' : 's'}{(v.changed_screens || []).length ? ` · changed ${v.changed_screens.length} screen(s)` : ''}</span> <Link className="text-xs underline" href={boardPath(r, board, 'review', v.id)}>Review</Link>{proto && <Link className="text-xs underline" href={`${nav(r, 'prototypes')}/${proto.id}`}>Prototype {proto.id.slice(0, 6)}</Link>}</div>{kids.length > 0 && <ul className="ml-5 border-l pl-3">{kids.map((k) => <Lineage key={k.id} v={k} />)}</ul>}</li>;
}
export function HistoryView() {
  const { r, p, boards } = useCurrent(); const data = useData(); const filter = useUi((s) => s.histFilter);
  const jobs = data.job.filter((x) => x.project_id === p.id).slice().reverse(); const shown = filter === 'all' ? jobs : jobs.filter((j) => (filter === 'attention' ? ['failed', 'timed_out', 'cancelled'].includes(j.status) : j.status === filter));
  const chips = [['all', 'All'], ['running', 'Running'], ['succeeded', 'Succeeded'], ['attention', 'Needs attention']];
  return (
    <>
      <Heading title="Job history & lineage" sub="Context snapshot → research → brief → generation → variant → feedback → revision → approval → prototype. Every decision has a trail." />
      <Content>
        <DecisionsPanel />
        <Panel title="Lineage">
          {boards.length ? boards.map((b) => { const roots = variantsOf(b).filter((v) => !v.parent_id); const ctxs = [...new Set(variantsOf(b).map((v) => v.context_id))];
            return <div key={b.id} className="lineage-board mb-5"><h3 className="font-semibold"><Link href={boardPath(r, b)} className="underline">{b.title}</Link></h3>
              <p className="my-1 text-xs text-muted-foreground">Brief: {b.brief}<br />{b.blind ? (b.revealed ? (b.blind_choice?.variant_id ? `Blind result: preferred Option ${b.blind_choice.label || '?'} (${b.blind_choice.runner_name})${b.blind_choice.reason && b.blind_choice.reason !== 'Approved' ? ' · “' + b.blind_choice.reason + '”' : ''}` : 'Blind comparison revealed without a choice') : 'Blind comparison in progress: identities hidden') : null}{b.blind ? <br /> : null}{b.research_id ? `Research: “${b.research_brief}” · ${boardResearch(b).length} findings pinned` : 'No research attached'} · context versions used: {ctxs.map((id) => { const c = data.context.find((x) => x.id === id); const multi = profilesOf(p).length > 1; return (multi ? (profilesOf(p).find((x) => x.id === (c?.profile_id || 'main'))?.name || 'Main') + ' ' : '') + 'v' + ctxVersion(c); }).join(', ') || 'none yet'}</p>
              {roots.length ? <ul className="lineage">{roots.map((v) => <Lineage key={v.id} v={v} />)}</ul> : <p className="text-xs text-muted-foreground">No variations yet.</p>}</div>; }) : <p className="text-muted-foreground">No boards yet.</p>}
        </Panel>
        <div className="my-1.5 mb-3.5 flex flex-wrap items-center gap-2" role="group" aria-label="Filter jobs">{chips.map(([k, l]) => <Button key={k} size="sm" variant={filter === k ? 'default' : 'outline'} data-hist-filter={k} aria-pressed={filter === k} onClick={() => ui.set({ histFilter: k })}>{l}</Button>)}<span className="text-xs text-muted-foreground">{shown.length} of {jobs.length} jobs</span></div>
        {shown.map((j) => { const run = runnerOf(j.runner_id); return (
          <Panel key={j.id} title={j.type.replaceAll('_', ' ')} action={<span className="flex items-center gap-2"><Tag kind={jobKind(j)}>{JOB_LABEL[j.status] || j.status}</Tag>{activeJob(j) ? <Button size="sm" variant="outline" data-cancel-job={j.id} onClick={() => jobAction('cancel', j.id).catch((e) => toast(e.message))}>Cancel</Button> : ['failed', 'timed_out', 'cancelled'].includes(j.status) && !j.retried_by ? <Button size="sm" variant="outline" data-retry-job={j.id} onClick={() => jobAction('retry', j.id).catch((e) => toast(e.message))}>Retry</Button> : null}</span>}>
            <p>{run?.name || j.runner_name || 'Removed runner'} · {fmtTime(j.created_at)} {fmtDuration(j) ? '· ' + fmtDuration(j) : ''}<br /><span className="text-xs text-muted-foreground">Input hash {fmtHash(j.input_hash)} · context {fmtHash(j.context?.hash)}{j.retry_of ? ' · retry of ' + j.retry_of.slice(0, 6) : ''}{j.retried_by ? ' · retried as ' + j.retried_by.slice(0, 6) : ''}</span></p>
            <RefThumbs job={j} />{j.events.map((e: any, i: number) => <p key={i} className="text-xs">{new Date(e.time * 1000).toLocaleTimeString()} &nbsp; {e.message}</p>)}
            <div className="mt-2 flex flex-wrap gap-x-3.5 text-xs">{j.runner_name === 'Hidden (blind)' ? <span className="text-muted-foreground">Envelope and log hidden while the comparison is blind</span> : <a className="underline" target="_blank" rel="noopener" href={`/assets/jobs/${j.id}/envelope.json`}>envelope.json</a>}<a className="underline" target="_blank" rel="noopener" href={`/assets/jobs/${j.id}/TASK.md`}>TASK.md</a>{run?.type === 'cli' && <a className="underline" target="_blank" rel="noopener" href={`/assets/jobs/${j.id}/runner.log`}>runner.log</a>}{j.variant_id && <Link className="underline" href={boardPath(r, data.board.find((b) => b.id === j.board_id) || {}, 'review', j.variant_id)}>Output variation</Link>}</div>
          </Panel>); })}
        {!shown.length && <Empty title="No jobs match" text="Your first job will appear here." />}
      </Content>
    </>
  );
}

/* ---------- settings: agents & runners ---------- */
function RunnerRow({ x, bwrap }: { x: any; bwrap: boolean }) {
  const [msg, setMsg] = useState('');
  const save = async (e: React.MouseEvent<HTMLButtonElement>) => {
    const row = (e.currentTarget as HTMLElement).closest('[data-runner]') as HTMLElement; const q = (s: string) => row.querySelector(s) as HTMLInputElement | null;
    const data: any = { id: x.id, name: q('[data-runner-name]')!.value, enabled: q('[data-runner-enabled]')!.checked }; const model = q('[data-runner-model]'); if (model) data.model = model.value;
    const retries = q('[data-runner-retries]'); if (retries) data.auto_retries = Math.max(0, Math.min(3, parseInt(retries.value || '0', 10) || 0));
    const sbx = q('[data-runner-sandbox]'); if (sbx && !sbx.disabled) data.sandbox = sbx.checked ? 'bwrap' : 'none';
    const env = row.querySelector('[data-runner-env]') as HTMLTextAreaElement | null; if (env) data.env_allowlist = env.value.split(/[\s,]+/).filter(Boolean);
    try { await api('update-runner', data); toast('Runner saved'); await refresh(); } catch (er: any) { toast(er.message); }
  };
  const test = async () => { try { const r = await api('test-runner', { id: x.id }); setMsg(r.message); toast(r.message); } catch (er: any) { toast(er.message); } };
  return (
    <div className="runner-row flex flex-wrap items-start justify-between gap-4 border-b py-4 last:border-0" data-runner={x.id}>
      <div className="grow min-w-[260px]">
        <div className="flex flex-wrap items-center gap-2.5"><label className="sr-only" htmlFor={`rn-${x.id}`}>Name</label><Input id={`rn-${x.id}`} data-runner-name={x.id} defaultValue={x.name} className="w-56" /><Tag kind={x.type === 'fixture' ? '' : 'success'}>{x.type === 'fixture' ? 'Fixture · offline' : 'Local agent'}</Tag>{x.enabled === false && <Tag kind="warn">Disabled</Tag>}</div>
        <p className="mt-1.5 text-xs">{x.type === 'fixture' ? 'Deterministic template runner; no credentials.' : `${x.executable} · timeout ${x.timeout || 120}s`}</p>
        {x.type === 'cli' && <>
          <div className="mt-1.5 flex items-center gap-2"><label className="text-xs" htmlFor={`rm-${x.id}`}>Model</label><Input id={`rm-${x.id}`} data-runner-model={x.id} defaultValue={x.model || ''} placeholder="agent default" className="w-56" /></div>
          <label className="mt-2 block text-xs" htmlFor={`re-${x.id}`}>Environment passed to the agent</label><Textarea id={`re-${x.id}`} data-runner-env={x.id} rows={2} className="font-mono" defaultValue={(x.env_allowlist || ['PATH', 'HOME', 'LANG']).join(', ')} aria-describedby={`env-help-${x.id}`} />
          <div className="mt-2 flex flex-wrap items-center gap-4"><label className="flex items-center gap-2 text-xs font-normal" htmlFor={`rr-${x.id}`}>Automatic retries <Input id={`rr-${x.id}`} type="number" min={0} max={3} data-runner-retries={x.id} defaultValue={x.auto_retries || 0} className="w-16" /></label><label className="flex items-center gap-2 text-xs font-normal"><input type="checkbox" data-runner-sandbox={x.id} defaultChecked={!!x.sandbox} disabled={!bwrap} /> Filesystem sandbox (bubblewrap)</label></div>
          <p className="mt-1.5 text-xs text-muted-foreground">{bwrap ? 'With the sandbox on, the agent can write only its own job folder; your home directory and other projects are hidden and the rest is read-only.' : 'bubblewrap is not usable on this machine, so agents run with only the environment allowlist as protection.'} Failed or timed-out jobs retry up to the chosen number of times with the same inputs.</p>
          <p className="text-xs text-muted-foreground" id={`env-help-${x.id}`}>Only these variables are visible to the agent process. Add the API-key variable your agent needs; nothing else is inherited.</p></>}
        <p className="text-xs text-muted-foreground" id={`test-${x.id}`} role="status">{msg}</p>
      </div>
      <div className="flex items-center gap-2"><label className="flex items-center gap-2 text-xs font-normal"><input type="checkbox" data-runner-enabled={x.id} defaultChecked={x.enabled !== false} /> Enabled</label><Button size="sm" variant="outline" data-save-runner={x.id} onClick={save}>Save</Button><Button size="sm" variant="outline" data-test-runner={x.id} onClick={test}>Test</Button><Button size="icon-sm" variant="ghost" data-delete-runner={x.id} aria-label={`Delete ${x.name}`} onClick={() => deleteRunner(x.id)}><Ic name="trash" size={13} /></Button></div>
    </div>
  );
}
export function SettingsView() {
  const data = useData(); const agents = useAgents(); const cfg = useConfig(); const [sel, setSel] = useState('');
  const a = agents.find((x) => x.id === sel);
  const add = async () => { if (!sel) return toast('Choose an installed coding agent'); try { await api('local-runner', { agent: sel, model: (document.getElementById('local-model') as HTMLInputElement).value.trim() }); toast('Local agent configuration added'); await refresh(); } catch (e: any) { toast(e.message); } };
  return (
    <>
      <Heading title="Agents & models" sub="Use the coding agents installed on this machine. Each configuration is an independent runner." />
      <Content>
        <Note>Fixture runners work offline with no API key. Local execution uses each agent’s existing authentication. Model IDs come from local metadata when available; installation does not guarantee model access.</Note>
        <Panel title="Local coding agents" action={<Button variant="outline" size="sm" data-action="scan-agents" onClick={() => runAction('scan-agents')}><Ic name="refresh" size={13} /> Rescan installed</Button>}>
          <div className="grid gap-4 md:grid-cols-2">
            <div><label className="text-xs font-medium" htmlFor="local-agent">Coding agent</label><select id="local-agent" value={sel} onChange={(e) => setSel(e.target.value)} className={cn(nativeSelect, 'mt-1.5')}><option value="">Choose an installed agent</option>{agents.map((x) => <option key={x.id} value={x.id} disabled={!x.supported}>{x.name}{x.supported ? '' : ' · adapter not available'}</option>)}</select><p id="agent-path" className="mt-1.5 text-xs text-muted-foreground">{a ? a.executable : `${agents.length} installed tools detected on PATH`}</p></div>
            <div><label className="text-xs font-medium" htmlFor="local-model">Model</label><Input id="local-model" list="model-list" placeholder="Agent default, or enter a model ID" key={sel} className="mt-1.5" /><datalist id="model-list">{(a?.models || []).map((m: string) => <option key={m} value={m} />)}</datalist><p id="model-source" className="mt-1.5 text-xs text-muted-foreground">{a ? a.model_source : 'Select a coding agent to see locally available model information.'}</p></div>
          </div>
          <Button className="primary mt-4" data-action="add-local-runner" onClick={add}><Ic name="plus" size={13} /> Add runner configuration</Button>
        </Panel>
        <Panel title="Runner configurations">{data.runner.map((x) => <RunnerRow key={x.id} x={x} bwrap={cfg.bwrap} />)}</Panel>
        <ReviewDocsPanel />
      </Content>
    </>
  );
}
void useMemo; void jobRefUrl; void dataStore; void rescanAgents;
