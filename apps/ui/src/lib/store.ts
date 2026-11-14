// Client state: a tiny external store (no state library), the API client, polling, and the selectors ported from the old store.js.
import { useSyncExternalStore } from 'react';

type Listener = () => void;
export function createStore<T extends object>(init: T) {
  let s = init; const ls = new Set<Listener>();
  return {
    get: () => s,
    set(p: Partial<T> | ((s: T) => Partial<T>)) { s = { ...s, ...(typeof p === 'function' ? p(s) : p) }; ls.forEach((l) => l()); },
    subscribe(l: Listener) { ls.add(l); return () => { ls.delete(l); }; },
  };
}
export function useSel<T extends object, R>(store: ReturnType<typeof createStore<T>>, sel: (s: T) => R): R {
  return useSyncExternalStore(store.subscribe, () => sel(store.get()));
}

export type Data = { project: any[]; context: any[]; board: any[]; variant: any[]; job: any[]; research: any[]; annotation: any[]; runner: any[]; prototype: any[]; reference: any[] };
const EMPTY: Data = { project: [], context: [], board: [], variant: [], job: [], research: [], annotation: [], runner: [], prototype: [], reference: [] };

export const dataStore = createStore<{ data: Data; ready: boolean; agents: any[]; config: { bwrap: boolean; share_port: number; max_jobs?: number } }>({ data: EMPTY, ready: false, agents: [], config: { bwrap: false, share_port: 0 } });
export const useData = () => useSel(dataStore, (s) => s.data);
export const useConfig = () => useSel(dataStore, (s) => s.config);
export const useAgents = () => useSel(dataStore, (s) => s.agents);
export const getData = () => dataStore.get().data;

export async function api(action: string, data?: unknown): Promise<any> {
  const r = await fetch('/api/' + action, data !== undefined ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) } : {});
  const x = await r.json(); if (!r.ok) throw Error(x.message || 'Request failed'); return x;
}
let lastText = '';
export async function refresh() {
  const r = await fetch('/api/state'); const text = await r.text(); if (!r.ok) throw Error('state unavailable');
  if (text === lastText && dataStore.get().ready) return; lastText = text;
  dataStore.set({ data: JSON.parse(text), ready: true });
}
export async function boot() {
  await refresh();
  const [agents, config] = await Promise.all([api('local-agents'), api('config')]); dataStore.set({ agents, config });
}
export async function rescanAgents() { dataStore.set({ agents: await api('local-agents') }); }

/* ---------- UI state shared across components ---------- */
export type Draft = { markdown: string; tokens: string; rules: any[] };
export const ui = createStore({
  screen: '0', selectedVariant: '', device: (typeof matchMedia === 'function' && matchMedia('(max-width:767px)').matches ? 'mobile' : 'desktop') as 'desktop' | 'mobile', zoom: 100,
  showReverted: false, showBefore: false, activePin: '', inspTab: 'design' as 'design' | 'checks' | 'comments' | 'audit', tool: 'comment' as 'comment' | 'move',
  regionOnly: true, showRegions: true, histFilter: 'all', roundState: {} as Record<string, boolean>, fitPending: true, scrollTo: '',
  draft: null as Draft | null, draftFor: '', viewProfile: '', genProfile: '', reviewView: 'd' as 'd' | 'm', busy: false, playerFile: '' as string,
});
export const useUi = <R,>(sel: (s: ReturnType<typeof ui.get>) => R) => useSel(ui, sel);

