import { useEffect, useLayoutEffect, useMemo, useState, type ReactNode } from 'react';
import { Link, navigate, useCurrent, nav, boardPath } from '@/lib/router';
import { useData, useUi, ui, variantsOf, visibleVariants, defaultVariant, roundsOf, strandedJobs, variantStatus, checksOf, unresolvedReviews, activeJob, runnerOf, img, live, api, freeOf } from '@/lib/store';
import { twinLink, ProfileTag } from '@/tools';
import { CutOff } from '@/assist';
import { frameOf, cardWidth, hasPhoneView, reviewBase, targetLabel } from '@/lib/frame';
import { boardResearch } from '@/lib/research';
import { fmtWhen, fmtHash } from '@/lib/format';
import { elementRects, fitZoom, ZMIN, ZMAX } from '@/lib/dom';
import { Button } from '@/components/ui/button';
import { SegmentedControl, SegmentedControlItem } from '@/components/ui/segmented-control';
import { Ic } from '@/components/app/icons';
import { Heading } from '@/components/app/chrome';
import { Tag, Empty, Note, toast } from '@/components/app/feedback';
import { JobProgress, usageLine, usageNote } from '@/components/app/progress';
import { jobAction, openLive, openRef, pinModal, pinEdit, pinDelete, runAction, blindPick, blindReveal, acceptRevision, revertRevision } from '@/actions';
import { nativeSelect } from '@/actions';
import { Inspector } from './inspector';
import { EditCanvas } from './editor';
import { cn } from '@/lib/utils';

const JOB_LABEL: Record<string, string> = { queued: 'Queued', running: 'Running', succeeded: 'Succeeded', failed: 'Failed', timed_out: 'Timed out', cancelled: 'Cancelled' };
const jobKind = (j: any) => (j.status === 'succeeded' ? 'success' : j.status === 'failed' ? 'fail' : ['timed_out', 'cancelled'].includes(j.status) ? 'warn' : '');

export function RefThumbs({ job }: { job: any }) {
  if (!job?.references?.length) return null; const n = job.references.length;
  return <div className="refstrip my-2 flex flex-wrap items-center gap-2" aria-label="Reference images sent with this job">{job.references.map((r: any) => <button key={r.file} className="refthumb size-10 overflow-hidden rounded-md border p-0" data-ref-open={`${job.id}:${r.file}:${r.name}`} title={r.name + (r.note ? ' · ' + r.note : '')} onClick={() => openRef(`${job.id}:${r.file}:${r.name}`)}><img src={`/assets/jobs/${job.id}/references/${r.file}`} alt={r.name} className="size-full object-cover" /></button>)}<span className="text-xs text-muted-foreground">{n} reference{n === 1 ? '' : 's'} sent</span></div>;
}

export function Thumb({ src, alt, className }: { src: string; alt: string; className?: string }) {
  const [bad, setBad] = useState(false); useEffect(() => setBad(false), [src]);
  return bad ? <div className="nothumb grid size-full place-items-center p-3 text-center text-xs text-muted-foreground">No screenshot available · use live preview</div> : <img src={src} alt={alt} loading="lazy" className={className} onError={() => setBad(true)} />;
}

/* ---------- canvas helpers: zoom, fit, scroll-to, keyboard ---------- */
export function setZoom(z: number) { ui.set({ zoom: Math.round(Math.min(ZMAX, Math.max(ZMIN, z))) }); }
export function FloatBar({ mode }: { mode: string }) {
  const zoom = useUi((s) => s.zoom);
  return (
    <div className="floatbar sticky bottom-4 mx-auto mt-4 flex w-fit items-center gap-1 rounded-full bg-foreground px-2 py-1.5 text-background shadow-lg" role="toolbar" aria-label="Canvas controls">
      <button className="grid size-8 place-items-center rounded-full hover:bg-background/15" data-action="zoom-out" aria-label="Zoom out" title="Zoom out (−)" onClick={() => setZoom(zoom - 10)}><Ic name="minus" size={14} /></button>
      <button className="zoomval min-w-12 rounded-full px-2 text-xs hover:bg-background/15" data-action="zoom-reset" aria-label="Reset zoom to 100%" title="Reset (0)" onClick={() => setZoom(100)}>{zoom}%</button>
      <button className="grid size-8 place-items-center rounded-full hover:bg-background/15" data-action="zoom-in" aria-label="Zoom in" title="Zoom in (+)" onClick={() => setZoom(zoom + 10)}><Ic name="plus" size={14} /></button>
      <span className="mx-1 h-4 w-px bg-background/30" />
      <button className="flex items-center gap-1.5 rounded-full px-2.5 text-xs hover:bg-background/15" data-action="zoom-fit" title="Fit (1)" onClick={() => setZoom(fitZoom(mode))}><Ic name="fit" size={14} /> Fit</button>
    </div>
  );
}
export function useCanvasEffects(mode: string, deps: unknown[]) {
  const fitPending = useUi((s) => s.fitPending); const scrollTo = useUi((s) => s.scrollTo);
  useLayoutEffect(() => {
    if (fitPending && document.querySelector('.frames,.review-area')) { const z = Math.max(ZMIN, Math.min(100, fitZoom(mode))); ui.set({ fitPending: false, zoom: z }); }
  }, [fitPending, mode, ...deps]);
  useEffect(() => { if (scrollTo) { document.getElementById(scrollTo)?.scrollIntoView({ block: 'nearest', inline: 'center' }); ui.set({ scrollTo: '' }); } }, [scrollTo, ...deps]);
}
export function useCanvasKeys() {
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      const typing = (e.target as HTMLElement)?.matches?.('input,textarea,select,[contenteditable]') || document.querySelector('[data-slot=dialog-popup]');
      const path = location.pathname.split('/').filter(Boolean); const onBoard = path[2] === 'boards' && path[3];
      if (!typing && !e.ctrlKey && !e.metaKey && !e.altKey && onBoard) {
        const k = e.key; const z = ui.get().zoom; const mode = path[4] || '';
        if (k === 'v' || k === 'V') return ui.set({ tool: 'move' }); if (k === 'c' || k === 'C') return ui.set({ tool: 'comment' }); if (k === 'e' || k === 'E') return ui.set({ tool: 'edit' });
        if (k === '+' || k === '=') return setZoom(z + 10); if (k === '-') return setZoom(z - 10); if (k === '0') return setZoom(100); if (k === '1') return setZoom(fitZoom(mode));
        if (k === 'Escape' && ui.get().activePin) return ui.set({ activePin: '' });
      }
    };
    const wheel = (e: WheelEvent) => { if (!e.ctrlKey || !(e.target as HTMLElement)?.closest?.('.canvas')) return; e.preventDefault(); setZoom(ui.get().zoom + (e.deltaY < 0 ? 10 : -10)); };
    document.addEventListener('keydown', key); document.addEventListener('wheel', wheel, { passive: false });
    return () => { document.removeEventListener('keydown', key); document.removeEventListener('wheel', wheel); };
  }, []);
}

