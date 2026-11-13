// Shared workflow selectors: presentation and handoff use the same finding selection.
export function findingsForHandoff(research) {
 const selected=research.findings.filter(f=>f.selected);
 return selected.length?selected:research.findings;
}
export function researchJobs(state,projectId) {
 return state.job.filter(j=>j.project_id===projectId&&j.type==='research').sort((a,b)=>b.created_at-a.created_at);
}
export function researchStatus(job) {
 return ({queued:'Queued',running:'Research in progress',succeeded:'Research ready',failed:'Research failed',timed_out:'Research timed out'})[job.status]||job.status;
}
export function boardResearch(board) { return board?.research_findings||[]; }
// Splits a free-text source box into traceable records: http(s) lines become URL sources, the rest pasted excerpts.
// Everything here is user-supplied, never "verified" by the studio.
export function parseSources(text) {
 return String(text||'').split('\n').map(l=>l.trim()).filter(Boolean).map(line=>/^https?:\/\/\S+$/i.test(line)
  ?{title:line,url:line,verification:'source_supplied_by_user'}
  :{title:'Pasted excerpt',text:line,verification:'source_supplied_by_user'});
}