/* ---------- selectors ---------- */
export const runnerOf = (id: string) => getData().runner.find((r) => r.id === id);
export const enabledRunners = () => getData().runner.filter((r) => r.enabled !== false).sort((a, b) => Number(a.type === 'fixture') - Number(b.type === 'fixture'));
export const variantsOf = (board: any) => getData().variant.filter((v) => v.board_id === board?.id).sort((a, b) => a.created_at - b.created_at);
export const visibleVariants = (board: any) => variantsOf(board).filter((v) => ui.get().showReverted || v.review_state !== 'reverted' || v.id === ui.get().selectedVariant);
export const defaultVariant = (vs: any[]) => vs.find((v) => v.approved) || [...vs].reverse().find((v) => v.review_state !== 'reverted') || vs.at(-1);
export const referencesOf = (pid: string) => getData().reference.filter((r) => r.project_id === pid).sort((a, b) => a.created_at - b.created_at);
export const contextsOf = (pid: string, profileId?: string) => getData().context.filter((c) => c.project_id === pid && (!profileId || (c.profile_id || 'main') === profileId)).sort((a, b) => a.created_at - b.created_at);
// Guideline profiles. A project without any behaves as one implicit 'Main' profile.
export const profilesOf = (p: any): any[] => p?.profiles?.length ? p.profiles : p ? [{ id: 'main', name: 'Main', context_id: p.context_id }] : [];
export const activeProfileId = (p: any) => { const l = profilesOf(p); return l.some((x) => x.id === p?.profile_id) ? p.profile_id : l[0]?.id; };
export const profileCtx = (p: any, profileId?: string, data: Data = getData()) => { const pr = profilesOf(p).find((x) => x.id === (profileId || activeProfileId(p))) || profilesOf(p)[0]; return (pr && data.context.find((c) => c.id === pr.context_id)) || null; };
export const profileOfVariant = (v: any, data: Data = getData()) => { const c = data.context.find((x) => x.id === v?.context_id); const p = data.project.find((x) => x.id === v?.project_id); const id = v?.profile_id || c?.profile_id || 'main'; return { id, name: profilesOf(p).find((x) => x.id === id)?.name || v?.profile_name || 'Main' }; };
export const prototypeOf = (v: any) => getData().prototype.filter((p) => p.variant_id === v?.id).sort((a, b) => b.created_at - a.created_at)[0];
export const refUrl = (r: any) => `/assets/projects/${r.project_id}/references/${r.file}`;
export const jobRefUrl = (jobId: string, r: any) => `/assets/jobs/${jobId}/references/${r.file}`;
export const img = (v: any, s: string, view: string = 'd') => `/assets/variants/${v.id}/thumbnails/${s}${view === 'm' ? '-m' : ''}.png`;
export const live = (v: any, s: string) => `/assets/variants/${v.id}/screens/${s}.html`;
export const protoLive = (p: any, s: string) => `/assets/prototypes/${p.id}/screens/${s}.html`;
export const checksOf = (v: any) => (v?.validation || []).map((x: any, i: number) => ({ ...x, index: i, review: v.reviews?.[i] }));
// Free-exploration level a variant was generated under ('' = normal), and its rules-vs-free twin from the same launch.
export const freeOf = (v: any, data: Data = getData()): string => data.job.find((j) => j.id === v?.job_id)?.context?.run_overrides?.free || '';
export function twinOf(v: any, data: Data = getData()) {
  if (!v || v.parent_id || v.kind === 'mix' || !v.runner_id) return null; const mine = freeOf(v, data); const t = data.job.find((j) => j.id === v.job_id)?.created_at ?? v.created_at;
  return data.variant.find((x) => x.id !== v.id && x.board_id === v.board_id && !x.parent_id && x.runner_id === v.runner_id && (x.profile_id || 'main') === (v.profile_id || 'main') && (freeOf(x, data) ? 1 : 0) !== (mine ? 1 : 0) && Math.abs((data.job.find((j) => j.id === x.job_id)?.created_at ?? x.created_at) - t) < 8) || null;
}
export const unresolvedReviews = (v: any) => checksOf(v).filter((x: any) => x.outcome === 'review' && x.review?.decision !== 'accepted');
export function variantStatus(v: any): [string, string] {
  if (v.approved) return ['Approved · locked', 'success'];
  if (v.review_state === 'pending') return ['Revision awaiting decision', 'warning'];
  if (v.review_state === 'reverted') return ['Reverted', 'error'];
  return ['Generated', 'success'];
}
// Jobs that produced no variation (running, failed, timed out or cancelled), not superseded by a retry and not dismissed.
export const strandedJobs = (board: any) => getData().job.filter((j) => j.board_id === board?.id && ['generate_board', 'revise_board'].includes(j.type) && !j.variant_id && !j.retried_by && !j.dismissed && j.status !== 'succeeded').sort((a, b) => a.created_at - b.created_at);
export const activeJob = (j: any) => ['queued', 'running'].includes(j.status);