/* ---------- board page ---------- */
function BoardTabs({ b, vs, mode }: { b: any; vs: any[]; mode: string }) {
  const { r } = useCurrent(); const dv = defaultVariant(vs);
  const t = (label: string, href: string, on: boolean, extra?: ReactNode) => <Link key={label} href={href} role="tab" aria-selected={on} className={cn('tab -mb-px border-b-2 px-0.5 pb-2.5 text-[13px] text-muted-foreground transition-colors hover:text-foreground', on ? 'active border-foreground font-semibold text-foreground' : 'border-transparent')}>{label}{extra}</Link>;
  return <nav className="tabs flex gap-6 overflow-x-auto" role="tablist" aria-label="Board views">{t('Research', nav(r, 'research'), false)}{t('Variants', boardPath(r, b), !mode, vs.length ? <span className="chip ml-1.5 rounded bg-muted px-1.5 py-0.5 text-xs">{vs.length}</span> : null)}{t('Compare', boardPath(r, b, 'compare'), mode === 'compare')}{t('Review', dv ? boardPath(r, b, 'review', dv.id) : boardPath(r, b, 'review'), mode === 'review')}</nav>;
}
function BlindBanner({ b }: { b: any }) {
  if (b.blind && !b.revealed) return <div className="blindbar mx-4 mt-3 flex flex-wrap items-center gap-3 rounded-lg border bg-muted/60 px-3 py-2.5 text-[13px] lg:mx-7" role="status"><Ic name="eye" size={15} /><span><strong>Blind comparison.</strong> Runner identities are hidden until you choose. Pick the option you prefer, approve one, or reveal.</span><span className="grow" /><Button size="sm" variant="outline" data-blind-reveal onClick={blindReveal}>Reveal without choosing</Button></div>;
  if (b.blind && b.revealed) { const c = b.blind_choice; return <div className="blindbar revealed mx-4 mt-3 flex items-center gap-3 rounded-lg border border-success/32 bg-success/6 px-3 py-2.5 text-[13px] lg:mx-7" role="status"><Ic name="check" size={15} /><span>{c && c.variant_id ? <>You preferred <strong>Option {c.label || '?'}</strong>, which was <strong>{c.runner_name}</strong>{c.reason && c.reason !== 'Approved' ? ` · “${c.reason}”` : c.reason === 'Approved' ? ' (by approving it)' : ''}.</> : 'Identities revealed without a choice.'}</span></div>; }
  return null;
}
export function BoardView() {
  const { r, b, vs, v } = useCurrent(); const data = useData(); const showReverted = useUi((s) => s.showReverted);
  useCanvasKeys(); useCanvasEffects(r.mode === 'review' ? 'review' : 'board', [vs.length, r.mode]);
  if (!b) return <Empty title="No board" text="Create a board to begin." />;
  const found = boardResearch(b); const jobsNow = data.job.filter((j) => j.board_id === b.id && activeJob(j));
  const head = (
    <>
      <Heading title={b.title} sub={`Explore independent directions. Keep your design principles in focus.${targetLabel(b) ? ' Designing for: ' + targetLabel(b) + '.' : ''}`} tabs={<BoardTabs b={b} vs={vs} mode={r.mode} />} />
      <BlindBanner b={b} />
      {(found.length > 0 || jobsNow.length > 0) && <div className="board-context mx-4 mt-3 lg:mx-7">
        {found.length > 0 && <details className="rounded-lg border bg-background px-3 py-2 text-[13px]"><summary className="flex cursor-pointer items-center gap-2"><Ic name="research" size={13} /> {found.length} research findings carried into this board</summary>{found.map((f: any) => <p key={f.id} className="my-2"><strong>{f.title}</strong><br />{f.detail} <span className="text-xs text-muted-foreground">{f.verification}</span></p>)}<Link className="research-link underline" href={nav(r, 'research')}>View source research</Link></details>}
        {jobsNow.map((j) => <div key={j.id} className="board-job mt-2 flex items-center justify-between text-xs"><span className="flex items-center gap-2"><span className="progress size-1.5 animate-pulse rounded-full bg-foreground/60" /> {runnerOf(j.runner_id)?.name} · {j.status}</span><span className="text-muted-foreground">{j.events.at(-1)?.message || 'Queued'}</span></div>)}
      </div>}
    </>
  );
  if (r.mode === 'compare') return <>{head}<CompareView b={b} vs={vs} /></>;
  if (r.mode === 'review') return <>{head}<ReviewView b={b} vs={vs} v={v} /></>;
  const stranded = strandedJobs(b);
  if (!vs.length && !stranded.length) return <>{head}<div className="canvas p-6"><Empty title="One brief. Different possibilities." text="Generate independent screen boards from your shared design context."><p className="mb-4 text-xs text-muted-foreground">{b.screens.join(' → ')}</p><Button className="primary" data-action="generate" onClick={() => runAction('generate')}><Ic name="spark" /> Generate variants</Button></Empty></div></>;
  const shown = visibleVariants(b); const hidden = vs.length - shown.length; const usage = usageLine(b, data);
  return (
    <>
      {head}
      {usage && <div className="usage-line px-4 pt-3 text-xs text-muted-foreground lg:px-7">{usage}</div>}
      <div className="canvas-toolbar flex flex-wrap items-center justify-between gap-x-4 gap-y-2 px-4 py-3 text-xs text-muted-foreground lg:px-7">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1"><span className="size-1.5 rounded-full bg-success" />{vs.length} variations · {b.screens.length} screens per board{(b.reference_ids || []).length ? <> · <Ic name="image" size={12} /> {(b.reference_ids || []).length} reference image{(b.reference_ids || []).length === 1 ? '' : 's'}</> : null}
          {hidden ? <> · <button className="underline" data-action="toggle-reverted" onClick={() => ui.set({ showReverted: !showReverted })}>Show {hidden} reverted</button></> : showReverted && vs.some((x) => x.review_state === 'reverted') ? <> · <button className="underline" data-action="toggle-reverted" onClick={() => ui.set({ showReverted: false })}>Hide reverted</button></> : null}</div>
        <div className="flex flex-wrap items-center gap-2"><span className="max-md:hidden">Double-click a frame for live preview · Ctrl+scroll to zoom</span>
          {vs.filter((x) => x.review_state !== 'reverted').length >= 2 && <Button size="xs" variant="outline" data-action="mix" onClick={() => runAction('mix')}><Ic name="columns" size={12} /> Mix screens</Button>}
          {!(b.blind && b.revealed) && <Button size="xs" variant={b.blind ? 'default' : 'outline'} data-blind-toggle={String(!b.blind)} aria-pressed={!!b.blind} onClick={async () => { await api('board-blind', { board_id: b.id, blind: !b.blind }); toast(!b.blind ? 'Blind mode on: runner identities are hidden' : 'Blind mode off'); }}><Ic name="eye" size={12} /> Blind compare: {b.blind ? 'on' : 'off'}</Button>}</div>
      </div>
      <div className="canvas figma bg-muted/30 px-4 pb-8 pt-3 lg:px-7">
        {stranded.map((j) => <JobCard key={j.id} j={j} />)}
        <VariantGroups shown={shown} v={v} b={b} />
        <FloatBar mode="board" />
      </div>
    </>
  );
}

