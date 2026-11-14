export function findingsForHandoff(research: any) { const selected = research.findings.filter((f: any) => f.selected); return selected.length ? selected : research.findings; }
export const researchJobs = (state: any, projectId: string) => state.job.filter((j: any) => j.project_id === projectId && j.type === 'research').sort((a: any, b: any) => b.created_at - a.created_at);
// Attempts still needing attention: not finished OK and not already replaced by a retry.
export const researchPending = (jobs: any[]) => jobs.filter((j) => j.status !== 'succeeded' && !j.retried_by);
export const researchStatus = (job: any) => ({ queued: 'Queued', running: 'Research in progress', succeeded: 'Research ready', failed: 'Research failed', timed_out: 'Research timed out' } as any)[job.status] || job.status;
export const boardResearch = (board: any) => board?.research_findings || [];
export function parseSources(text: string) {
  return String(text || '').split('\n').map((l) => l.trim()).filter(Boolean).map((line) => (/^https?:\/\/\S+$/i.test(line)
    ? { title: line, url: line, verification: 'source_supplied_by_user' } : { title: 'Pasted excerpt', text: line, verification: 'source_supplied_by_user' }));
}
// The design brief for a board made from research: an instruction to design screens, never the bare research question.
export const handoffBrief = (question: string) => `Design the screens of an interface for: ${String(question || '').trim().replace(/[?.\s]+$/, '')}. Turn the selected research findings into real interface screens (steps, forms, actions), not a written summary.`;
