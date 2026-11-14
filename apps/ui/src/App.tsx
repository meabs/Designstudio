import { useEffect } from 'react';
import { boot, refresh, dataStore, useSel, useData } from '@/lib/store';
import { navigate, useRoute, parseRoute } from '@/lib/router';
import { useInterval } from '@/components/app/feedback';
import { Toaster, DialogHost, Empty } from '@/components/app/feedback';
import { TopBar, Rail, ProjectPanel, ActivityStrip } from '@/components/app/chrome';
import { TooltipProvider } from '@/components/ui/tooltip';
import { Button } from '@/components/ui/button';
import { BoardView } from '@/views/board';
import { Inspector } from '@/views/inspector';
import { ProjectsView, BoardsList, ReferencesView, HistoryView, SettingsView } from '@/views/pages';
import { ContextView } from '@/views/context';
import { ResearchView } from '@/views/research';
import { PlayerPage } from '@/views/player';
import { runAction } from '@/actions';
import { cn } from '@/lib/utils';

export default function App() {
  const ready = useSel(dataStore, (s) => s.ready); const r = useRoute(); const data = useData();
  useEffect(() => { boot().catch(() => {}); }, []);
  useInterval(() => { refresh().catch(() => {}); }, 1800, ready);
  useEffect(() => {
    if (!ready || location.pathname !== '/') return; const p = data.project.find((x) => !x.archived); const b = data.board.find((x) => x.project_id === p?.id);
    navigate(p ? `/projects/${p.id}/boards${b ? '/' + b.id : ''}` : '/projects', { replace: true });
  }, [ready]);
  useEffect(() => { document.title = 'Design Studio'; }, []);
  if (!ready) return <div className="grid min-h-dvh place-items-center text-sm text-muted-foreground">Loading…</div>;
  const view = r.view; const home = view === 'projects';
  const wide = ['projects', 'settings', 'context', 'history', 'research', 'references'].includes(view) || (view === 'boards' && !r.boardId);
  let main;
  if (!r.project && view !== 'projects' && view !== 'settings') main = <div className="p-8"><Empty title="Start with a project" text="Everything — guidance, research, boards — lives inside a project."><Button className="primary" data-action="new-project" onClick={() => runAction('new-project')}>New project</Button></Empty></div>;
  else main = ({ projects: <ProjectsView />, context: <ContextView />, references: <ReferencesView />, research: <ResearchView />, history: <HistoryView />, settings: <SettingsView /> } as any)[view] || (r.boardId ? <BoardView /> : <BoardsList />);
  return (
    <TooltipProvider>
      {view === 'prototypes' ? <PlayerPage /> : (
        <div className="flex min-h-dvh flex-col bg-background pb-14 lg:h-dvh lg:pb-0">
          <TopBar />
          <div className={cn('shell flex min-h-0 flex-1 flex-col lg:grid', home ? 'nopanel lg:grid-cols-[56px_minmax(0,1fr)]' : wide ? 'lg:grid-cols-[56px_240px_minmax(0,1fr)]' : 'lg:grid-cols-[56px_240px_minmax(0,1fr)_280px]')}>
            <Rail />
            {!home && <ProjectPanel />}
            <main id="main" className={cn('workspace flex min-w-0 flex-col lg:overflow-auto', wide && 'full')}>{main}</main>
            {!wide && <Inspector />}
          </div>
          {!home && <ActivityStrip />}
        </div>
      )}
      <Toaster /><DialogHost />
    </TooltipProvider>
  );
}
void parseRoute;
