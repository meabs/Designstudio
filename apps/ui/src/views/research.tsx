import { useEffect, useState } from 'react';
import { Link, useCurrent, boardPath, nav } from '@/lib/router';
import { useData, useUi, ui, runnerOf, enabledRunners, activeJob, api, refresh } from '@/lib/store';
import { findingsForHandoff, researchJobs, researchPending, researchStatus, parseSources } from '@/lib/research';
import { isUrl, uuid } from '@/lib/format';
import { Heading } from '@/components/app/chrome';
import { Tag, Panel, Content, Note, toast } from '@/components/app/feedback';
import { Ic } from '@/components/app/icons';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { RefPicker } from '@/components/app/refs';
import { JobProgress } from '@/components/app/progress';
import { RefThumbs } from './board';
import { handoff, jobAction, nativeSelect } from '@/actions';
import { cn } from '@/lib/utils';

function Results({ pid }: { pid: string }) {
  const { r } = useCurrent(); const data = useData(); const jobs = researchJobs(data, pid); const results = data.research.filter((x) => x.project_id === pid);
  if (!jobs.length && !results.length) return <div className="research-empty rounded-xl border border-dashed p-9 text-center text-muted-foreground"><strong>Your findings will appear here</strong><p>Start with a question. Progress and results stay on this page.</p></div>;
  return (
    <>
      {researchPending(jobs).map((j) => (
        <Panel key={j.id} className="research-progress" title={<span className="flex items-center gap-2">{activeJob(j) && <span className="progress size-1.5 animate-pulse rounded-full bg-foreground/60" />}{researchStatus(j)}</span>} action={<span className="flex items-center gap-2"><Tag>{runnerOf(j.runner_id)?.name || 'Agent'}</Tag>{activeJob(j) ? <Button size="sm" variant="outline" data-cancel-job={j.id} onClick={() => jobAction('cancel', j.id).catch((e) => toast(e.message))}><Ic name="stop" size={13} /> Cancel</Button> : !j.retried_by ? <Button size="sm" variant="outline" data-retry-job={j.id} onClick={() => jobAction('retry', j.id).catch((e) => toast(e.message))}><Ic name="refresh" size={13} /> Retry</Button> : null}</span>}>
          <p><strong>{j.brief}</strong></p><RefThumbs job={j} /><p className="my-2">{j.events.at(-1)?.message || 'Waiting for the agent to start.'}</p>{activeJob(j) && <div className="job-progress" data-progress={j.id}><JobProgress job={j} /></div>}
          <details className="mt-2"><summary className="cursor-pointer text-xs">Activity details</summary>{j.events.map((e: any, i: number) => <p key={i} className="text-xs">{new Date(e.time * 1000).toLocaleTimeString()} · {e.message}</p>)}</details>
          {['failed', 'timed_out', 'cancelled'].includes(j.status) && <p className="mt-2">Your earlier results are preserved. Retry, or adjust the question or agent above.</p>}
        </Panel>
      ))}
      {results.slice().sort((a, b) => (b.created_at || 0) - (a.created_at || 0)).map((res) => {
        const job = jobs.find((j) => j.id === res.job_id); const fixture = runnerOf(job?.runner_id)?.type === 'fixture'; const chosen = findingsForHandoff(res); const linked = data.board.filter((b) => b.research_id === res.id); const anySel = res.findings.some((f: any) => f.selected);
        return (
          <Panel key={res.id} className="research-result" title={<span className="flex flex-col items-start gap-2"><Tag kind="success">Research ready</Tag>{res.brief}</span>} action={<span className="text-xs text-muted-foreground">{res.findings.length} findings</span>}>
            <RefThumbs job={job} />
            {(res.limitations || []).length > 0 && <Note kind="warn"><strong>Stated limits of this research:</strong><ul className="ml-4 mt-1.5 list-disc">{res.limitations.map((l: string, i: number) => <li key={i}>{l}</li>)}</ul></Note>}
            <p className="mb-2">Use all findings below, or tick the ones you want to take forward.</p>
            {res.findings.map((f: any) => <label key={f.id} className="finding mb-2 flex items-start gap-2.5 text-[13px] font-normal"><input type="checkbox" className="mt-1 size-4" data-finding={f.id} data-research={res.id} checked={!!f.selected} onChange={async (e) => { try { await api('finding', { id: f.id, research_id: res.id, selected: e.target.checked }); await refresh(); } catch (er: any) { toast(er.message); } }} /><span><strong>{f.title}</strong> <Tag kind={f.verification === 'verified_source' ? 'success' : 'warn'}>{f.verification === 'unverified_claim' ? (fixture ? 'Synthetic · Unverified' : 'Unverified') : f.verification === 'verified_source' ? 'Verified source' : 'User-supplied source'}</Tag><span className="finding-detail mt-0.5 block text-muted-foreground">{f.detail}</span></span></label>)}
            {res.findings.length ? <div className="research-next mt-4 flex flex-wrap items-center justify-between gap-3 rounded-lg border bg-muted/50 p-3"><div><strong>{anySel ? chosen.length + ' selected findings' : 'All ' + chosen.length + ' findings'} → screen generation</strong><p className="text-xs text-muted-foreground">The board keeps a copy of this research for generation and revisions.</p></div><Button className="primary" data-handoff={res.id} onClick={() => handoff(res.id)}>{anySel ? 'Use selected findings' : 'Use all findings'} <Ic name="forward" size={13} /></Button></div> : <p>No findings returned. Try refining your research question.</p>}
            {linked.map((b) => <p key={b.id} className="mt-2">Used in <Link className="research-link underline" href={boardPath(r, b)}>{b.title}</Link> · {b.research_findings.length} findings carried forward</p>)}
            {res.sources?.length ? <details open className="mt-3"><summary className="cursor-pointer text-[13px]">Source material ({res.sources.length})</summary>{res.sources.map((s: any, i: number) => <p key={i} className="my-2">{isUrl(s.url) ? <a className="research-link underline" target="_blank" rel="noopener noreferrer" href={s.url}>{s.title || s.url}</a> : (s.title || 'Supplied source')}{s.text ? <><br />“{s.text}”</> : null}<br /><span className="text-xs text-muted-foreground">{s.verification === 'source_supplied_by_user' ? 'Supplied by you; not independently verified' : s.verification || 'Unverified'}</span></p>)}</details> : <p className="mt-3 text-xs text-muted-foreground">No sources were supplied, so every finding is unverified.</p>}
          </Panel>
        );
      })}
    </>
  );
}

