// Shared client state and selectors. Views read from here; app.js mutates it.
export const S = {
  data: { project: [], context: [], board: [], variant: [], job: [], research: [], annotation: [], runner: [], prototype: [], reference: [] },
  agents: [], screen: '0', selectedVariant: '', device: 'desktop', zoom: 100, showReverted: false, showBefore: false,
  activePin: '', inspTab: 'design', tool: 'comment', scrollTo: '', fitPending: true, histFilter: 'all', draft: null, draftFor: '', busy: false,
};

export function route() {
  const a = location.pathname.split('/').filter(Boolean), q = new URLSearchParams(location.search);
  const project = S.data.project.find(p => p.id === a[1]) || S.data.project.find(p => !p.archived);
  const view = a[0] === 'settings' ? 'settings' : a[0] === 'projects' && a.length === 1 ? 'projects' : a[2] || 'boards';
  return { project, view, boardId: view === 'prototypes' ? '' : a[3], mode: view === 'prototypes' ? '' : a[4] || '', variantId: a[5] || '', prototypeId: view === 'prototypes' ? a[3] : '', q };
}
export const base = () => '/projects/' + route().project?.id;
export const nav = view => base() + '/' + view;
export const boardPath = (b, mode = '', extra = '') => `${nav('boards')}/${b.id}${mode ? '/' + mode : ''}${extra ? '/' + extra : ''}`;
export const img = (v, s) => `/assets/variants/${v.id}/thumbnails/${s}.png`;
export const live = (v, s) => `/assets/variants/${v.id}/screens/${s}.html`;
export const protoLive = (p, s) => `/assets/prototypes/${p.id}/screens/${s}.html`;
export const runnerOf = id => S.data.runner.find(r => r.id === id);
export const enabledRunners = () => S.data.runner.filter(r => r.enabled !== false).sort((a, b) => (a.type === 'fixture') - (b.type === 'fixture'));
export const variantsOf = board => S.data.variant.filter(v => v.board_id === board?.id).sort((a, b) => a.created_at - b.created_at);
export const visibleVariants = board => variantsOf(board).filter(v => S.showReverted || v.review_state !== 'reverted' || v.id === S.selectedVariant);
export const defaultVariant = vs => vs.find(v => v.approved) || [...vs].reverse().find(v => v.review_state !== 'reverted') || vs.at(-1);
export const referencesOf = pid => S.data.reference.filter(r => r.project_id === pid).sort((a, b) => a.created_at - b.created_at);
export const refUrl = r => `/assets/projects/${r.project_id}/references/${r.file}`;
export const jobRefUrl = (jobId, r) => `/assets/jobs/${jobId}/references/${r.file}`;
export const contextsOf = pid => S.data.context.filter(c => c.project_id === pid).sort((a, b) => a.created_at - b.created_at);
export const prototypeOf = v => S.data.prototype.filter(p => p.variant_id === v?.id).sort((a, b) => b.created_at - a.created_at)[0];

export function current() {
  const r = route(), p = r.project, boards = S.data.board.filter(b => b.project_id === p?.id);
  const listPage = r.view === 'boards' && !r.boardId;
  const b = boards.find(b => b.id === r.boardId) || (listPage ? null : boards[0]);
  const vs = variantsOf(b);
  const pool = r.view === 'boards' && r.mode === 'review' && r.variantId ? r.variantId : S.selectedVariant;
  const v = vs.find(v => v.id === pool) || defaultVariant(vs);
  const ctx = S.data.context.find(c => c.id === p?.context_id);
  return { r, p, b, vs, v, ctx, boards };
}

// Validation helpers shared by canvas, inspector and approval dialog.
export const checksOf = v => (v?.validation || []).map((x, i) => ({ ...x, index: i, review: v.reviews?.[i] }));
export const unresolvedReviews = v => checksOf(v).filter(x => x.outcome === 'review' && x.review?.decision !== 'accepted');
export function variantStatus(v) {
  if (v.approved) return ['Approved · locked', 'success'];
  if (v.review_state === 'pending') return ['Revision awaiting decision', 'warn'];
  if (v.review_state === 'reverted') return ['Reverted', 'fail'];
  return ['Generated', 'success'];
}
// Jobs that produced no variation (running, failed, timed out or cancelled) and were not superseded by a retry.
export const strandedJobs = board => S.data.job.filter(j => j.board_id === board?.id && ['generate_board', 'revise_board'].includes(j.type) && !j.variant_id && !j.retried_by && j.status !== 'succeeded').sort((a, b) => a.created_at - b.created_at);

export function signature() {
  const d = S.data;
  return JSON.stringify([d.job.map(j => [j.id, j.status, j.events.length, j.retried_by]), d.variant.map(v => [v.id, v.approved, v.review_state, Object.keys(v.reviews || {}).length]),
    d.annotation.map(a => [a.id, a.status, a.selected, a.comment]), d.board.map(b => [b.id, b.title, b.research_updated_at]), d.prototype.length, d.context.map(c => c.id), d.runner.map(r => [r.id, r.enabled, r.name]),
    d.research.map(r => [r.id, r.findings.filter(f => f.selected).length]), d.reference.map(r => [r.id, r.name, r.note]), d.project.map(p => [p.id, p.name, p.archived, p.context_id])]);
}