/* ---------- job cards ---------- */
function JobCard({ j }: { j: any }) {
  const { r } = useCurrent(); const runner = runnerOf(j.runner_id); const cli = runner?.type === 'cli'; const open = activeJob(j); const last = j.events.at(-1)?.message || 'Queued';
  const name = runner?.name || j.runner_name || 'Removed runner';
  if (!open) return (
    <section className="job-card job-row mb-4 flex gap-3 rounded-xl border border-destructive/30 border-l-[3px] border-l-destructive bg-background p-3.5 max-md:flex-col" role="alert">
      <span className="job-ico mt-0.5 text-destructive-foreground"><Ic name="x" size={13} /></span>
      <div className="job-main min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-x-2.5 gap-y-1.5"><strong>{name}</strong><Tag kind={jobKind(j)}>{JOB_LABEL[j.status] || j.status}</Tag><span className="text-xs text-muted-foreground">{j.type === 'revise_board' ? 'Revision' : 'Generation'} · {fmtWhen(j.created_at)}{j.retry_of ? ` · ${j.auto_retry ? 'automatic ' : ''}retry (attempt ${j.attempt || 2})` : ''}{usageNote(j)}</span></div>
        <div className="job-err mt-1 line-clamp-2 break-words text-[13px] text-muted-foreground" title={last}>{last}</div>
        {j.agent_report?.text && <details className="mt-1"><summary className="cursor-pointer text-xs">What the agent said <span className="text-muted-foreground">(its own words, unverified)</span></summary><pre className="jp-log my-2 max-h-44 overflow-auto whitespace-pre-wrap break-words rounded-md bg-neutral-900 p-2.5 font-mono text-[11px] leading-relaxed text-neutral-200" tabIndex={0}>{j.agent_report.text}</pre></details>}
        <div className="mt-1 flex flex-wrap gap-x-3.5 text-xs"><Link className="underline" href={nav(r, 'history')}>Job history</Link>{cli && <a className="underline" target="_blank" rel="noopener" href={`/assets/jobs/${j.id}/runner.log`}>Runner log <Ic name="external" size={11} className="inline" /></a>}<a className="underline" target="_blank" rel="noopener" href={`/assets/jobs/${j.id}/TASK.md`}>Task <Ic name="external" size={11} className="inline" /></a></div>
      </div>
      <div className="job-acts flex shrink-0 flex-wrap items-start justify-end gap-2 max-md:justify-start"><Button size="sm" className="primary" data-retry-job={j.id} onClick={() => jobAction('retry', j.id).catch((e) => toast(e.message))}><Ic name="refresh" size={13} /> Retry with same inputs</Button><Button size="sm" variant="outline" data-dismiss-job={j.id} title="Hide this failed attempt; it stays in Job history" onClick={() => jobAction('dismiss', j.id).catch((e) => toast(e.message))}>Dismiss</Button></div>
    </section>
  );
  return (
    <section className="variant job-card mb-5 overflow-hidden rounded-xl border bg-background" role="status">
      <div className="variant-bar flex flex-wrap items-center justify-between gap-2 border-b px-4 py-3"><div className="flex items-center gap-2.5"><span className="agent-avatar grid size-7 place-items-center rounded-lg bg-muted"><span className="progress size-1.5 animate-pulse rounded-full bg-foreground/60" /></span><div><strong className="text-[13px]">{name}</strong><div className="text-xs text-muted-foreground">{j.type === 'revise_board' ? 'Revision' : 'Independent generation'} · {JOB_LABEL[j.status] || j.status}{j.retry_of ? ` · ${j.auto_retry ? 'automatic ' : ''}retry (attempt ${j.attempt || 2})` : ''}</div></div></div>
        <div className="flex items-center gap-2"><Tag kind={jobKind(j)}>{JOB_LABEL[j.status] || j.status}</Tag><Button size="sm" variant="outline" data-cancel-job={j.id} onClick={() => jobAction('cancel', j.id).catch((e) => toast(e.message))}><Ic name="stop" size={13} /> Cancel</Button></div></div>
      <div className="job-body px-4 py-3 text-[13px]"><p className="mb-2">{last}</p><div className="job-progress" data-progress={j.id}><JobProgress job={j} /></div>
        <div className="mt-2 flex flex-wrap gap-x-3.5 text-xs"><Link className="underline" href={nav(r, 'history')}>Job history</Link><a className="underline" target="_blank" rel="noopener" href={`/assets/jobs/${j.id}/TASK.md`}>Task instruction <Ic name="external" size={11} className="inline" /></a></div></div>
    </section>
  );
}

