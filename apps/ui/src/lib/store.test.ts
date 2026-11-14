import { beforeEach, describe, expect, it } from 'vitest';
import { dataStore, roundsOf, ctxVersion, strandedJobs, effectiveOf, tokenState, isDirty, ui, runnerHistory, variantStatus } from './store';

const set = (p: any) => dataStore.set((s) => ({ data: { ...s.data, ...p } }));
beforeEach(() => set({ job: [], variant: [], context: [] }));

describe('rounds', () => {
  it('runs are grouped into rounds; revisions stay with their root; mixes get their own round', () => {
    set({ job: [{ id: 'j1', created_at: 100 }, { id: 'j2', created_at: 101 }, { id: 'j3', created_at: 500 }, { id: 'j4', created_at: 900 }],
      variant: [{ id: 'a', board_id: 'b', job_id: 'j1', created_at: 100 }, { id: 'b2', board_id: 'b', job_id: 'j2', created_at: 101 }, { id: 'c', board_id: 'b', job_id: 'j3', created_at: 500 }, { id: 'a2', board_id: 'b', job_id: 'j4', parent_id: 'a', created_at: 900 }, { id: 'm', board_id: 'b', job_id: 'j4', kind: 'mix', created_at: 950 }, { id: 'x', board_id: 'other', job_id: 'j1', created_at: 100 }] });
    const { rounds, of } = roundsOf({ id: 'b' });
    expect(rounds.map((r: any) => [r.label, r.variants.map((v: any) => v.id)])).toEqual([['Round 1', ['a', 'b2', 'a2']], ['Round 2', ['c']], ['Mix 3', ['m']]]);
    expect(of.a2).toBe(of.a); expect(of.c).not.toBe(of.a);
  });
});
describe('selectors', () => {
  it('context version falls back to creation order for old records without one', () => {
    set({ context: [{ id: 'x', project_id: 'p', created_at: 1 }, { id: 'y', project_id: 'p', created_at: 2 }, { id: 'z', project_id: 'p', created_at: 3, version: 9 }] });
    const c = dataStore.get().data.context; expect(ctxVersion(c[1])).toBe(2); expect(ctxVersion(c[2])).toBe(9); expect(ctxVersion(undefined)).toBe('?');
  });
  it('dismissed and retried failures no longer count as stranded jobs', () => {
    set({ job: [{ id: '1', board_id: 'b', type: 'generate_board', status: 'failed' }, { id: '2', board_id: 'b', type: 'generate_board', status: 'failed', dismissed: true }, { id: '3', board_id: 'b', type: 'generate_board', status: 'failed', retried_by: '4' }, { id: '4', board_id: 'b', type: 'generate_board', status: 'running' }] });
    expect(strandedJobs({ id: 'b' }).map((j: any) => j.id)).toEqual(['1', '4']);
  });
  it('runner history is the median of successful generation runs only', () => {
    set({ job: [10, 30, 20].map((d, i) => ({ id: 'j' + i, runner_id: 'r', status: 'succeeded', type: 'generate_board', usage: { duration_s: d } })).concat([{ id: 'f', runner_id: 'r', status: 'failed', type: 'generate_board', usage: { duration_s: 999 } } as any]) });
    expect(runnerHistory('r')).toEqual({ n: 3, median: 20 }); expect(runnerHistory('nobody')).toEqual({ n: 0, median: null });
  });
  it('variant status wording', () => { expect(variantStatus({ approved: true })[0]).toMatch(/Approved/); expect(variantStatus({ review_state: 'pending' })[1]).toBe('warning'); expect(variantStatus({})[0]).toBe('Generated'); });
});
describe('guideline drafts', () => {
  it('rules merge by scope precedence and report overrides', () => {
    const e = effectiveOf([{ id: 'A', scope: 'project', description: 'p' }, { id: 'A', scope: 'job', description: 'j' }, { id: 'B', scope: 'workspace', enabled: false }]);
    expect(e.rules.map((r: any) => r.description)).toEqual(['j']); expect(e.overrides).toHaveLength(1);
  });
  it('tokens must be a flat JSON object', () => { expect(tokenState('{"a":"#fff"}').err).toBe(''); expect(tokenState('{"a":{}}').err).toMatch(/flat JSON/); expect(tokenState('{').err).toMatch(/flat JSON/); });
  it('isDirty ignores rule version numbers and detects real edits', () => {
    const ctx = { id: 'c', markdown: 'm', tokens: { a: '1' }, rules: [{ id: 'R', version: 3 }] };
    ui.set({ draftFor: 'c', draft: { markdown: 'm', tokens: '{"a":"1"}', rules: [{ id: 'R', version: 1 }] } }); expect(isDirty(ctx)).toBe(false);
    ui.set({ draft: { markdown: 'changed', tokens: '{"a":"1"}', rules: [{ id: 'R' }] } }); expect(isDirty(ctx)).toBe(true);
  });
});
