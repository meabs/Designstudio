import { useEffect, useRef } from 'react';
import { Link, navigate, useCurrent, nav, boardPath } from '@/lib/router';
import { useData, useUi, ui, protoLive } from '@/lib/store';
import { SegmentedControl, SegmentedControlItem } from '@/components/ui/segmented-control';
import { Button } from '@/components/ui/button';
import { Ic } from '@/components/app/icons';
import { Tag, Empty } from '@/components/app/feedback';
import { shareModal } from '@/actions';
import { cn } from '@/lib/utils';

export function PlayerPage() {
  const { r, p, b } = useCurrent(); const data = useData(); const device = useUi((s) => s.device); const playerFile = useUi((s) => s.playerFile);
  const proto = data.prototype.find((x) => x.id === r.prototypeId); const frame = useRef<HTMLIFrameElement>(null);
  useEffect(() => { ui.set({ device: b?.target === 'mobile' ? 'mobile' : 'desktop' }); }, [r.prototypeId, b?.id]);
  useEffect(() => {
    ui.set({ playerFile: '' });
    const onMsg = (e: MessageEvent) => { if (!frame.current || e.source !== frame.current.contentWindow || e.data?.type !== 'screen') return; ui.set({ playerFile: String(e.data.file || '').replace(/[^\w.\-]/g, '') }); };
    window.addEventListener('message', onMsg); return () => window.removeEventListener('message', onMsg);
  }, [r.prototypeId]);
  if (!proto) return <div className="p-8"><Empty title="Prototype not found" text="Approve a variation to build a prototype."><Button render={<Link href={nav(r, 'boards')} />} variant="outline">Back to boards</Button></Empty></div>;
  const start = proto.screens.find((s: any) => s.id === proto.start_screen_id) || proto.screens[0]; const board = data.board.find((x) => x.id === proto.board_id);
  const file = playerFile || start.file.split('/').pop(); const i = Math.max(0, proto.screens.findIndex((s: any) => s.file.split('/').pop() === file)); const cur = proto.screens[i] || proto.screens[0];
  const post = (m: any) => frame.current?.contentWindow?.postMessage(m, '*');
  const seg = 'text-xs';
  return (
    <div className="flex h-dvh flex-col bg-muted/40">
      <header className="top flex min-h-12 shrink-0 flex-wrap items-center justify-between gap-2 border-b bg-background px-3 py-1.5 lg:px-4">
        <div className="flex items-center gap-3"><Link href="/projects" className="logo flex items-center gap-2.5 text-sm font-semibold"><span className="grid size-8 place-items-center rounded-lg border bg-muted/60"><Ic name="boards" size={15} /></span><span className="max-md:hidden">Design Studio</span></Link><span className="sep opacity-40 max-md:hidden">/</span><Link className="crumb text-sm text-muted-foreground max-md:hidden" href={`/projects/${p?.id}/boards`}>{p?.name}</Link><Tag>PROTOTYPE</Tag></div>
        <div className="flex flex-wrap items-center gap-2">
          <Button variant="outline" size="sm" data-player="back" aria-label="Back" onClick={() => post({ cmd: 'back' })}><Ic name="back" size={14} /> Back</Button>
          <Button variant="outline" size="sm" data-player="forward" aria-label="Forward" onClick={() => post({ cmd: 'forward' })}>Forward <Ic name="forward" size={14} /></Button>
          <Button variant="outline" size="sm" data-action="restart" onClick={() => { if (frame.current) frame.current.src = protoLive(proto, proto.start_screen_id); }}><Ic name="refresh" size={14} /> Restart</Button>
          <SegmentedControl role="group" aria-label="Mock state">{['default', 'help', 'error'].map((n) => <SegmentedControlItem key={n} className={seg} data-player-state={n} onClick={() => post({ cmd: 'state', name: n })}>{n[0].toUpperCase() + n.slice(1)}</SegmentedControlItem>)}</SegmentedControl>
          <SegmentedControl role="group" aria-label="Device"><SegmentedControlItem className={seg} data-device="desktop" aria-pressed={device === 'desktop'} aria-current={device === 'desktop' ? 'page' : undefined} onClick={() => ui.set({ device: 'desktop' })}><Ic name="monitor" size={13} /> 1440</SegmentedControlItem><SegmentedControlItem className={seg} data-device="mobile" aria-pressed={device === 'mobile'} aria-current={device === 'mobile' ? 'page' : undefined} onClick={() => ui.set({ device: 'mobile' })}><Ic name="phone" size={13} /> 390</SegmentedControlItem></SegmentedControl>
          <Button variant="outline" size="sm" render={<a target="_blank" rel="noopener" href={protoLive(proto, start.id)} />}><Ic name="external" size={13} /> New tab</Button>
          <Button variant="outline" size="sm" data-action="share" onClick={shareModal}><Ic name="link" size={13} /> Share</Button>
          <Button variant="outline" size="sm" render={<a href={`/api/export/${proto.id}`} />}><Ic name="download" size={13} /> Export ZIP</Button>
          <Button variant="ghost" size="sm" data-action="exit-player" onClick={() => navigate(board ? boardPath(r, board) : nav(r, 'boards'))}>Close</Button>
        </div>
      </header>
      <div className="player-info flex shrink-0 flex-wrap gap-x-7 gap-y-1 border-b bg-background px-4 py-2 text-xs text-muted-foreground" id="player-info" role="status" aria-live="polite">
        <span><strong className="text-foreground">{cur.title}</strong> · screen {i + 1} of {proto.screens.length}</span><span>{proto.board_title} · <strong>v{proto.version}</strong> · {proto.runner_name} · build {proto.id.slice(0, 6)}</span><span>{device === 'desktop' ? 'Desktop · 1440px' : 'Mobile · 390px'}</span>
      </div>
      <div className="player flex min-h-0 flex-1 items-start justify-center overflow-auto p-4 lg:p-6">
        <div className={cn('device h-full min-h-[480px] bg-white', device === 'desktop' ? 'desktop w-[1440px] max-w-full rounded-lg border shadow-sm' : 'mobile max-h-[844px] w-[390px] max-w-full overflow-hidden rounded-[34px] border-[10px] border-neutral-800 bg-neutral-800')}>
          <iframe ref={frame} id="player" title={`Approved click-through prototype: ${board?.title || ''}`} sandbox="allow-scripts allow-forms" src={protoLive(proto, start.id)} className="block size-full border-0 bg-white" />
        </div>
      </div>
    </div>
  );
}