/* ---------- variants, grouped by round ---------- */
function VariantGroups({ shown, v, b }: { shown: any[]; v: any; b: any }) {
  const data = useData(); const roundState = useUi((s) => s.roundState);
  const R = useMemo(() => roundsOf(b), [b, data.variant, data.job]);
  const groups = R.rounds.slice().reverse().map((r: any) => ({ r, vs: shown.filter((x) => R.of[x.id] === r) })).filter((g: any) => g.vs.length);
  if (groups.length < 2) return <>{shown.map((vv) => <VariantCard key={vv.id} vv={vv} v={v} b={b} />)}</>;
  const many = shown.length > 6;
  return <>{groups.map((g: any, gi: number) => {
    const key = `${b.id}:${g.r.n}`; const open = roundState[key] ?? (!many || gi === 0 || g.vs.some((x: any) => x.id === v?.id));
    return (
      <details key={key} className="round mb-4" open={open} data-round={key} onToggle={(e) => { const o = e.currentTarget.open; if (o !== open) ui.set((s) => ({ roundState: { ...s.roundState, [key]: o } })); }}>
        <summary className="flex cursor-pointer list-none flex-wrap items-center gap-x-3.5 gap-y-1.5 pb-3 pt-2 text-[13px]"><Ic name="chevron" size={13} className={cn('transition-transform', open && 'rotate-90')} /><strong>{g.r.label}</strong><span className="text-muted-foreground">{fmtWhen(g.r.t)} · {g.vs.length} variant{g.vs.length === 1 ? '' : 's'}</span>{!open && <span className="flex flex-wrap gap-1.5">{g.vs.map((x: any) => <span key={x.id} className="rchip rounded-md bg-muted px-2 py-0.5 text-xs text-muted-foreground">{x.runner_name} v{x.version}{x.approved ? ' · approved' : ''}</span>)}</span>}</summary>
        {g.vs.map((vv: any) => <VariantCard key={vv.id} vv={vv} v={v} b={b} />)}
      </details>
    );
  })}</>;
}
function roundTag(vv: any, b: any, R: any) { const rd = R.of[vv.id]; return rd ? `${R.rounds.length > 1 ? rd.label + ' · ' : ''}${fmtWhen(vv.created_at)} · ` : ''; }
function VariantCard({ vv, v, b }: { vv: any; v: any; b: any }) {
  const { r } = useCurrent(); const data = useData(); const zoom = useUi((s) => s.zoom); const screen = useUi((s) => s.screen);
  const R = useMemo(() => roundsOf(b), [b, data.variant, data.job]);
  const [label, kind] = variantStatus(vv); const checks = checksOf(vv); const failed = checks.filter((x: any) => x.outcome === 'fail').length; const passed = checks.filter((x: any) => x.outcome === 'pass').length; const pending = unresolvedReviews(vv).length;
  const parent = data.variant.find((x) => x.id === vv.parent_id); const changed = new Set(vv.changed_screens || []); const sc = vv.manifest.screens; const edges = vv.manifest.edges || [];
  const select = (sid: string) => { if (ui.get().screen === sid && ui.get().selectedVariant === vv.id) return; ui.set({ screen: sid, selectedVariant: vv.id }); };
  return (
    <section className={cn('variant fsection mb-5 overflow-hidden rounded-xl border bg-background', vv.id === v?.id && 'chosen border-foreground/35 ring-[3px] ring-foreground/5', vv.review_state === 'reverted' && 'reverted opacity-60')} data-variant={vv.id}>
      <div className="variant-bar flex flex-wrap items-center justify-between gap-2 border-b px-4 py-3">
        <div className="flex flex-wrap items-center gap-2.5">
          <span className="agent-avatar grid size-7 place-items-center rounded-lg bg-muted"><Ic name={vv.parent_id ? 'edit' : 'spark'} size={14} /></span>
          <div><strong className="text-[13px]">{vv.runner_name}</strong> <span className="variant-meta text-xs text-muted-foreground">{roundTag(vv, b, R)}{parent ? `Revision of v${parent.version}` : vv.kind === 'mix' ? 'Mixed version' : 'Independent direction'} · v{vv.version}</span></div>
          <Tag kind={kind}>{label}</Tag>{b.blind && b.revealed && vv.blind_label ? <Tag>Option {vv.blind_label}</Tag> : null}{(vv.references || []).length ? <Tag><Ic name="image" size={11} /> {vv.references.length} ref</Tag> : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {b.blind && !b.revealed && vv.review_state !== 'reverted' && <Button size="sm" className="primary" data-blind-pick={vv.id} onClick={() => blindPick(vv.id)}><Ic name="check" size={13} /> I prefer this</Button>}
          {vv.review_state === 'pending' && <><Button size="sm" className="primary" data-accept={vv.id} onClick={() => acceptRevision(vv.id).catch((e) => toast(e.message))}><Ic name="check" size={13} /> Accept</Button><Button size="sm" variant="outline" data-revert={vv.id} onClick={() => revertRevision(vv.id)}><Ic name="undo" size={13} /> Revert</Button></>}
          {parent && <Button size="sm" variant="outline" render={<Link href={`${boardPath(r, b, 'compare')}?left=${parent.id}&right=${vv.id}`} />}><Ic name="columns" size={13} /> vs parent</Button>}
          <Button size="sm" variant="outline" render={<Link href={boardPath(r, b, 'review', vv.id)} />}>Review <Ic name="forward" size={13} /></Button>
        </div>
      </div>
      <div className="frames screens flex items-start gap-2 overflow-x-auto p-5" style={{ zoom: zoom / 100 }}>
        {sc.map((s: any, i: number) => {
          const sel = vv.id === v?.id && s.id === screen; const flow = i < sc.length - 1 && edges.some((e: any) => e.from === s.id && e.to === sc[i + 1].id); const m = (vv.mix_sources || []).find((x: any) => x.screen === s.id);
          return (
            <div key={s.id} className="contents">
              <div className={cn('fframe screen shrink-0 cursor-pointer', sel && 'selected')} style={{ width: cardWidth(b) }} id={`frame-${vv.id}-${s.id}`} role="button" tabIndex={0} aria-label={`${s.title}, ${vv.runner_name} v${vv.version}. Double-click for live preview`} data-select-screen={s.id} data-select-variant={vv.id}
                onClick={() => select(s.id)} onDoubleClick={() => openLive(vv, s.id)} onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); select(s.id); } }}>
                <div className="fname mb-1.5 flex items-center gap-1.5 text-xs text-muted-foreground"><span>{s.title}</span>{changed.has(s.id) ? <Tag kind="warn">Changed</Tag> : null}{m ? <span className="muted">· {m.name} v{m.version}</span> : null}</div>
                <div className={cn('thumbnail fbox relative overflow-hidden rounded-md border bg-white', sel && 'ring-2 ring-foreground ring-offset-1')} style={{ aspectRatio: `${frameOf(b).w}/${frameOf(b).h}` }}><Thumb src={img(vv, s.id)} alt={`${s.title} screen generated by ${vv.runner_name}`} className="size-full object-cover object-top" />{hasPhoneView(b) && <img src={img(vv, s.id, 'm')} alt="" loading="lazy" className="phone-thumb absolute bottom-1.5 right-1.5 w-[24%] rounded-md border-2 border-background bg-white shadow-md" onError={(e) => { (e.target as HTMLElement).style.display = 'none'; }} />}</div>
                <div className="fsize mt-1 text-[11px] text-muted-foreground/70">{frameOf(b).w} × {frameOf(b).h}{hasPhoneView(b) ? ' · phone view inset' : ''}</div>
              </div>
              {flow && <span className="flow grid w-11 shrink-0 place-items-center text-muted-foreground/60" style={{ height: Math.round((cardWidth(b) * frameOf(b).h) / frameOf(b).w) + 26 }} aria-hidden="true" title={edges.find((e: any) => e.from === s.id)?.trigger || ''}><Ic name="forward" size={16} /></span>}
            </div>
          );
        })}
      </div>
      <div className="variant-foot flex flex-wrap justify-between gap-2 border-t bg-muted/30 px-4 py-2.5 text-xs text-muted-foreground"><span><span className={cn('mr-1 inline-block size-1.5 rounded-full', failed ? 'bg-warning' : 'bg-success')} /> {passed} passed · {failed} failed · {pending ? `${pending} need designer review` : 'designer review complete'}</span><span className="flex items-center gap-1.5"><ProfileTag v={vv} b={b} />Context <span className="font-mono">{fmtHash(data.context.find((c) => c.id === vv.context_id)?.hash)}</span></span></div>
    </section>
  );
}

