import { useMemo, type ReactNode } from 'react';
import { Link, navigate, useCurrent, useRoute, nav, boardPath, projectBase } from '@/lib/router';
import { useData, useUi, ui, contextsOf, referencesOf, variantsOf, roundsOf, prototypeOf, activeJob, isDirty, ctxVersion } from '@/lib/store';
import { fmtHash } from '@/lib/format';
import { Button } from '@/components/ui/button';
import { SegmentedControl, SegmentedControlItem } from '@/components/ui/segmented-control';
import { Ic, type IconName } from './icons';
import { Tag } from './feedback';
import { cn } from '@/lib/utils';
import { runAction } from '@/actions';

const RAIL: [string, string, IconName][] = [['projects', 'Projects', 'projects'], ['boards', 'Boards', 'boards'], ['research', 'Research', 'research'], ['context', 'Guidelines', 'context'], ['history', 'History', 'history'], ['settings', 'Agent settings', 'settings']];

export function TopBar() {
  const { r, p, b, v } = useCurrent(); const data = useData(); const tool = useUi((s) => s.tool);
  const home = r.view === 'projects'; const running = data.job.filter(activeJob).length; const proto = prototypeOf(v);
  const live = data.project.filter((x) => !x.archived);
  const review = r.view === 'boards' && r.mode === 'review';
  return (
    <header className="top flex min-h-12 shrink-0 items-center justify-between gap-3 overflow-x-auto border-b bg-background px-3 lg:px-4">
      <div className="flex shrink-0 items-center gap-2.5">
        <Link href="/projects" aria-label="All projects" className="grid size-8 place-items-center rounded-lg border bg-muted/60"><Ic name="boards" size={15} /></Link>
        <nav className="crumbs flex items-center gap-2 text-sm text-muted-foreground max-md:hidden" aria-label="Breadcrumb">
          <Link href="/projects" className="hover:text-foreground">Design Studio</Link>
          {!home && p && <>
            <span className="sep opacity-50">/</span><Link href={`${projectBase(r)}/boards`} className="hover:text-foreground">{p.name}</Link>
            {live.length > 1 && <span className="relative grid size-6 place-items-center rounded-md text-muted-foreground hover:bg-accent hover:text-foreground"><Ic name="chevron" size={13} className="rotate-90" /><select data-switch-project aria-label="Switch project" title="Switch project" value={p.id} onChange={(e) => navigate(`/projects/${e.target.value}/boards`)} className="crumb-select absolute inset-0 cursor-pointer opacity-0">{live.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</select></span>}
            {b && r.boardId && <><span className="sep opacity-50">/</span><span className="crumb-cur font-semibold text-foreground">{b.title}</span></>}
          </>}
        </nav>
      </div>
      {review && (
        <SegmentedControl role="group" aria-label="Tool" className="toolseg shrink-0">
          <SegmentedControlItem data-tool="move" aria-pressed={tool === 'move'} aria-current={tool === 'move' ? 'page' : undefined} title="Move (V)" aria-label="Move tool" onClick={() => ui.set({ tool: 'move' })}><Ic name="cursor" size={14} /></SegmentedControlItem>
          <SegmentedControlItem data-tool="comment" aria-pressed={tool === 'comment'} aria-current={tool === 'comment' ? 'page' : undefined} title="Comment (C)" aria-label="Comment tool" onClick={() => ui.set({ tool: 'comment' })}><Ic name="comment" size={14} /></SegmentedControlItem>
        </SegmentedControl>
      )}
      <div className="flex shrink-0 items-center gap-2">
        {!home && p && <>
          <Link href={nav(r, 'context')} className="toplink px-2 text-sm text-muted-foreground hover:text-foreground">Guidelines</Link>
          <Link href={nav(r, 'history')} className="toplink flex items-center gap-1.5 px-2 text-sm text-muted-foreground hover:text-foreground">Jobs{running ? <span className="progress size-1.5 animate-pulse rounded-full bg-foreground/60" title={`${running} running`} /> : null}</Link>
          <Button variant="outline" size="sm" data-action="generate" disabled={!b} onClick={() => runAction('generate')}><Ic name="spark" size={14} /> Generate variants</Button>
        </>}
        <span className="avatar grid size-7 place-items-center rounded-full bg-foreground text-[11px] font-semibold text-background" aria-hidden="true">You</span>
        {!home && p && <Button size="sm" className="primary" data-action="preview" title={proto ? undefined : 'Approve a variation to build a prototype'} onClick={() => runAction('preview')}><Ic name="play" size={14} /> Preview prototype</Button>}
      </div>
    </header>
  );
}

export function Rail() {
  const r = useRoute();
  return (
    <nav className="rail fixed inset-x-0 bottom-0 z-40 flex h-14 items-center justify-around border-t bg-background px-1.5 lg:static lg:h-auto lg:flex-col lg:justify-start lg:gap-3.5 lg:border-r lg:border-t-0 lg:py-4" aria-label="Main navigation">
      {RAIL.map(([k, label, icon]) => {
        const href = k === 'projects' ? '/projects' : k === 'settings' ? '/settings/agents' : nav(r, k);
        const on = r.view === k; const bottom = k === 'settings';
        return <Link key={k} href={href} title={label} aria-label={label} aria-current={on ? 'page' : 'false'} className={cn('grid size-10 place-items-center rounded-lg text-muted-foreground transition-colors hover:bg-accent hover:text-foreground', on && 'active bg-accent text-foreground', bottom && 'bottom lg:mt-auto')}><Ic name={icon} size={18} /></Link>;
      })}
    </nav>
  );
}

const lrow = 'lrow flex w-full items-center gap-2.5 rounded-lg px-2.5 py-1.5 text-left text-[13px] text-muted-foreground hover:bg-accent hover:text-foreground';
export function ProjectPanel() {
  const { r, p, b, boards, ctx, v } = useCurrent(); const data = useData(); const roundState = useUi((s) => s.roundState); const showReverted = useUi((s) => s.showReverted);
  useUi((s) => s.draftFor); const sel = v;
  const refs = referencesOf(p?.id); const versions = contextsOf(p?.id); const dirty = isDirty(ctx);
  const vs = variantsOf(b).filter((x) => showReverted || x.review_state !== 'reverted' || x.id === sel?.id);
  const R = useMemo(() => (b ? roundsOf(b) : { rounds: [], of: {} as Record<string, any> }), [b, data.variant, data.job]);
  const row = (href: string, icon: IconName, label: string, extra: ReactNode = null, on = false) => <Link key={label} href={href} className={cn(lrow, on && 'on bg-accent text-foreground font-medium')}><Ic name={icon} size={14} /><span className="lname flex-1 truncate">{label}</span>{extra}</Link>;
  const layerRow = (x: any) => (
    <div key={x.id} className="lgroup">
      <button className={cn(lrow, x.id === sel?.id && 'on-soft bg-accent text-foreground')} data-layer-variant={x.id} onClick={() => layerClick(r, b, x.id)} title={`${R.of[x.id]?.label || ''} · ${x.runner_name} v${x.version}`}>
        <Ic name="layers" size={14} /><span className="lname flex-1 truncate">{R.rounds.length > 1 && R.of[x.id] ? <span className="rtag mr-1 rounded bg-foreground/8 px-1 text-[10px] font-semibold">R{R.of[x.id].n}</span> : null}{x.runner_name} · v{x.version}</span>
        <span className={cn('size-1.5 rounded-full', x.approved ? 'bg-success' : x.review_state === 'pending' ? 'bg-warning' : 'bg-muted-foreground/40')} />
      </button>
      {x.id === sel?.id && x.manifest.screens.map((s: any) => <button key={s.id} className={cn(lrow, 'child ml-4 w-[calc(100%-1rem)]', ui.get().screen === s.id && 'on bg-accent text-foreground')} data-layer-variant={x.id} data-layer-screen={s.id} onClick={() => layerClick(r, b, x.id, s.id)}><Ic name="frame" size={13} /><span className="lname truncate">{s.title}</span></button>)}
    </div>
  );
  return (
    <aside className="project-panel hidden overflow-auto border-r bg-muted/30 px-3 py-4 lg:block">
      <div className="mb-3 flex items-center justify-between px-1"><strong className="truncate text-sm">{p?.name}</strong><Button variant="ghost" size="icon-sm" data-action="project-menu" aria-label="Project settings" onClick={() => runAction('project-menu')}><Ic name="dots" /></Button></div>
      <Section label="Design context">
        {row(nav(r, 'context'), 'context', 'Guidelines', <Tag>MD</Tag>, r.view === 'context')}
        {row(nav(r, 'context') + '#tokens', 'tokens', 'Tokens', <span className="count text-xs text-muted-foreground">{Object.keys(ctx?.tokens || {}).length}</span>)}
        {row(nav(r, 'context') + '#rules', 'rules', 'Rules', <span className="count text-xs text-muted-foreground">{ctx?.rules.length || 0}</span>)}
        {row(nav(r, 'references'), 'image', 'References', <span className="count text-xs text-muted-foreground">{refs.length}</span>, r.view === 'references')}
        {row(nav(r, 'research'), 'research', 'Research', <span className="count text-xs text-muted-foreground">{data.research.filter((x) => x.project_id === p?.id).length}</span>, r.view === 'research')}
      </Section>
      <Section label="Pages" action={<Button variant="ghost" size="icon-xs" data-action="new-board" aria-label="New board" onClick={() => runAction('new-board')}><Ic name="plus" size={13} /></Button>}>
        {row(nav(r, 'boards'), 'boards', 'All boards', null, r.view === 'boards' && !r.boardId)}
        {boards.map((x) => <Link key={x.id} href={boardPath(r, x)} className={cn(lrow, 'child ml-3 w-[calc(100%-0.75rem)]', x.id === b?.id && r.boardId && 'on bg-accent text-foreground font-medium')}><Ic name="file" size={13} /><span className="lname flex-1 truncate">{x.title}</span><span className="count text-xs text-muted-foreground">{x.screens.length}</span></Link>)}
      </Section>
      {r.view === 'boards' && r.boardId && b && (
        <Section label="Layers">
          {!vs.length ? <p className="px-2.5 text-xs text-muted-foreground">No variations yet.</p> : R.rounds.length < 2 ? vs.map(layerRow) : R.rounds.slice().reverse().map((rd: any, i: number) => {
            const items = vs.filter((x) => R.of[x.id] === rd); if (!items.length) return null; const key = `L:${b.id}:${rd.n}`;
            const open = roundState[key] ?? (i === 0 || items.some((x) => x.id === sel?.id));
            return <details key={key} className="lround" open={open} data-round={key} onToggle={(e) => { const o = e.currentTarget.open; if (o !== open) ui.set((s) => ({ roundState: { ...s.roundState, [key]: o } })); }}><summary className="flex cursor-pointer list-none items-center gap-2 px-2.5 py-1.5 text-xs font-semibold text-muted-foreground">{rd.label}<span className="count ml-auto font-normal">{items.length}</span></summary>{items.map(layerRow)}</details>;
          })}
        </Section>
      )}
      <details className="psec mt-3 px-1"><summary className="cursor-pointer text-xs font-semibold uppercase tracking-wide text-muted-foreground">Active rules ({ctx?.effective_rules.length || 0})</summary>{(ctx?.effective_rules || []).map((x: any) => <div key={x.id} className="mini-rule mt-2 flex gap-2 text-xs"><span className={cn('mt-1 size-1.5 shrink-0 rounded-full', x.verification === 'deterministic' ? 'bg-success' : 'bg-warning')} /><span>{x.id} <span className="text-muted-foreground">v{x.version || 1}</span><div className="mt-0.5 text-muted-foreground">{x.description}</div></span></div>)}</details>
      <div className="context-footer mt-4 rounded-lg border bg-background px-3 py-2.5 text-xs text-muted-foreground"><span className={cn('mr-1 inline-block size-1.5 rounded-full', dirty ? 'bg-warning' : 'bg-success')} />{dirty ? 'Unsaved guideline edits' : 'Context saved'} · v{ctx?.version || versions.length} · <span className="font-mono">{fmtHash(ctx?.hash)}</span></div>
    </aside>
  );
}
function layerClick(r: any, b: any, id: string, screen?: string) {
  ui.set({ selectedVariant: id, ...(screen !== undefined ? { screen } : {}), activePin: '', showBefore: false });
  if (r.mode === 'review') navigate(boardPath(r, b, 'review', id), { keepView: true });
  else { navigate(boardPath(r, b), { keepView: true }); ui.set({ scrollTo: `frame-${id}-${ui.get().screen}` }); }
}
function Section({ label, action, children }: { label: string; action?: ReactNode; children: ReactNode }) {
  return <div className="psec mb-3"><div className="psec-head mb-1 flex items-center justify-between px-2.5 text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">{label}{action}</div>{children}</div>;
}

export function ActivityStrip() {
  const { p, r } = useCurrent(); const data = useData();
  const jobs = data.job.filter((j) => j.project_id === p?.id); const running = jobs.filter(activeJob).length;
  const failed = jobs.filter((j) => ['failed', 'timed_out'].includes(j.status) && !j.retried_by && !j.dismissed).length; const last = jobs.at(-1)?.events.at(-1)?.message;
  return (
    <footer className="activity hidden h-8 shrink-0 items-center justify-between border-t bg-background px-4 text-xs text-muted-foreground lg:flex">
      <span className="flex min-w-0 items-center gap-2"><span className="flex items-center gap-1.5"><Ic name="history" size={13} /> Activity</span><span className="opacity-40">│</span><span className={cn('size-1.5 rounded-full', running ? 'bg-foreground/60' : failed ? 'bg-warning' : 'bg-success')} /><span>{running ? `${running} running` : 'Idle'}{failed ? ` · ${failed} need attention` : ''}</span><span className="opacity-40">│</span><span className="truncate">{last || 'Ready. Your design context comes first.'}</span></span>
      <Link href={nav(r, 'history')} className="hover:text-foreground">Open log</Link>
    </footer>
  );
}

export function Heading({ title, sub, tabs, right }: { title: string; sub: string; tabs?: ReactNode; right?: ReactNode }) {
  return (
    <div className="workspace-head border-b bg-background px-4 pt-5 lg:px-7">
      <div className="flex flex-wrap items-center justify-between gap-3"><h1 className="text-lg font-semibold tracking-tight">{title}</h1><span className="flex items-center gap-2">{right}</span></div>
      <p className="mb-4 mt-1 text-[13px] text-muted-foreground">{sub}</p>{tabs}
    </div>
  );
}
void ctxVersion;
