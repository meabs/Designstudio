import { describe, expect, it } from 'vitest';
import { findingsForHandoff, handoffBrief, parseSources, researchPending } from './research';

describe('research helpers', () => {
  it('use all findings needs no individual selection', () => { const r = { findings: [{ id: 'a' }, { id: 'b' }] }; expect(findingsForHandoff(r)).toEqual(r.findings); expect(findingsForHandoff({ findings: [{ id: 'a', selected: true }, { id: 'b' }] })).toEqual([{ id: 'a', selected: true }]); });
  it('a failed attempt disappears once its retry exists, but a failure without one stays visible', () => {
    const jobs = [{ id: 'a', status: 'failed', retried_by: 'b' }, { id: 'b', status: 'succeeded' }, { id: 'c', status: 'failed' }, { id: 'd', status: 'running' }, { id: 'e', status: 'cancelled', retried_by: 'f' }];
    expect(researchPending(jobs).map((j) => j.id)).toEqual(['c', 'd']);
  });
  it('handoff brief is a design instruction, not the research question', () => { const b = handoffBrief('What will a credit card journey look like in 2030?'); expect(b).toMatch(/^Design the screens of an interface for: What will a credit card journey look like in 2030\./); expect(b).toMatch(/not a written summary/); });
  it('sources keep URLs and pasted excerpts apart, always as user-supplied', () => {
    expect(parseSources('https://example.org/x\nA pasted excerpt\n\n')).toEqual([{ title: 'https://example.org/x', url: 'https://example.org/x', verification: 'source_supplied_by_user' }, { title: 'Pasted excerpt', text: 'A pasted excerpt', verification: 'source_supplied_by_user' }]);
  });
});