/* ---------- compare ---------- */
function CompareView({ b, vs }: { b: any; vs: any[] }) {
  const { r } = useCurrent(); const screen = useUi((s) => s.screen); const q = r.q; const usable = vs.filter((x) => x.review_state !== 'reverted');
  if (!vs.length) return <div className="canvas p-6"><Empty title="Nothing to compare yet" text="Generate at least two variations first." /></div>;
  const right = vs.find((x) => x.id === q.get('right')) || usable.at(-1) || vs.at(-1);
  const left = vs.find((x) => x.id === q.get('left')) || (right.parent_id && vs.find((x) => x.id === right.parent_id)) || vs.filter((x) => x.id !== right.id && x.parent_id !== right.id).at(-1) || vs.find((x) => x.id !== right.id) || right;
  const setSide = (side: string, id: string) => { const nq = new URLSearchParams(location.search); nq.set(side, id); navigate(location.pathname + '?' + nq, { replace: true, keepView: true }); };
  const twin = twinLink(right); const gotoTwin = () => { const nq = new URLSearchParams(location.search); if (twin) { nq.set('left', twin.left); nq.set('right', twin.right); navigate(location.pathname + '?' + nq, { replace: true, keepView: true }); } };
  const Col = ({ x, side }: { x: any; side: string }) => {
    const checks = checksOf(x); const fail = checks.filter((c: any) => c.outcome === 'fail').length; const pass = checks.filter((c: any) => c.outcome === 'pass').length; const rev = unresolvedReviews(x).length; const changed = (x.changed_screens || []).includes(screen);
    return (
      <div className="compare-col min-w-0">
        <label className="sr-only" htmlFor={`cmp-${side}`}>{side} variation</label>
        <select id={`cmp-${side}`} data-compare-side={side} value={x.id} onChange={(e) => setSide(side, e.target.value)} className={nativeSelect}>{vs.map((o) => <option key={o.id} value={o.id}>{o.runner_name} · v{o.version} · {variantStatus(o)[0]}</option>)}</select>
        <div className="my-2.5 flex flex-wrap gap-1.5"><Tag kind={variantStatus(x)[1]}>{variantStatus(x)[0]}</Tag><ProfileTag v={x} b={b} /><CutOff v={x} />{freeOf(x) ? <Tag kind="warn">Free · {freeOf(x) === 'open' ? 'fully open' : 'rules off'}</Tag> : null}{x.rule_breaks ? <Tag kind={x.rule_breaks.results.some((c: any) => c.outcome === 'fail') ? 'fail' : ''}>{x.rule_breaks.results.filter((c: any) => c.outcome === 'fail').length} rule breaks</Tag> : null}{changed ? <Tag kind="warn">Changed in this screen</Tag> : null}<Tag kind={fail ? 'fail' : ''}>{pass} pass · {fail} fail · {rev} review</Tag></div>
        <div className="overflow-hidden rounded-lg border bg-white"><Thumb src={img(x, screen)} alt={`${b.screens[Number(screen)]} · ${x.runner_name} v${x.version}`} className="w-full" /></div>
        <div className="filmstrip my-2.5 flex gap-2 overflow-x-auto" role="group" aria-label={`Screens of ${x.runner_name}`}>{x.manifest.screens.map((s: any) => <button key={s.id} className={cn('film h-16 w-12 shrink-0 overflow-hidden rounded-md border p-0', s.id === screen && 'on ring-2 ring-foreground')} data-screen={s.id} aria-label={s.title} onClick={() => ui.set({ screen: s.id })}><img src={img(x, s.id)} alt="" loading="lazy" className="size-full object-cover object-top" /></button>)}</div>
        {x.changes.map((c: string, i: number) => <p key={i} className="my-1 text-xs">{c}</p>)}
        <Button variant="outline" size="sm" render={<Link href={boardPath(r, b, 'review', x.id)} />}>Open in review</Button>
      </div>
    );
  };
  return (
    <div className="canvas bg-muted/30 px-4 py-4 lg:px-7">
      <div className="mb-5 flex flex-wrap items-center gap-2" role="group" aria-label="Screen">{b.screens.map((s: string, i: number) => <Button key={i} size="sm" variant={screen === String(i) ? 'default' : 'outline'} data-screen={i} aria-pressed={screen === String(i)} onClick={() => ui.set({ screen: String(i) })}>{s}{left.changed_screens?.includes(String(i)) || right.changed_screens?.includes(String(i)) ? ' •' : ''}</Button>)}<span className="text-xs text-muted-foreground">• changed in a revision</span></div>
      {twin && left.id !== twin.twin.id && <div className="mb-4"><Button size="sm" variant="outline" data-action="compare-twin" onClick={gotoTwin}><Ic name="columns" size={13} /> Compare rules vs free for {right.runner_name}</Button></div>}
      {left.id === right.id && <Note>Choose two different versions to compare, for example a parent and its revision.</Note>}
      <div className="compare-grid grid gap-5 md:grid-cols-2"><Col x={left} side="left" /><Col x={right} side="right" /></div>
    </div>
  );
}