export function ResearchView() {
  const { p } = useCurrent(); const data = useData(); const busyUi = useUi((s) => s.busy); const busy = busyUi || researchJobs(data, p.id).some(activeJob);
  const run = async () => {
    if (busy) return; const brief = (document.getElementById('research-brief') as HTMLTextAreaElement).value.trim(); if (!brief) return toast('Enter a research question first');
    ui.set({ busy: true });
    try {
      await api('research', { project_id: p.id, brief, sources: parseSources((document.getElementById('sources') as HTMLTextAreaElement).value), reference_ids: [...document.querySelectorAll<HTMLInputElement>('#research-refs input[name=references]:checked')].map((i) => i.value), runner_ids: [(document.getElementById('research-runner') as HTMLSelectElement).value], idempotency_key: uuid() });
      await refresh();
    } catch (e: any) { toast(e.message); } finally { ui.set({ busy: false }); }
  };
  return (
    <>
      <Heading title="Research → design" sub="Run research, review the findings, then carry them straight into screen generation." />
      <Content>
        <div className="workflow-steps mb-6 flex flex-wrap items-center gap-4 text-xs text-muted-foreground"><strong className="rounded-lg bg-muted px-3.5 py-2.5 text-foreground">1 · Research</strong><span>→</span><span>2 · Generate screens</span><span>→</span><span>3 · Review &amp; prototype</span></div>
        <Panel title="What would you like to understand?">
          <label className="mb-1.5 block text-xs font-medium" htmlFor="research-brief">Research question</label><Textarea id="research-brief" rows={3} placeholder="What makes a financial eligibility journey clearer?" />
          <label className="mb-1.5 mt-3 block text-xs font-medium" htmlFor="sources">Source material · one URL or pasted excerpt per line</label><Textarea id="sources" rows={3} placeholder="https://…  (URLs are kept as supplied sources; nothing is fetched or verified for you)" />
          <div className="mb-1.5 mt-3 text-xs font-medium">Reference images (optional)</div><RefPicker id="research-refs" selected={[]} projectId={p.id} />
          <div className="mt-4 flex items-end justify-between gap-3"><div><label className="mb-1.5 block text-xs font-medium" htmlFor="research-runner">Research agent</label><select id="research-runner" className={cn(nativeSelect, 'w-auto')}>{enabledRunners().map((x) => <option key={x.id} value={x.id}>{x.name}{x.type === 'fixture' ? ' · template demo' : ''}</option>)}</select></div><Button className="primary" data-action="run-research" disabled={busy} onClick={run}><Ic name="spark" /> Run research</Button></div>
          <p className="mt-3 text-xs text-muted-foreground">Findings appear below automatically. Without sources, findings are labelled unverified.</p>
        </Panel>
        <div id="research-results"><Results pid={p.id} /></div>
      </Content>
    </>
  );
}
void nav; void useEffect; void useState;
