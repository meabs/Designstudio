import { useEffect, useRef, useState } from 'react';
import { api, useConfig, useData, runnerHistory } from '@/lib/store';
import { fmtDur, kTokens } from '@/lib/format';
import { Progress } from '@/components/ui/progress';
import { cn } from '@/lib/utils';

const SLOW_HINT_S = 90;
const logOpen = new Set<string>();

// Live progress for a running or queued job: elapsed, files written, last activity, and an expandable log tail.
export function JobProgress({ job }: { job: any }) {
  const [p, setP] = useState<any>(null);
  useEffect(() => {
    let live = true; const tick = async () => { try { const x = await api('job-progress/' + job.id); if (live) setP(x); } catch { /* next tick */ } };
    tick(); const t = setInterval(tick, 1500); return () => { live = false; clearInterval(t); };
  }, [job.id]);
  const cfg = useConfig();
  if (!p) return <p className="text-xs text-muted-foreground">Checking progress…</p>;
  if (p.status === 'queued') return <div className="jp text-[13px]"><strong>Waiting for a free worker</strong>{p.queue_position ? ` · position ${p.queue_position} in the queue` : ''}{cfg.max_jobs ? ` · ${cfg.max_jobs} job${cfg.max_jobs === 1 ? '' : 's'} run${cfg.max_jobs === 1 ? 's' : ''} at a time` : ''}</div>;
  const exp = p.screens_expected; const done = p.screens_written;
  const bits = [exp ? `${done} of ${exp} screens written` : `${p.file_count} file${p.file_count === 1 ? '' : 's'} written`];
  if (p.status === 'running') bits.push(p.file_count || p.log_tail ? `last activity ${fmtDur(p.idle_s)} ago` : 'agent starting up');
  return (
    <div className="jp text-[13px]">
      <div><strong>{p.status === 'running' ? 'Running' : 'Ran'} {fmtDur(p.elapsed_s)}</strong>{p.timeout_s ? ` of up to ${fmtDur(p.timeout_s)}` : ''} · {bits.join(' · ')}</div>
      {exp ? <Progress value={Math.round((100 * done) / exp)} className="my-2" aria-label="Screens written" /> : <div className="jp-bar indeterminate my-2 h-1.5 overflow-hidden rounded bg-muted"><span className="block h-full w-1/3 animate-[jpslide_1.4s_ease-in-out_infinite] rounded bg-foreground" /></div>}
      {p.status === 'running' && p.idle_s > SLOW_HINT_S && <p className="jp-hint my-1.5 rounded-md bg-warning/10 px-2.5 py-2 text-xs text-warning-foreground">No new output for {fmtDur(p.idle_s)}. Some agents write their files only at the end, so this can be normal; use Cancel if it looks stuck.</p>}
      <details data-log={job.id} open={logOpen.has(job.id)} onToggle={(e) => { e.currentTarget.open ? logOpen.add(job.id) : logOpen.delete(job.id); }} className="mt-1.5">
        <summary className="cursor-pointer text-xs text-muted-foreground">Live output</summary>
        {p.log_hidden ? <p className="text-xs text-muted-foreground">Live output is hidden while this comparison is blind.</p> : <>
          {p.log_tail ? <pre className="jp-log my-2 max-h-44 overflow-auto whitespace-pre-wrap break-words rounded-md bg-neutral-900 p-2.5 font-mono text-[11px] leading-relaxed text-neutral-200" tabIndex={0}>{p.log_tail}</pre> : <p className="text-xs text-muted-foreground">Nothing printed yet. Some agents print only when they finish; watch the file list instead.</p>}
          {p.files.length ? <p className="text-xs text-muted-foreground">Files so far: {p.files.map((f: any) => <span key={f.name} className="mr-1 font-mono">{f.name}</span>)}</p> : null}
        </>}
      </details>
    </div>
  );
}

