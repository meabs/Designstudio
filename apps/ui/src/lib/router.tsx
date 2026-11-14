import { useSyncExternalStore, type AnchorHTMLAttributes, type MouseEvent } from 'react';
import { createStore, dataStore, ui, useData, useSel, variantsOf, defaultVariant, getData, profileCtx, profilesOf } from './store';

const loc = createStore({ path: location.pathname + location.search });
window.addEventListener('popstate', () => loc.set({ path: location.pathname + location.search }));
export function navigate(path: string, opts: { replace?: boolean; keepView?: boolean } = {}) {
  const samePath = path.split('?')[0] === location.pathname;
  history[opts.replace ? 'replaceState' : 'pushState']({}, '', path); loc.set({ path });
  if (!opts.keepView && !samePath) ui.set({ screen: '0', activePin: '', showBefore: false, fitPending: true });
}
export const useLocationPath = () => useSel(loc, (s) => s.path);

export type Route = { project: any; view: string; boardId: string; mode: string; variantId: string; prototypeId: string; q: URLSearchParams };
export function parseRoute(path: string, data = getData()): Route {
  const [pathname, search] = path.split('?'); const a = pathname.split('/').filter(Boolean); const q = new URLSearchParams(search || '');
  const project = data.project.find((p) => p.id === a[1]) || data.project.find((p) => !p.archived);
  const view = a[0] === 'settings' ? 'settings' : a[0] === 'projects' && a.length === 1 ? 'projects' : a[2] || 'boards';
  return { project, view, boardId: view === 'prototypes' ? '' : a[3] || '', mode: view === 'prototypes' ? '' : a[4] || '', variantId: a[5] || '', prototypeId: view === 'prototypes' ? a[3] || '' : '', q };
}
export function useRoute(): Route { const path = useLocationPath(); const data = useData(); return parseRoute(path, data); }

export const projectBase = (r: Route) => '/projects/' + r.project?.id;
export const nav = (r: Route, view: string) => projectBase(r) + '/' + view;
export const boardPath = (r: Route, b: any, mode = '', extra = '') => `${nav(r, 'boards')}/${b.id}${mode ? '/' + mode : ''}${extra ? '/' + extra : ''}`;

export function computeCurrent(path: string, data = getData(), selected = ui.get().selectedVariant) {
  const r = parseRoute(path, data);
  const p = r.project; const boards = data.board.filter((b) => b.project_id === p?.id);
  const listPage = r.view === 'boards' && !r.boardId;
  const b = boards.find((x) => x.id === r.boardId) || (listPage ? null : boards[0]) || null;
  const vs = variantsOf(b); const pool = r.view === 'boards' && r.mode === 'review' && r.variantId ? r.variantId : selected;
  const v = vs.find((x) => x.id === pool) || defaultVariant(vs) || null;
  // The Guidelines page shows the profile being edited; everywhere else shows the project's default profile.
  const ctx = (r.view === 'context' && profilesOf(p).some((x) => x.id === ui.get().viewProfile) && profileCtx(p, ui.get().viewProfile, data)) || data.context.find((c) => c.id === p?.context_id) || null;
  return { r, p, b, vs, v, ctx, boards };
}
export const getCurrent = () => computeCurrent(location.pathname + location.search);
export function useCurrent() {
  const path = useLocationPath(); const data = useData(); const selected = useSel(ui, (s) => s.selectedVariant); useSel(ui, (s) => s.viewProfile);
  return computeCurrent(path, data, selected);
}

export function Link({ href, children, ...rest }: AnchorHTMLAttributes<HTMLAnchorElement> & { href: string }) {
  const onClick = (e: MouseEvent<HTMLAnchorElement>) => {
    if (e.defaultPrevented || e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || rest.target || rest.download) return;
    if (!href.startsWith('/') || href.startsWith('/api/') || href.startsWith('/assets/')) return;
    e.preventDefault(); navigate(href);
  };
  return <a href={href} onClick={onClick} {...rest}>{children}</a>;
}
void useSyncExternalStore; void dataStore;