/* ---------- review ---------- */
function RegionOverlay({ shown, screen, ids, fr }: { shown: any; screen: string; ids: string[]; fr: { w: number; h: number } }) {
  const [rects, setRects] = useState<Record<string, any> | null>(null);
  useEffect(() => { let live = true; elementRects(shown, screen, fr).then((x) => { if (live) setRects(x); }); return () => { live = false; }; }, [shown.id, screen, fr.w, fr.h]);
  return <div className="regions pointer-events-none absolute inset-0" data-region-ids={ids.join(',')} data-region-variant={shown.id} data-region-screen={screen}>{rects && ids.filter((id) => rects[id] && rects[id].y < 1).map((id) => { const x = rects[id]; return <div key={id} className="region absolute border-2 border-dashed border-destructive bg-destructive/10" style={{ left: `${x.x * 100}%`, top: `${x.y * 100}%`, width: `${x.w * 100}%`, height: `${Math.min(x.h, 1 - x.y) * 100}%` }}><span className="absolute -top-5 left-0 rounded-t bg-destructive px-1.5 text-[10px] text-white">{id}</span></div>; })}</div>;
}
function ReviewView({ b, vs, v }: { b: any; vs: any[]; v: any }) {
  const { r } = useCurrent(); const data = useData(); const s = useUi((x) => x);
  if (!v) return <div className="canvas p-6"><Empty title="Nothing to review" text="Generate variations first." /></div>;
  const parent = data.variant.find((x) => x.id === v.parent_id); const showBefore = s.showBefore && parent; const shown = showBefore ? parent : v; const commenting = s.tool === 'comment' && !showBefore; const editing = s.tool === 'edit' && !showBefore;
  const view = hasPhoneView(b) ? s.reviewView : 'd'; const fr = frameOf(b, view);
  const pins = data.annotation.filter((a) => a.variant_id === v.id && a.screen === s.screen && (a.view || 'd') === view); const changed = v.changed_screens || []; const open = pins.find((a) => a.id === s.activePin);
  const num = (a: any) => data.annotation.filter((x) => x.variant_id === v.id).findIndex((x) => x.id === a.id) + 1;
  const regions = (v.changed_regions || {})[s.screen];
  const onArea = (e: React.MouseEvent<HTMLDivElement>) => {
    if ((e.target as HTMLElement).closest('.pop,.pin')) return;
    if (s.tool !== 'comment' && !showBefore) { if (s.activePin) ui.set({ activePin: '' }); return; }
    if (showBefore) return; const rect = e.currentTarget.getBoundingClientRect();
    pinModal(Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width)), Math.min(1, Math.max(0, (e.clientY - rect.top) / rect.height)), view);
  };
  return (
    <div className="canvas review-canvas bg-muted/30 px-4 py-4 lg:px-7">
      <div className="mb-3.5 flex flex-wrap items-center gap-2">
        <label className="sr-only" htmlFor="review-variant">Variation</label>
        <select id="review-variant" data-review-variant value={v.id} onChange={(e) => navigate(boardPath(r, b, 'review', e.target.value), { keepView: true })} className={cn(nativeSelect, 'w-auto max-w-full')}>{vs.map((x) => <option key={x.id} value={x.id}>{x.runner_name} · v{x.version} · {variantStatus(x)[0]}</option>)}</select>
        {hasPhoneView(b) && <SegmentedControl role="group" aria-label="Review at"><SegmentedControlItem data-review-view="d" aria-current={view === 'd' ? 'page' : undefined} onClick={() => ui.set({ reviewView: 'd' })}><Ic name="monitor" size={13} /> Desktop</SegmentedControlItem><SegmentedControlItem data-review-view="m" aria-current={view === 'm' ? 'page' : undefined} onClick={() => ui.set({ reviewView: 'm' })}><Ic name="phone" size={13} /> Phone</SegmentedControlItem></SegmentedControl>}
        <Button size="sm" variant="outline" data-open-live={v.id} data-screen-id={s.screen} onClick={() => openLive(v, s.screen)}><Ic name="eye" size={13} /> Live preview</Button>
        {parent && <><SegmentedControl role="group" aria-label="Before and after"><SegmentedControlItem data-action="show-after" aria-current={showBefore ? undefined : 'page'} onClick={() => ui.set({ showBefore: false })}>After (v{v.version})</SegmentedControlItem><SegmentedControlItem data-action="show-before" aria-current={showBefore ? 'page' : undefined} onClick={() => ui.set({ showBefore: true })}>Before (v{parent.version})</SegmentedControlItem></SegmentedControl>
          <Button size="sm" variant="outline" render={<Link href={`${boardPath(r, b, 'compare')}?left=${parent.id}&right=${v.id}`} />}><Ic name="columns" size={13} /> Side by side</Button></>}
        {regions && <><label className="flex items-center gap-1.5 text-xs font-normal"><input type="checkbox" data-show-regions checked={s.showRegions} onChange={(e) => ui.set({ showRegions: e.target.checked })} /> Show changed regions</label>{regions.outside ? <Tag kind="fail">Changes outside identified elements</Tag> : null}</>}
        <span className="grow text-xs text-muted-foreground">{v.approved ? 'Approved and locked: feedback starts a new revision.' : editing ? 'Edit tool: click an element, change it in the panel, then save as a new version.' : commenting ? 'Comment tool: click the screen to drop a pin.' : showBefore ? 'Before view is read-only.' : 'Move tool: select pins. Press C to comment.'}</span>
      </div>
      <div className="reviewstage flex items-start gap-4 max-md:flex-col max-md:items-stretch">
        <div className="filmcol flex gap-2 md:w-24 md:flex-col" role="group" aria-label="Screens">{v.manifest.screens.map((sc: any) => <button key={sc.id} className={cn('film flex w-24 shrink-0 flex-col gap-1 rounded-lg border bg-background p-1.5 text-xs', sc.id === s.screen && 'on ring-2 ring-foreground')} data-screen={sc.id} aria-label={sc.title} onClick={() => ui.set({ screen: sc.id })}><img src={img(shown, sc.id)} alt="" loading="lazy" className="aspect-[3/4] w-full rounded object-cover object-top" /><span>{sc.title}{changed.includes(sc.id) ? ' •' : ''}</span></button>)}</div>
        <div className="reviewframe min-w-0 flex-1 overflow-auto">
          <div className="fname mb-1.5 text-xs"><span>{b.screens[Number(s.screen)]}</span> <span className="muted text-muted-foreground">· {shown.runner_name} v{shown.version}</span></div>
          <div className={cn('review-area relative mx-auto max-w-full select-none', commenting ? 'commenting cursor-crosshair' : '')} id="pin-area" role="button" tabIndex={0} aria-label="Screen preview. Press Enter to add a feedback pin." style={{ width: Math.round((reviewBase(b, view) * s.zoom) / 100) }}
            onClick={onArea} onKeyDown={(e) => { if ((e.key === 'Enter' || e.key === ' ') && e.target === e.currentTarget) { e.preventDefault(); if (!showBefore) pinModal(0.5, 0.5, view); } }}>
            {editing ? <EditCanvas v={shown} screen={s.screen} fr={fr} width={Math.round((reviewBase(b, view) * s.zoom) / 100)} /> : (
  <Thumb src={img(shown, s.screen, view)} alt={`${b.screens[Number(s.screen)]} · ${shown.runner_name} v${shown.version}${view === 'm' ? ' · phone view' : ''}`} className="block w-full rounded border bg-white" />
            )}
            {!editing && regions && s.showRegions && <RegionOverlay shown={shown} screen={s.screen} ids={regions.elements || []} fr={fr} />}
            {!showBefore && !editing && pins.map((a) => <span key={a.id} className={cn('pin absolute grid size-6 -translate-x-1/2 -translate-y-1/2 cursor-pointer place-items-center rounded-full border-2 border-background bg-foreground text-[11px] text-background shadow-md', a.status === 'applied' && 'applied bg-muted-foreground', s.activePin === a.id && 'focus ring-2 ring-ring')} data-pin={a.id} role="button" tabIndex={0} aria-label={`Comment ${num(a)}`} title={a.comment} style={{ left: `${a.x * 100}%`, top: `${a.y * 100}%` }} onClick={(e) => { e.stopPropagation(); ui.set({ activePin: a.id }); }}><b>{num(a)}</b></span>)}
            {!showBefore && open && (
              <div className="pop absolute z-20 w-60 rounded-xl border bg-popover p-3 text-popover-foreground shadow-lg" role="dialog" aria-label={`Comment ${num(open)}`} onClick={(e) => e.stopPropagation()} style={{ left: `${Math.min(open.x * 100, 62)}%`, ...(open.y > 0.55 ? { bottom: `calc(${(1 - open.y) * 100}% + 36px)` } : { top: `calc(${open.y * 100}% + 18px)` }) }}>
                <div className="flex items-center justify-between"><strong className="text-sm">Comment {num(open)}</strong><span className="flex gap-0.5">{open.status !== 'applied' && <><Button variant="ghost" size="icon-xs" data-pin-edit={open.id} aria-label="Edit comment" onClick={() => pinEdit(open.id)}><Ic name="edit" size={13} /></Button><Button variant="ghost" size="icon-xs" data-pin-delete={open.id} aria-label="Delete comment" onClick={() => pinDelete(open.id)}><Ic name="trash" size={13} /></Button></>}<Button variant="ghost" size="icon-xs" data-pin-close aria-label="Close" onClick={() => ui.set({ activePin: '' })}><Ic name="x" size={13} /></Button></span></div>
                <p className="my-1.5 text-[13px]">{open.comment}</p><span className="text-xs text-muted-foreground">{open.element_id ? `Anchored to “${open.element_id}”` : 'Coordinates only'}{open.status === 'applied' ? ' · applied in a revision' : ''}</span>
              </div>
            )}
          </div>
        </div>
      </div>
      <FloatBar mode="review" />
    </div>
  );
}
export { Inspector };
void live;