const GEN = ['generate_board', 'revise_board'];
const sum = (a: any[], f: (x: any) => number | null | undefined) => a.reduce((n, x) => n + (f(x) || 0), 0);
export function usageLine(board: any, data: any): string {
  if (board.blind && !board.revealed) return 'Agent usage hidden while this comparison is blind';
  const jobs = data.job.filter((j: any) => j.board_id === board.id && GEN.includes(j.type)); if (!jobs.length) return '';
  const timed = jobs.filter((j: any) => j.usage); const toks = timed.filter((j: any) => j.usage.tokens != null);
  const agents = timed.filter((j: any) => data.runner.find((r: any) => r.id === j.runner_id)?.type === 'cli').length;
  return `Agent usage on this board: ${jobs.length} run${jobs.length === 1 ? '' : 's'} · ${fmtDur(sum(timed, (j) => j.usage.duration_s)) || '0s'} agent time${agents ? ` · ${toks.length ? kTokens(sum(toks, (j) => j.usage.tokens)) + ' tokens' : 'no token counts reported'}${toks.length && toks.length < agents ? ` (only ${toks.length} of ${agents} agent runs report them)` : ''}` : ''}`;
}
export const usageNote = (j: any) => (j.usage ? ` · took ${fmtDur(j.usage.duration_s)}${j.usage.tokens != null ? ` · ${kTokens(j.usage.tokens)} tokens` : ''}` : '');

// Pre-generate estimate from the median of the user's own earlier runs of the same runner; never a dollar figure.
export function EstimateBox({ board }: { board: any }) {
  const ref = useRef<HTMLDivElement>(null); const data = useData(); const cfg = useConfig();
  const [ids, setIds] = useState<string[]>([]);
  useEffect(() => {
    const form = ref.current?.closest('form'); if (!form) return;
    const read = () => setIds(new FormData(form).getAll('runners') as string[]); read();
    form.addEventListener('change', read); return () => form.removeEventListener('change', read);
  }, []);
  const runs = data.job.filter((j) => j.board_id === board?.id && GEN.includes(j.type)).length;
  const warn = runs >= 8 ? <><br /><strong>This board already has {runs} runs.</strong> Each run uses your own agent subscription or API credits.</> : null;
  let body: React.ReactNode = null;
  if (ids.length) {
    const rows = ids.map((id) => ({ r: data.runner.find((x) => x.id === id), h: runnerHistory(id, data) }));
    const cli = rows.filter((x) => x.r?.type === 'cli'); const known = cli.filter((x) => x.h.n); const unknown = cli.filter((x) => !x.h.n);
    if (!cli.length) body = <><strong>Estimate:</strong> template fixtures finish in seconds and use no agent credits.{warn}</>;
    else {
      const lanes = Array(Math.max(1, cfg.max_jobs || 3)).fill(0);
      known.map((x) => x.h.median as number).sort((a, b) => b - a).forEach((d) => { lanes[lanes.indexOf(Math.min(...lanes))] += d; });
      body = <><strong>Estimate:</strong> {known.length ? <>~{fmtDur(Math.max(...lanes))} until all variants are ready ({known.map((x, i) => <span key={i}>{i ? ' · ' : ''}{x.r.name} ~{fmtDur(x.h.median)} <span className="text-muted-foreground">({x.h.n} earlier run{x.h.n === 1 ? '' : 's'})</span></span>)}). Agent time ~{fmtDur(sum(known, (x) => x.h.median))}.</> : 'no history for these agents yet, so no estimate.'}{unknown.length && known.length ? ` No history yet for ${unknown.map((x) => x.r.name).join(', ')}, so it is not in the estimate.` : ''} Based on your own past runs here; real agents vary, and the studio cannot see your agent’s price or token spend.{warn}</>;
    }
  }
  return <div ref={ref} id="estimate" aria-live="polite" className={cn('mb-4 rounded-lg border bg-muted/60 px-3 py-2.5 text-xs leading-relaxed', !body && 'hidden')}>{body}</div>;
}