// A "round" is one generate action: the variants created together, plus every revision descending from them.
export function roundsOf(board: any) {
  const vs = variantsOf(board); const byId = Object.fromEntries(vs.map((v) => [v.id, v]));
  const jobs = getData().job; const t = (v: any) => jobs.find((j) => j.id === v.job_id)?.created_at ?? v.created_at;
  const root = (v: any) => { let x = v; let g = 0; while (x.parent_id && byId[x.parent_id] && g++ < 50) x = byId[x.parent_id]; return x; };
  const rounds: any[] = []; const of: Record<string, any> = {};
  for (const v of vs.filter((x) => !x.parent_id).sort((a, b) => t(a) - t(b))) {
    const last = rounds.at(-1);
    if (last && v.kind !== 'mix' && last.kind !== 'mix' && t(v) - last.t < 8) last.variants.push(v);
    else rounds.push({ n: rounds.length + 1, t: t(v), kind: v.kind === 'mix' ? 'mix' : 'run', variants: [v] });
  }
  rounds.forEach((r) => r.variants.forEach((v: any) => { of[v.id] = r; }));
  for (const v of vs.filter((x) => x.parent_id)) { const r = of[root(v).id]; if (r) { of[v.id] = r; r.variants.push(v); } }
  rounds.forEach((r) => { r.label = r.kind === 'mix' ? `Mix ${r.n}` : `Round ${r.n}`; });
  return { rounds, of };
}
export const ctxVersion = (c: any) => (c ? c.version || contextsOf(c.project_id).findIndex((x) => x.id === c.id) + 1 || '?' : '?');

/* ---------- guideline draft (unsaved editor state) ---------- */
export function ensureDraft(ctx: any) {
  const s = ui.get(); if (s.draftFor === ctx.id && s.draft) return;
  ui.set({ draft: { markdown: ctx.markdown, tokens: JSON.stringify(ctx.tokens, null, 2), rules: structuredClone(ctx.rules) }, draftFor: ctx.id });
}
export function isDirty(ctx: any, s = ui.get()) {
  if (!ctx || s.draftFor !== ctx.id || !s.draft) return false;
  const strip = (rs: any[]) => JSON.stringify(rs.map((r) => ({ ...r, version: undefined })));
  let tokens: string; try { tokens = JSON.stringify(JSON.parse(s.draft.tokens)); } catch { return true; }
  return s.draft.markdown !== ctx.markdown || tokens !== JSON.stringify(ctx.tokens) || strip(s.draft.rules) !== strip(ctx.rules);
}
// Same precedence as the server (workspace < project < job); lets the designer see conflicts before saving.
export function effectiveOf(rules: any[]) {
  const win: Record<string, any> = {}; const overrides: any[] = [];
  for (const scope of ['workspace', 'project', 'job']) for (const r of rules) if ((r.scope || 'project') === scope && r.enabled !== false) {
    if (win[r.id]) overrides.push({ id: r.id, superseded: win[r.id], winner: r, justification: r.justification || 'More specific scope' });
    win[r.id] = r;
  }
  return { rules: Object.values(win), overrides };
}
export function tokenState(text: string): { tokens: Record<string, any> | null; err: string } {
  try { const t = JSON.parse(text); if (!t || typeof t !== 'object' || Array.isArray(t) || Object.values(t).some((x) => typeof x === 'object')) throw 0; return { tokens: t, err: '' }; }
  catch { return { tokens: null, err: 'Tokens must be a valid flat JSON object (no nesting).' }; }
}

// Median wall-clock of earlier successful runs of the same runner configuration.
export function runnerHistory(rid: string, data: Data = getData()) {
  const d = data.job.filter((j) => j.runner_id === rid && j.status === 'succeeded' && j.usage && ['generate_board', 'revise_board'].includes(j.type)).map((j) => j.usage.duration_s as number).sort((a, b) => a - b);
  if (!d.length) return { n: 0, median: null as number | null };
  const m = d.length % 2 ? d[(d.length - 1) / 2] : (d[d.length / 2 - 1] + d[d.length / 2]) / 2; return { n: d.length, median: m };
}
