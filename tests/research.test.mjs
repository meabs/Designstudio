import test from 'node:test';
import assert from 'node:assert/strict';
import {findingsForHandoff,researchJobs,researchStatus,boardResearch} from '../apps/web/research.js';
test('use all findings needs no individual selection',()=>{
 const r={findings:[{id:'a'},{id:'b'}]};assert.deepEqual(findingsForHandoff(r),r.findings);
});
test('explicit selection is respected',()=>{
 const r={findings:[{id:'a',selected:false},{id:'b',selected:true}]};assert.deepEqual(findingsForHandoff(r).map(f=>f.id),['b']);
});
test('progress is project scoped and latest first',()=>{
 const state={job:[{id:'old',project_id:'p',type:'research',created_at:1},{id:'other',project_id:'q',type:'research',created_at:3},{id:'generate',project_id:'p',type:'generate_board',created_at:3},{id:'new',project_id:'p',type:'research',created_at:2}]};assert.deepEqual(researchJobs(state,'p').map(j=>j.id),['new','old']);
});
test('each terminal outcome has a distinct visible status',()=>{
 for(const [status,label] of [['running','Research in progress'],['succeeded','Research ready'],['failed','Research failed'],['timed_out','Research timed out']])assert.equal(researchStatus({status}),label);
});
test('board shows its pinned findings rather than global selections',()=>{
 assert.deepEqual(boardResearch({research_findings:[{id:'pinned'}]}),[{id:'pinned'}]);assert.deepEqual(boardResearch({}),[]);
});
import {parseSources} from '../apps/web/research.js';
test('URLs and pasted excerpts become supplied, never verified, sources',()=>{
 const s=parseSources('https://example.org/a\n\n  An excerpt  ');
 assert.equal(s.length,2);assert.equal(s[0].url,'https://example.org/a');assert.equal(s[1].text,'An excerpt');
 assert.ok(s.every(x=>x.verification==='source_supplied_by_user'));assert.deepEqual(parseSources(''),[]);
});
