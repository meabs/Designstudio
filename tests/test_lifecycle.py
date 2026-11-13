import sys, tempfile, unittest, time, threading, json, re
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/api'))
import server as s, jobs

class LifecycleTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.old=s.STORE; s.STORE=Path(self.tmp.name); s.seed(); self.p=s.allof('project')[0]; self.b=s.allof('board')[0]; s.CANCEL.clear()
 def tearDown(self): s.STORE=self.old; self.tmp.cleanup()
 def run_job(self,kind='generate_board',runner=1,parent=None,annotations=[]):
  ctx=s.get(self.p['context_id']); j=dict(id=s.uid(),project_id=self.p['id'],type=kind,runner_id=s.allof('runner')[runner]['id'],context=ctx,board_id=self.b['id'],parent_id=parent,annotations=annotations,brief=self.b['brief'],instruction='t',events=[],status='queued',created_at=time.time())
  s.save('job',j)
  with patch.object(s.subprocess,'run',return_value=None),patch.object(s.time,'sleep'): s.execute(j)
  return s.get(j['id'])
 def variant(self,**kw): return s.get(self.run_job(**kw)['variant_id'])
 # --- regression: research result must not be overwritten by its own job record
 def test_research_result_survives_job_completion(self):
  j=dict(id=s.uid(),project_id=self.p['id'],type='research',runner_id=s.allof('runner')[0]['id'],context=s.get(self.p['context_id']),brief='q',instruction='t',events=[],status='queued',sources=[],created_at=time.time()); s.save('job',j)
  with patch.object(s.time,'sleep'): s.execute(j)
  r=[x for x in s.allof('research') if x['project_id']==self.p['id']]; self.assertEqual(len(r),1); self.assertEqual(r[0]['job_id'],j['id']); self.assertEqual(s.get(j['id'])['status'],'succeeded'); self.assertTrue(r[0]['findings'])
 def test_empty_research_question_rejected(self):
  with self.assertRaises(ValueError): s.launch({'brief':'  ','runner_ids':[s.allof('runner')[0]['id']]},'research',self.p['id'])
 # --- context
 def test_identical_save_returns_same_version(self):
  c=s.get(self.p['context_id']); again=s.context(self.p['id'],{'markdown':c['markdown'],'tokens':c['tokens'],'rules':[{k:v for k,v in r.items()} for r in c['rules']]}); self.assertEqual(again['id'],c['id']); self.assertEqual(len([x for x in s.allof('context') if x['project_id']==self.p['id']]),1)
 def test_rule_versions_increment_only_on_change(self):
  c=s.get(self.p['context_id']); rules=[dict(r) for r in c['rules']]; rules[0]['description']='Changed'; n=s.context(self.p['id'],{'markdown':c['markdown'],'tokens':c['tokens'],'rules':rules})
  self.assertEqual(n['version'],2); by={r['id']:r['version'] for r in n['rules']}; self.assertEqual(by['CTA-001'],2); self.assertEqual(by['COPY-001'],1)
 def test_duplicate_or_blank_rule_rejected(self):
  r=dict(s.RULES[0])
  with self.assertRaises(ValueError): s.context(self.p['id'],{'rules':[r,dict(r)]})
  with self.assertRaises(ValueError): s.context(self.p['id'],{'rules':[dict(r,id=' ')]})
 # --- revision decisions and approval
 def test_revision_pending_accept_revert_and_lineage(self):
  parent=self.variant(); a=s.save('annotation',dict(id=s.uid(),variant_id=parent['id'],screen='0',x=.5,y=.2,comment='Move text',status='open',selected=True,created_at=time.time()))
  job=self.run_job('revise_board',1,parent['id'],[a]); child=s.get(job['variant_id']); self.assertEqual(child['review_state'],'pending'); self.assertEqual(child['changed_screens'],['0']); self.assertIsNone(parent.get('review_state'))
  self.assertEqual(s.set_review_state(child['id'],'reverted')['review_state'],'reverted'); self.assertEqual(s.get(parent['id'])['id'],parent['id'])
  with self.assertRaises(ValueError): s.set_review_state(parent['id'],'accepted')
 def test_reverted_cannot_be_approved_and_approved_cannot_be_reverted(self):
  parent=self.variant(); a=s.save('annotation',dict(id=s.uid(),variant_id=parent['id'],screen='1',x=.5,y=.5,comment='x',status='open',selected=True,created_at=time.time()))
  child=s.get(self.run_job('revise_board',1,parent['id'],[a])['variant_id']); s.set_review_state(child['id'],'reverted')
  with self.assertRaises(ValueError): s.approve(child['id'])
  child2=s.get(self.run_job('revise_board',1,parent['id'],[s.save('annotation',dict(id=s.uid(),variant_id=parent['id'],screen='0',x=.5,y=.5,comment='y',status='open',selected=True,created_at=time.time()))])['variant_id']); s.approve(child2['id'])
  with self.assertRaises(ValueError): s.set_review_state(child2['id'],'reverted')
 def test_approval_is_idempotent_locked_and_builds_isolated_bundle(self):
  v=self.variant(); r1=s.approve(v['id']); r2=s.approve(v['id']); self.assertEqual(r1['prototype']['id'],r2['prototype']['id']); self.assertEqual(len(s.allof('prototype')),1)
  bundle=s.STORE/'prototypes'/r1['prototype']['id']; self.assertTrue((bundle/'index.html').is_file()); self.assertIn('nav.js',(bundle/'screens/0.html').read_text())
  self.assertNotIn('nav.js',(s.STORE/'variants'/v['id']/'screens/0.html').read_text(),'source variant stays untouched')
  self.assertTrue(s.get(v['id'])['approved'])
 def test_approving_another_variant_moves_approval_but_keeps_prototypes(self):
  a=self.variant(runner=0); b=self.variant(runner=1); pa=s.approve(a['id'])['prototype']; s.approve(b['id'])
  self.assertFalse(s.get(a['id'])['approved']); self.assertTrue(s.get(b['id'])['approved']); self.assertTrue((s.STORE/'prototypes'/pa['id']/'screens/0.html').is_file())
 # --- annotations
 def test_only_open_pins_on_parent_can_drive_revision(self):
  parent=self.variant(); other=self.variant(runner=0); pin=s.save('annotation',dict(id=s.uid(),variant_id=other['id'],screen='0',x=.1,y=.1,comment='c',status='open',selected=True,created_at=time.time()))
  with self.assertRaises(ValueError): s.launch(dict(board_id=self.b['id'],parent_id=parent['id'],annotation_ids=[pin['id']],runner_ids=[parent['runner_id']]),'revise_board',self.p['id'])
  with self.assertRaises(ValueError): s.launch(dict(board_id=self.b['id'],parent_id=parent['id'],annotation_ids=[],runner_ids=[parent['runner_id']]),'revise_board',self.p['id'])
 # --- jobs: cancel, timeout, retry, concurrency
 def cli_runner(self,exe,args,timeout=30):
  return s.save('runner',dict(id=s.uid(),name='cli',type='cli',executable=exe,args=args,timeout=timeout,enabled=True))
 def test_cancel_running_cli_job_saves_no_variant(self):
  r=self.cli_runner('/bin/sleep',['30']); j=dict(id=s.uid(),project_id=self.p['id'],type='generate_board',runner_id=r['id'],context=s.get(self.p['context_id']),board_id=self.b['id'],parent_id=None,annotations=[],brief='b',instruction='t',events=[],status='queued',created_at=time.time()); s.save('job',j)
  t=threading.Thread(target=s.execute,args=(j,)); t.start(); time.sleep(.8); s.CANCEL.add(j['id']); t.join(10); self.assertFalse(t.is_alive()); self.assertEqual(s.get(j['id'])['status'],'cancelled'); self.assertEqual(s.allof('variant'),[])
 def test_timeout_is_distinct_and_keeps_partial_log(self):
  r=self.cli_runner('/bin/sh',['-c','echo partial; sleep 30'],timeout=1); j=dict(id=s.uid(),project_id=self.p['id'],type='generate_board',runner_id=r['id'],context=s.get(self.p['context_id']),board_id=self.b['id'],parent_id=None,annotations=[],brief='b',instruction='t',events=[],status='queued',created_at=time.time()); s.save('job',j)
  s.execute(j); self.assertEqual(s.get(j['id'])['status'],'timed_out'); self.assertIn('partial',(s.STORE/'jobs'/j['id']/'runner.log').read_text())
 def test_retry_reuses_inputs_once(self):
  r=self.cli_runner('/bin/false',[]); j=dict(id=s.uid(),project_id=self.p['id'],type='generate_board',runner_id=r['id'],context=s.get(self.p['context_id']),board_id=self.b['id'],parent_id=None,annotations=[],brief='b',instruction='t',events=[],status='queued',created_at=time.time(),input_hash='abc'); s.save('job',j); s.execute(j); self.assertEqual(s.get(j['id'])['status'],'failed')
  with patch.object(s.threading,'Thread'): new=s.retry_job(j['id'])
  self.assertEqual(new['input_hash'],'abc'); self.assertEqual(new['retry_of'],j['id']); self.assertEqual(s.get(j['id'])['retried_by'],new['id'])
  with self.assertRaises(ValueError): s.retry_job(j['id'])
  with self.assertRaises(ValueError): s.retry_job(new['id'])
 def test_disabled_runner_rejected(self):
  r=s.allof('runner')[0]; r['enabled']=False; s.save('runner',r)
  with self.assertRaises(ValueError): s.launch(dict(board_id=self.b['id'],brief='b',runner_ids=[r['id']]),'generate_board',self.p['id'])


 # --- reference images
 PNG=bytes.fromhex('89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c4890000000d49444154789c6360f8cfc0f01f0005000201a5f645e60000000049454e44ae426082')
 def upload(self,raw=None,name='Mood board.png',pid=None):
  import base64
  return s.add_reference(dict(project_id=pid or self.p['id'],name=name,data=base64.b64encode(raw or self.PNG).decode()))
 def test_reference_upload_validates_type_and_size(self):
  r=self.upload(); self.assertEqual(r['mime'],'image/png'); self.assertTrue((s.STORE/'projects'/self.p['id']/'references'/r['file']).is_file())
  with self.assertRaises(ValueError): self.upload(b'<svg onload=alert(1)></svg>')
  with self.assertRaises(ValueError): self.upload(b'\x89PNG\r\n\x1a\n'+b'0'*(s.MAX_REF_BYTES+1))
  with self.assertRaises(ValueError): s.add_reference(dict(project_id=self.p['id'],data='not base64!!'))
  self.assertNotIn('/',self.upload(name='../../etc/passwd.png')['name'])
 def test_references_reach_job_envelope_instruction_and_snapshot(self):
  r=self.upload(); rec=s.get(r['id']); rec['note']='Use this card layout'; s.save('reference',rec)
  with patch.object(s.threading,'Thread'): jobs=s.launch(dict(board_id=self.b['id'],brief='b',runner_ids=[x['id'] for x in s.allof('runner')[:2]],reference_ids=[r['id']]),'generate_board',self.p['id'])
  for j in jobs:
   self.assertEqual(j['references'][0]['sha256'],r['sha256']); self.assertIn('references/'+r['file'],j['instruction']); self.assertIn('Use this card layout',j['instruction']); self.assertTrue((s.STORE/'jobs'/j['id']/'references'/r['file']).is_file())
  self.assertEqual(jobs[0]['input_hash'],jobs[1]['input_hash']); self.assertEqual(s.get(self.b['id'])['reference_ids'],[r['id']])
 def test_references_change_shared_input_hash(self):
  r=self.upload()
  with patch.object(s.threading,'Thread'):
   a=s.launch(dict(board_id=self.b['id'],brief='b',runner_ids=[s.allof('runner')[0]['id']],reference_ids=[]),'generate_board',self.p['id'])[0]
   b=s.launch(dict(board_id=self.b['id'],brief='b',runner_ids=[s.allof('runner')[0]['id']],reference_ids=[r['id']]),'generate_board',self.p['id'])[0]
  self.assertNotEqual(a['input_hash'],b['input_hash'])
 def test_snapshot_survives_library_delete_and_retry(self):
  r=self.upload(); runner=self.cli_runner('/bin/false',[])
  with patch.object(s.threading,'Thread'): j=s.launch(dict(board_id=self.b['id'],brief='b',runner_ids=[runner['id']],reference_ids=[r['id']]),'generate_board',self.p['id'])[0]
  s.execute(j); s.delete_reference(r['id']); self.assertEqual(s.allof('reference'),[])
  with patch.object(s.threading,'Thread'): new=s.retry_job(j['id'])
  self.assertTrue((s.STORE/'jobs'/new['id']/'references'/r['file']).is_file())
 def test_variant_flags_references_for_designer_review(self):
  r=self.upload(); b=s.get(self.b['id']); b['reference_ids']=[r['id']]; s.save('board',b)
  with patch.object(s.threading,'Thread'): j=s.launch(dict(board_id=self.b['id'],brief='b',runner_ids=[s.allof('runner')[0]['id']]),'generate_board',self.p['id'])[0]
  with patch.object(s.subprocess,'run',return_value=None),patch.object(s.time,'sleep'): s.execute(j)
  v=s.get(s.get(j['id'])['variant_id']); self.assertEqual(len(v['references']),1); self.assertTrue(any(x['check'].startswith('Reference images') and x['outcome']=='review' for x in v['validation']))
 def test_reference_from_other_project_rejected(self):
  other=s.project({'name':'Other'}); r=self.upload(pid=other['id'])
  with self.assertRaises(ValueError): s.launch(dict(board_id=self.b['id'],brief='b',runner_ids=[s.allof('runner')[0]['id']],reference_ids=[r['id']]),'generate_board',self.p['id'])

 # --- hardened validation
 def pkg(self):
  v=self.variant(); return v,s.STORE/'variants'/v['id']
 def test_hostile_content_rejected(self):
  v,folder=self.pkg(); page=folder/'screens/0.html'; original=page.read_text()
  cases={'<style>@import "x.css";</style>':'@import','<div style="background:url(https://evil.test/a.png)"></div>':'url','<script>navigator.sendBeacon("/x")</script>':'sendBeacon','<iframe src="screens/1.html"></iframe>':'frame','<script>import("./x.js")</script>':'import','<form action="https://evil.test"></form>':'action','<script>location.href="https://evil.test"</script>':'navigation'}
  for bad,why in cases.items():
   page.write_text(original+bad)
   with self.assertRaises(ValueError,msg=why): s.validate(folder,v['manifest'],[])
  page.write_text(original); s.validate(folder,v['manifest'],[])
 def test_external_reference_in_css_or_js_asset_rejected(self):
  v,folder=self.pkg(); (folder/'assets').mkdir(exist_ok=True)
  (folder/'assets/theme.css').write_text('body{background:url(//cdn.test/x.png)}')
  with self.assertRaises(ValueError): s.validate(folder,v['manifest'],[])
  (folder/'assets/theme.css').write_text('a{color:red}'); (folder/'assets/app.js').write_text('fetch("/api")')
  with self.assertRaises(ValueError): s.validate(folder,v['manifest'],[])
 def test_symlink_and_file_count_limits(self):
  v,folder=self.pkg(); (folder/'assets').mkdir(exist_ok=True); (folder/'assets/link.txt').symlink_to('/etc/hostname')
  with self.assertRaises(ValueError): s.validate(folder,v['manifest'],[])
  (folder/'assets/link.txt').unlink()
  for i in range(s.MAX_PACKAGE_FILES+1): (folder/'assets'/f'f{i}.txt').write_text('x')
  with self.assertRaises(ValueError): s.validate(folder,v['manifest'],[])
 def test_unresolved_token_reference_fails_check(self):
  v,folder=self.pkg(); page=folder/'screens/0.html'; page.write_text(page.read_text()+'<style>p{color:var(--missing-token)}</style>')
  r=[x for x in s.validate(folder,v['manifest'],[],{'accent':'#000'}) if x['check']=='Token references'][0]; self.assertEqual(r['outcome'],'fail'); self.assertIn('--missing-token',r['evidence'])
  page.write_text(page.read_text().replace('var(--missing-token)','var(--missing-token,#111)'))
  self.assertEqual([x for x in s.validate(folder,v['manifest'],[]) if x['check']=='Token references'][0]['outcome'],'pass')
 def test_manifest_contract_errors_are_specific(self):
  good=self.variant()['manifest']
  for mutate,msg in [(lambda m:m.update(kind='x'),'contract'),(lambda m:m.update(screens=[]),'screens'),(lambda m:m['screens'].append(dict(m['screens'][0])),'Duplicate'),(lambda m:m.update(start_screen_id='zzz'),'start_screen_id'),(lambda m:m['edges'].append({'from':'0','to':'9'}),'edge'),(lambda m:m['screens'][0].pop('title'),'title')]:
   import copy; m=copy.deepcopy(good); mutate(m)
   with self.assertRaisesRegex(ValueError,msg): s.check_manifest(m)
 # --- environment allowlist
 def test_cli_runner_only_sees_allowlisted_environment(self):
  import os
  os.environ['STUDIO_TEST_SECRET']='leak-me'; os.environ['STUDIO_TEST_OK']='fine'
  try:
   r=s.save('runner',dict(id=s.uid(),name='env',type='cli',executable='/bin/sh',args=['-c','echo secret=$STUDIO_TEST_SECRET ok=$STUDIO_TEST_OK'],timeout=20,enabled=True,env_allowlist=['PATH','STUDIO_TEST_OK']))
   j=dict(id=s.uid(),project_id=self.p['id'],type='generate_board',runner_id=r['id'],context=s.get(self.p['context_id']),board_id=self.b['id'],parent_id=None,annotations=[],brief='b',instruction='t',events=[],status='queued',created_at=time.time()); s.save('job',j); s.execute(j)
   log=(s.STORE/'jobs'/j['id']/'runner.log').read_text(); self.assertIn('secret= ',log); self.assertIn('ok=fine',log); self.assertNotIn('leak-me',log)
  finally: os.environ.pop('STUDIO_TEST_SECRET',None); os.environ.pop('STUDIO_TEST_OK',None)
 def test_local_agent_configs_carry_auth_env_but_not_everything(self):
  import local_agents
  from unittest.mock import patch as p
  with p.object(local_agents,'discover',return_value=[{'id':'claude','name':'Claude Code','supported':True,'executable':'/x/claude'}]):
   c=local_agents.configuration('claude','')
  self.assertIn('ANTHROPIC_API_KEY',c['env_allowlist']); self.assertNotIn('AWS_SECRET_ACCESS_KEY',c['env_allowlist'])

 def test_relative_links_inside_package_allowed_outside_rejected(self):
  v,folder=self.pkg(); (folder/'assets').mkdir(exist_ok=True); (folder/'assets/theme.css').write_text('a{color:red}'); page=folder/'screens/0.html'; base=page.read_text()
  page.write_text(base+'<link rel="stylesheet" href="../assets/theme.css">'); s.validate(folder,v['manifest'],[])
  for bad,msg in [('<a href="../../outside.html">x</a>','outside'),('<img src="/etc/passwd">','outside'),('<script src="../assets/missing.js"></script>','missing')]:
   page.write_text(base+bad)
   with self.assertRaisesRegex(ValueError,msg): s.validate(folder,v['manifest'],[])

 # --- durable queue
 def queued_job(self,runner=0,created=None,status='queued'):
  j=dict(id=s.uid(),project_id=self.p['id'],type='generate_board',runner_id=s.allof('runner')[runner]['id'],context=s.get(self.p['context_id']),board_id=self.b['id'],parent_id=None,annotations=[],brief='b',instruction='t',events=[],status=status,created_at=created or time.time())
  return s.save('job',j)
 def drain(self):
  while not s.JOBQ.empty(): s.JOBQ.get_nowait()
 def test_restart_resumes_queued_in_order_and_fails_interrupted(self):
  self.drain(); a=self.queued_job(created=1); b=self.queued_job(created=2); c=self.queued_job(created=3,status='running'); self.drain()   # simulate a restart: memory empty, DB intact
  self.assertEqual(s.recover_jobs(),2); self.assertEqual([s.JOBQ.get_nowait(),s.JOBQ.get_nowait()],[a['id'],b['id']])
  self.assertEqual(s.get(c['id'])['status'],'failed'); self.assertIn('Retry',s.get(c['id'])['events'][-1]['message']); self.assertIn('Resumed',s.get(a['id'])['events'][-1]['message'])
  with patch.object(s.threading,'Thread'): self.assertEqual(s.retry_job(c['id'])['retry_of'],c['id'])
 def test_cancel_queued_job_is_immediate_and_never_runs(self):
  self.drain(); j=self.queued_job(); s.enqueue(j); s.cancel_job(j['id']); self.assertEqual(s.get(j['id'])['status'],'cancelled')
  self.assertIsNone(s.claim(j['id'])); self.assertEqual(s.allof('variant'),[])
 def test_claim_is_exclusive(self):
  j=self.queued_job(); self.assertIsNotNone(s.claim(j['id'])); self.assertIsNone(s.claim(j['id'])); self.assertEqual(s.get(j['id'])['status'],'running')
 def test_workers_execute_queued_jobs_and_respect_limit(self):
  self.drain(); s.stop_workers()
  try:
   jobs=[self.queued_job(runner=i%2) for i in range(4)]
   with patch.object(s.subprocess,'run',return_value=None): 
    for j in jobs: s.enqueue(j)
    s.start_workers(2); self.assertEqual(len(s.WORKERS),2)
    end=time.time()+30
    while time.time()<end and any(s.get(j['id'])['status'] not in ('succeeded','failed') for j in jobs): time.sleep(.1)
   self.assertEqual([s.get(j['id'])['status'] for j in jobs],['succeeded']*4); self.assertEqual(len(s.allof('variant')),4)
  finally: s.stop_workers(); self.drain()

 # --- per-region revisions
 DOC='<html>\n<body>\n<main data-design-id="card"><h1 data-design-id="heading">Hello <b>there</b></h1><p>Body</p><img data-design-id="logo" src="a.png"><a data-design-id="cta" href="#">Go</a></main>\n<footer>Foot</footer></body></html>'
 def test_element_spans_handle_nesting_and_void_tags(self):
  sp=s.element_spans(self.DOC); self.assertEqual(set(sp),{'card','heading','logo','cta'}); a,b=sp['heading']; self.assertEqual(self.DOC[a:b],'<h1 data-design-id="heading">Hello <b>there</b></h1>')
  a,b=sp['logo']; self.assertEqual(self.DOC[a:b],'<img data-design-id="logo" src="a.png">'); self.assertTrue(sp['card'][0]<sp['heading'][0]<sp['heading'][1]<sp['card'][1])
 def test_diff_attributes_change_to_innermost_element(self):
  after=self.DOC.replace('Hello','Howdy'); d=s.diff_regions(self.DOC,after); self.assertEqual(d,{'elements':['heading'],'outside':False})
  d=s.diff_regions(self.DOC,self.DOC.replace('Foot','Changed footer')); self.assertEqual(d,{'elements':[],'outside':True})
  self.assertEqual(s.diff_regions(self.DOC,self.DOC.replace('Body','New body text')),{'elements':['card'],'outside':False})
  self.assertEqual(s.diff_regions(self.DOC,self.DOC.replace('>Go<','>Go now<'))['elements'],['cta']); self.assertEqual(s.diff_regions(self.DOC,self.DOC),{'elements':[],'outside':False})
 def test_region_revise_edits_only_the_pinned_element(self):
  out=s.region_revise(self.DOC,{'heading':'Shorter'}); self.assertEqual(s.diff_regions(self.DOC,out),{'elements':['heading'],'outside':False}); self.assertIn('Shorter',out)
  self.assertIsNone(s.region_revise(self.DOC,{'missing':'x'}))
 def revision_with(self,element_id,scope_mode='region'):
  parent=self.variant(); pin=s.save('annotation',dict(id=s.uid(),variant_id=parent['id'],screen='0',x=.5,y=.2,comment='Tighten the heading',element_id=element_id,status='open',selected=True,created_at=time.time()))
  with patch.object(s.threading,'Thread'): job=s.launch(dict(board_id=self.b['id'],parent_id=parent['id'],annotation_ids=[pin['id']],runner_ids=[parent['runner_id']],scope_mode=scope_mode),'revise_board',self.p['id'])[0]
  with patch.object(s.subprocess,'run',return_value=None),patch.object(s.time,'sleep'): s.execute(s.get(job['id']))
  return job,s.get(s.get(job['id'])['variant_id'])
 def test_region_scope_limits_change_and_passes_check(self):
  job,child=self.revision_with('heading'); self.assertEqual(job['scope'],{'0':{'mode':'region','elements':['heading']}}); self.assertIn('change ONLY the element',job['instruction'])
  self.assertEqual(child['changed_regions'],{'0':{'elements':['heading'],'outside':False}})
  chk=[x for x in child['validation'] if x['check'].startswith('Revision scope')]; self.assertEqual([x['outcome'] for x in chk],['pass'])
 def test_unanchored_pin_or_screen_mode_revises_whole_screen(self):
  job,child=self.revision_with(None); self.assertEqual(job['scope'],{'0':{'mode':'screen'}}); self.assertIn('may change the whole screen',job['instruction']); self.assertIn('explanation',child['changed_regions']['0']['elements'])
  job2,_=self.revision_with('heading','screen'); self.assertEqual(job2['scope'],{'0':{'mode':'screen'}})
 def test_scope_violation_is_a_deterministic_failure(self):
  real=s.region_revise
  def sloppy(html_text,notes): return real(html_text,notes).replace('Illustrative prototype only','Rewritten footer')
  with patch.object(jobs,'region_revise',side_effect=sloppy): job,child=self.revision_with('heading')
  chk=[x for x in child['validation'] if x['check'].startswith('Revision scope')]; self.assertEqual([x['outcome'] for x in chk],['fail']); self.assertIn('page content',chk[0]['evidence']); self.assertTrue(child['changed_regions']['0']['outside'])

 # --- blind A/B
 def blind_board(self):
  s.set_blind(self.b['id'],True)
  with patch.object(s.threading,'Thread'): jobs=s.launch(dict(board_id=self.b['id'],brief='b',runner_ids=[r['id'] for r in s.allof('runner')[:2]]),'generate_board',self.p['id'])
  with patch.object(s.subprocess,'run',return_value=None),patch.object(s.time,'sleep'):
   for j in jobs: s.execute(s.get(j['id']))
  return [s.get(s.get(j['id'])['variant_id']) for j in jobs]
 def api_state(self): return s.mask_state({k:s.allof(k) for k in ['project','context','board','variant','job','research','annotation','runner','prototype','reference']})
 def test_blind_labels_are_random_distinct_and_state_hides_identity(self):
  vs=self.blind_board(); labels=[v['blind_label'] for v in vs]; self.assertEqual(len(set(labels)),2)
  st=self.api_state(); import json; blob=json.dumps([st['variant'],st['job']])
  for v in st['variant']: self.assertEqual(v['runner_name'],'Option '+v['blind_label']); self.assertIsNone(v['runner_id']); self.assertNotIn('style',v)
  self.assertNotIn('Studio A',blob); self.assertNotIn('Studio B',blob); self.assertNotIn('Template demo',blob)
  self.assertEqual(s.get(vs[0]['id'])['runner_name'] in ('Studio A','Studio B'),True,'stored data is untouched')
 def test_revision_in_blind_mode_works_without_runner_id_and_inherits_label(self):
  vs=self.blind_board(); parent=vs[0]; pin=s.save('annotation',dict(id=s.uid(),variant_id=parent['id'],screen='0',x=.5,y=.2,comment='c',element_id='heading',status='open',selected=True,created_at=time.time()))
  with patch.object(s.threading,'Thread'): job=s.launch(dict(board_id=self.b['id'],parent_id=parent['id'],annotation_ids=[pin['id']]),'revise_board',self.p['id'])[0]
  self.assertEqual(job['runner_id'],parent['runner_id'])
  with patch.object(s.subprocess,'run',return_value=None),patch.object(s.time,'sleep'): s.execute(s.get(job['id']))
  self.assertEqual(s.get(s.get(job['id'])['variant_id'])['blind_label'],parent['blind_label'])
 def test_choice_reveals_and_records_result_and_cannot_reblind(self):
  vs=self.blind_board(); b=s.blind_choice(self.b['id'],vs[1]['id'],'cleaner'); self.assertTrue(b['revealed']); self.assertEqual(b['blind_choice']['runner_name'],vs[1]['runner_name']); self.assertEqual(b['blind_choice']['label'],vs[1]['blind_label'])
  st=self.api_state(); self.assertIn(vs[1]['runner_name'],[v['runner_name'] for v in st['variant']])
  with self.assertRaises(ValueError): s.set_blind(self.b['id'],True)
  with self.assertRaises(ValueError): s.blind_choice(self.b['id'],vs[0]['id'])
 def test_approving_in_blind_mode_ends_blindness_with_a_recorded_choice(self):
  vs=self.blind_board(); res=s.approve(vs[0]['id']); b=s.get(self.b['id']); self.assertTrue(b['revealed']); self.assertEqual(b['blind_choice']['reason'],'Approved'); self.assertEqual(b['blind_choice']['variant_id'],vs[0]['id'])
 def test_enabling_blind_labels_existing_variants_and_lineage(self):
  parent=self.variant(); pin=s.save('annotation',dict(id=s.uid(),variant_id=parent['id'],screen='0',x=.5,y=.2,comment='c',element_id='heading',status='open',selected=True,created_at=time.time()))
  child=s.get(self.run_job('revise_board',1,parent['id'],[pin])['variant_id']); s.set_blind(self.b['id'],True)
  self.assertTrue(s.get(parent['id'])['blind_label']); self.assertEqual(s.get(child['id'])['blind_label'],s.get(parent['id'])['blind_label'])
 def test_reveal_without_choice(self):
  self.blind_board(); b=s.blind_choice(self.b['id']); self.assertTrue(b['revealed']); self.assertIsNone(b['blind_choice'])

 # --- cross-variant mixing
 def two(self):
  a=self.variant(runner=0); b=self.variant(runner=1); return a,b
 def test_mix_composes_screens_from_different_versions_and_validates(self):
  a,b=self.two(); m=s.mix_variants(self.b['id'],{'0':a['id'],'1':b['id'],'2':a['id']})
  self.assertEqual(m['kind'],'mix'); self.assertEqual([x['id'] for x in m['manifest']['screens']],['0','1','2']); self.assertEqual([p['variant_id'] for p in m['mix_sources']],[a['id'],b['id'],a['id']])
  folder=s.STORE/'variants'/m['id']; self.assertEqual((folder/'screens/1.html').read_text(),(s.STORE/'variants'/b['id']/'screens/1.html').read_text()); self.assertEqual((folder/'screens/0.html').read_text(),(s.STORE/'variants'/a['id']/'screens/0.html').read_text())
  self.assertTrue(any(c['check']=='Mixed provenance' and c['outcome']=='review' for c in m['validation'])); self.assertFalse(any(c['outcome']=='fail' and c['check']=='Package & local navigation' for c in m['validation']))
  self.assertEqual({(e['from'],e['to']) for e in m['manifest']['edges']}>= {('0','1'),('1','2')},True)
  self.assertEqual(s.get(m['id'])['mix_sources'],m['mix_sources']); self.assertEqual(s.get(m['job_id'])['type'],'mix_board'); self.assertIn('Mix of',m['runner_name'])
 def test_mix_isolates_colliding_assets_and_rewrites_links(self):
  a,b=self.two()
  for v,color in ((a,'red'),(b,'blue')):
   f=s.STORE/'variants'/v['id']; (f/'assets').mkdir(exist_ok=True); (f/'assets/theme.css').write_text('p{color:%s}'%color); (f/'styles.css').write_text('b{color:%s}'%color)
   for sid in ('0','1','2'):
    page=f/'screens'/f'{sid}.html'; page.write_text(page.read_text()+'<link rel="stylesheet" href="../assets/theme.css"><link rel="stylesheet" href="../styles.css">')
  m=s.mix_variants(self.b['id'],{'0':a['id'],'1':b['id'],'2':b['id']}); folder=s.STORE/'variants'/m['id']
  p0=(folder/'screens/0.html').read_text(); p1=(folder/'screens/1.html').read_text()
  self.assertIn(f'../shared/{a["id"]}/assets/theme.css',p0); self.assertIn(f'../shared/{b["id"]}/styles.css',p1); self.assertNotIn('"../assets/theme.css"',p0)
  self.assertEqual((folder/'shared'/a['id']/'assets/theme.css').read_text(),'p{color:red}'); self.assertEqual((folder/'shared'/b['id']/'assets/theme.css').read_text(),'p{color:blue}')
  self.assertIn('1.html',p0)
  s.validate(folder,m['manifest'],[])
 def test_mix_requires_every_screen_and_two_sources_from_this_board(self):
  a,b=self.two()
  with self.assertRaises(ValueError): s.mix_variants(self.b['id'],{'0':a['id'],'1':b['id']})
  with self.assertRaises(ValueError): s.mix_variants(self.b['id'],{'0':a['id'],'1':a['id'],'2':a['id']})
  other=s.save('board',dict(id=s.uid(),project_id=self.p['id'],title='x',brief='b',screens=['A','B','C'])); 
  with self.assertRaises(ValueError): s.mix_variants(other['id'],{'0':a['id'],'1':b['id'],'2':a['id']})
  self.assertEqual([p for p in (s.STORE/'variants').iterdir() if p.name not in (a['id'],b['id'])],[],'failed mixes leave nothing behind')
 def test_mix_in_blind_mode_does_not_leak_names(self):
  vs=self.blind_board(); m=s.mix_variants(self.b['id'],{'0':vs[0]['id'],'1':vs[1]['id'],'2':vs[0]['id']})
  import json; blob=json.dumps(self.api_state()['variant']); self.assertIn('Option',m['runner_name']); self.assertNotIn('Studio A',blob); self.assertNotIn('Studio B',blob)
 def test_mix_can_be_approved_and_revised_with_explicit_runner(self):
  a,b=self.two(); m=s.mix_variants(self.b['id'],{'0':a['id'],'1':b['id'],'2':a['id']}); r=s.approve(m['id']); self.assertTrue((s.STORE/'prototypes'/r['prototype']['id']/'screens/1.html').is_file())
  pin=s.save('annotation',dict(id=s.uid(),variant_id=m['id'],screen='0',x=.5,y=.2,comment='c',element_id='heading',status='open',selected=True,created_at=time.time()))
  with self.assertRaisesRegex(ValueError,'Choose a runner'): s.launch(dict(board_id=self.b['id'],parent_id=m['id'],annotation_ids=[pin['id']]),'revise_board',self.p['id'])
  with patch.object(s.threading,'Thread'): job=s.launch(dict(board_id=self.b['id'],parent_id=m['id'],annotation_ids=[pin['id']],runner_ids=[a['runner_id']]),'revise_board',self.p['id'])[0]
  with patch.object(s.subprocess,'run',return_value=None),patch.object(s.time,'sleep'): s.execute(s.get(job['id']))
  child=s.get(s.get(job['id'])['variant_id']); self.assertEqual(child['parent_id'],m['id'])

 # --- limitation fixes
 def test_blind_withholds_runner_revealing_job_files_until_reveal(self):
  vs=self.blind_board(); jid=vs[0]['job_id']
  for name in ('envelope.json','runner.log','output/manifest.json'): self.assertTrue(s.hidden_job_file(f'/assets/jobs/{jid}/{name}'),name)
  self.assertFalse(s.hidden_job_file(f'/assets/jobs/{jid}/TASK.md')); self.assertFalse(s.hidden_job_file(f'/assets/jobs/{jid}/references/x.png')); self.assertFalse(s.hidden_job_file('/assets/variants/abc/manifest.json'))
  s.blind_choice(self.b['id']); self.assertFalse(s.hidden_job_file(f'/assets/jobs/{jid}/envelope.json'))
 def test_stamp_anchors_adds_ids_only_when_missing_and_keeps_markup_valid(self):
  doc='<html><body><main><h1>Title</h1><p class="x">Text <a href="1.html">next</a></p><img src="a.png"/><input name="n"><ul><li>One</li></ul></main></body></html>'
  out,n=s.stamp_anchors(doc); self.assertEqual(n,8); self.assertIn('<h1 data-design-id="auto-h1-1">',out); self.assertIn('<img src="a.png" data-design-id="auto-img-1"/>',out); self.assertIn('<input name="n" data-design-id="auto-input-1">',out)
  import re as _re; self.assertEqual(_re.sub(r' data-design-id="[^"]+"','',out),doc); self.assertEqual(set(s.element_spans(out)),{'auto-main-1','auto-h1-1','auto-p-1','auto-a-1','auto-img-1','auto-input-1','auto-ul-1','auto-li-1'})
  again,m=s.stamp_anchors(out); self.assertEqual((again,m),(out,0)); self.assertEqual(s.diff_regions(out,out.replace('Title','New')),{'elements':['auto-h1-1'],'outside':False})
 def test_agent_output_without_anchors_gets_them_and_is_flagged(self):
  script='mkdir -p output/screens; for i in 0 1 2; do n=$(( (i+1) % 3 )); printf "<!doctype html><html><body><h1>Screen $i</h1><p>copy</p><a href=\\"$n.html\\">go</a></body></html>" > output/screens/$i.html; done; printf \'{"schema_version":"1.0","kind":"clickthrough-static","board_id":"b","start_screen_id":"0","screens":[{"id":"0","title":"A","file":"screens/0.html"},{"id":"1","title":"B","file":"screens/1.html"},{"id":"2","title":"C","file":"screens/2.html"}],"edges":[]}\' > output/manifest.json'
  r=self.cli_runner('/bin/sh',['-c',script]); j=dict(id=s.uid(),project_id=self.p['id'],type='generate_board',runner_id=r['id'],context=s.get(self.p['context_id']),board_id=self.b['id'],parent_id=None,annotations=[],brief='b',instruction='t',events=[],status='queued',created_at=time.time()); s.save('job',j)
  with patch.object(s.subprocess,'run',return_value=None): s.execute(j)
  j2=s.get(j['id']); self.assertEqual(j2['status'],'succeeded',j2['events'][-1]['message']); v=s.get(j2['variant_id'])
  self.assertEqual(v['anchors_added'],{'0':3,'1':3,'2':3}); self.assertIn('data-design-id',(s.STORE/'variants'/v['id']/'screens/0.html').read_text())
  self.assertTrue(any(c['check'].startswith('Annotation anchors added') and c['outcome']=='review' for c in v['validation'])); self.assertTrue(any(c['check'].startswith('Stable targets') and c['outcome']=='pass' for c in v['validation']))
 def test_mix_consistency_flags_different_fonts_and_never_claims_a_pass(self):
  a,b=self.two()
  for v,font in ((a,'Georgia'),(b,'Inter')):
   for sid in '012':
    f=s.STORE/'variants'/v['id']/'screens'/f'{sid}.html'; f.write_text(f.read_text()+f'<style>body{{font-family:{font},serif}}</style>')
  m=s.mix_variants(self.b['id'],{'0':a['id'],'1':b['id'],'2':a['id']}); c=[x for x in m['validation'] if x['check'].startswith('Cross-screen consistency')][0]
  self.assertEqual(c['outcome'],'review'); self.assertIn('different primary fonts: georgia, inter',c['evidence']); self.assertIn('not a visual review',c['evidence'])

 # --- auto retry
 def run_worker_job(self,runner,**kw):
  j=dict(id=s.uid(),project_id=self.p['id'],type='generate_board',runner_id=runner['id'],context=s.get(self.p['context_id']),board_id=self.b['id'],parent_id=None,annotations=[],brief='b',instruction='t',events=[],status='queued',created_at=time.time(),**kw); s.save('job',j); return j
 def test_auto_retry_creates_linked_attempts_up_to_the_limit(self):
  self.drain(); r=self.cli_runner('/bin/false',[]); r['auto_retries']=2; s.save('runner',r); j=self.run_worker_job(r)
  with patch.object(s.threading,'Timer') as timer:
   s.execute(j); s.maybe_auto_retry(j['id']); second=s.get(s.get(j['id'])['retried_by']); self.assertEqual((second['attempt'],second['auto_retry'],second['retry_of']),(2,True,j['id'])); self.assertIn('attempt 2 of 3',second['events'][0]['message']); self.assertEqual(timer.call_args[0][0],2)
   s.execute(second); s.maybe_auto_retry(second['id']); third=s.get(s.get(second['id'])['retried_by']); self.assertEqual(third['attempt'],3)
   s.execute(third); s.maybe_auto_retry(third['id']); self.assertIsNone(s.get(third['id']).get('retried_by'),'stops at the limit')
 def test_no_auto_retry_by_default_after_cancel_or_for_success(self):
  r=self.cli_runner('/bin/false',[]); j=self.run_worker_job(r); s.execute(j); s.maybe_auto_retry(j['id']); self.assertIsNone(s.get(j['id']).get('retried_by'))
  r2=self.cli_runner('/bin/false',[]); r2['auto_retries']=3; s.save('runner',r2); c=self.run_worker_job(r2); s.CANCEL.add(c['id']); s.execute(c); s.maybe_auto_retry(c['id']); self.assertEqual(s.get(c['id'])['status'],'cancelled'); self.assertIsNone(s.get(c['id']).get('retried_by'))
  ok=self.run_worker_job(s.allof('runner')[0]); 
  with patch.object(s.subprocess,'run',return_value=None),patch.object(s.time,'sleep'): s.execute(ok)
  s.maybe_auto_retry(ok['id']); self.assertEqual(s.get(ok['id'])['status'],'succeeded'); self.assertIsNone(s.get(ok['id']).get('retried_by'))
 # --- sandbox
 def sandboxed(self,script,**cfg):
  r=self.cli_runner('/bin/sh',['-c',script]); r.update(sandbox='bwrap',sandbox_ro=[],sandbox_rw=[],**cfg); s.save('runner',r); j=self.run_worker_job(r); s.execute(j); return s.get(j['id']),(s.STORE/'jobs'/j['id'])
 def test_sandbox_command_shape(self):
  from unittest.mock import patch as p
  with p.object(jobs,'bwrap_ok',return_value=True):
   cmd=s.sandbox_command(dict(sandbox_ro=['/opt/x'],sandbox_rw=['~/.agent']),['agent','run'],s.STORE/'jobs'/'j1')
  self.assertEqual(cmd[0],'bwrap'); self.assertIn('--tmpfs',cmd); self.assertEqual(cmd[-2:],['agent','run']); self.assertIn('--unshare-pid',cmd); self.assertIn('--die-with-parent',cmd)
  self.assertIn('--ro-bind-try',cmd); self.assertIn('--bind-try',cmd); self.assertNotIn('--unshare-net',cmd)
  with p.object(jobs,'bwrap_ok',return_value=False), self.assertRaisesRegex(ValueError,'bubblewrap'): s.sandbox_command({},['x'],s.STORE)
 @unittest.skipUnless(s.bwrap_ok(),'bubblewrap not usable here')
 def test_sandbox_hides_storage_and_home_and_blocks_writes_but_keeps_job_dir(self):
  other=s.STORE/'jobs'/'other'; other.mkdir(parents=True); (other/'secret.txt').write_text('TOPSECRET'); (s.STORE/'studio-note.txt').write_text('NOTE')
  script='echo ok > output_marker.txt; cat '+str(other/'secret.txt')+' 2>&1; cat '+str(s.STORE/'studio-note.txt')+' 2>&1; echo HOME_ENTRIES=$(ls -A "$HOME" | wc -l); touch /etc/sandbox-write 2>&1; touch /usr/sandbox-write 2>&1; echo NET=$(cat /proc/net/dev | wc -l)'
  j,folder=self.sandboxed(script); log=(folder/'runner.log').read_text()
  self.assertTrue((folder/'output_marker.txt').is_file(),'job dir stays writable'); self.assertNotIn('TOPSECRET',log); self.assertNotIn('NOTE',log); self.assertIn('No such file',log); self.assertIn('HOME_ENTRIES=0',log); self.assertEqual(log.count('Read-only file system'),2)
  self.assertNotIn('NET=0',log)
 @unittest.skipUnless(s.bwrap_ok(),'bubblewrap not usable here')
 def test_sandbox_rebinds_only_listed_paths(self):
  import tempfile as tf, os
  with tf.TemporaryDirectory(dir=os.path.expanduser('~')) as d:
   (Path(d)/'auth.txt').write_text('TOKEN-DATA')
   r=self.cli_runner('/bin/sh',['-c','cat '+d+'/auth.txt; ls -A "$HOME" | wc -l']); r.update(sandbox='bwrap',sandbox_ro=[d],sandbox_rw=[]); s.save('runner',r); j=self.run_worker_job(r); s.execute(j)
   log=(s.STORE/'jobs'/j['id']/'runner.log').read_text(); self.assertIn('TOKEN-DATA',log)

 # --- share links
 def shared(self,hours=None):
  v=self.variant(); proto=s.approve(v['id'])['prototype']; proto=s.share_create(proto['id'],hours); return proto,proto['shares'][-1]['token']
 def serve(self):
  from http.server import ThreadingHTTPServer; srv=ThreadingHTTPServer(('127.0.0.1',0),s.ShareHandler); import threading as th; th.Thread(target=srv.serve_forever,daemon=True).start(); return srv,f'http://127.0.0.1:{srv.server_address[1]}'
 def get_url(self,url):
  import urllib.request, urllib.error
  try:
   with urllib.request.urlopen(url) as r: return r.status,r.read(),dict(r.headers)
  except urllib.error.HTTPError as e: return e.code,e.read(),dict(e.headers)
 def test_share_serves_only_the_prototype_bundle_read_only(self):
  proto,token=self.shared(); srv,base=self.serve()
  try:
   st,body,h=self.get_url(f'{base}/s/{token}/'); self.assertEqual(st,200); self.assertIn(b'Read-only share',body); self.assertEqual(h['Cache-Control'],'no-store'); self.assertIn('noindex',h['X-Robots-Tag'])
   st,body,_=self.get_url(f'{base}/s/{token}/meta.json'); meta=json.loads(body); self.assertEqual(len(meta['screens']),3); self.assertNotIn('runner',body.decode().lower()); self.assertNotIn('context',body.decode().lower())
   st,body,h=self.get_url(f'{base}/s/{token}/f/screens/0.html'); self.assertEqual(st,200); self.assertIn(b'nav.js',body); self.assertIn("connect-src 'self'",h['Content-Security-Policy'])
   st,_,_=self.get_url(f'{base}/s/{token}/f/_player/nav.js'); self.assertEqual(st,200)
   for bad in ('/api/state','/assets/jobs/x/envelope.json','/','/s/short/','/projects',f'/s/{token}/f/../../studio.db',f'/s/{token}/f/%2e%2e/%2e%2e/studio.db',f'/s/{token}/f//etc/passwd',f'/s/{token}/api/state'):
    self.assertIn(self.get_url(base+bad)[0],(404,410),bad)
   import urllib.request; req=urllib.request.Request(f'{base}/s/{token}/',method='POST',data=b'x')
   with self.assertRaises(Exception): urllib.request.urlopen(req)
  finally: srv.shutdown()
 def test_share_tokens_expire_revoke_and_do_not_cross_prototypes(self):
  proto,token=self.shared(hours=1); self.assertEqual(s.share_find(token)[0]['id'],proto['id'])
  p=s.get(proto['id']); p['shares'][-1]['expires_at']=time.time()-5; s.save('prototype',p); self.assertEqual(s.share_find(token),(None,'expired'))
  proto2,t2=self.shared(); s.share_revoke(proto2['id'],t2); self.assertEqual(s.share_find(t2),(None,'revoked')); self.assertEqual(s.share_find('nope'+'x'*20),(None,'unknown'))
  srv,base=self.serve()
  try: self.assertEqual(self.get_url(f'{base}/s/{token}/')[0],410); self.assertEqual(self.get_url(f'{base}/s/{t2}/f/screens/0.html')[0],410)
  finally: srv.shutdown()
 def test_share_validation(self):
  v=self.variant()
  with self.assertRaises(ValueError): s.share_create(v['id'],1)
  proto=s.approve(v['id'])['prototype']
  for bad in (0,-1,24*30+1,'x'):
   with self.assertRaises(ValueError): s.share_create(proto['id'],bad)
  self.assertIsNone(s.share_create(proto['id'],None)['shares'][-1]['expires_at']); self.assertGreater(len(s.share_create(proto['id'],24)['shares'][-1]['token']),20)

 # --- untrusted research output
 SUP=[dict(id='user_source_1',title='Lore note',text='abc',verification='source_supplied_by_user')]
 def test_research_output_is_sanitized_and_provenance_is_assigned_by_the_studio(self):
  raw={'brief':'x','job_id':'y','id':'z','schema_version':'1.0','limitations':['No web access'],'sources':[{'id':'user_source_1','verification':'verified_source'},{'id':'a1','title':'Made up','url':'https://example.org/x','verification':'verified_source'},{'id':'a2','url':'javascript:alert(1)'}],
   'findings':[{'id':'f1','title':'Backed by user note','detail':'d','source_ids':['user_source_1'],'verification':'verified_source','selected':True},{'id':'f2','title':'Backed by agent source','source_ids':['a1'],'verification':'verified_source'},{'id':'f3','title':'No source','source_ids':['ghost']},{'title':''},'junk',{'id':'f1','title':'Duplicate id','source_ids':[]}]}
  out=s.sanitize_research(raw,self.SUP); by={f['title']:f for f in out['findings']}
  self.assertEqual(set(out),{'summary','findings','sources','limitations'}); self.assertEqual(len(out['findings']),4)
  self.assertEqual(by['Backed by user note']['verification'],'source_supplied_by_user'); self.assertEqual(by['Backed by agent source']['verification'],'unverified_claim'); self.assertEqual(by['No source']['verification'],'unverified_claim'); self.assertEqual(by['No source']['source_ids'],[])
  self.assertTrue(all(f['selected'] is False for f in out['findings'])); self.assertTrue(all(f['verification']!='verified_source' for f in out['findings'])); self.assertEqual(len({f['id'] for f in out['findings']}),4)
  agent=[x for x in out['sources'] if x['id']=='a1'][0]; self.assertEqual(agent['verification'],'unverified_claim'); self.assertIn('did not retrieve',agent['note']); self.assertIsNone([x for x in out['sources'] if x['id']=='a2'][0]['url']); self.assertEqual(out['sources'][0]['verification'],'source_supplied_by_user'); self.assertEqual(out['limitations'],['No web access'])
  for bad in ({},{'findings':'x'},[]):
   with self.assertRaises(ValueError): s.sanitize_research(bad,[])
 def test_real_agent_research_json_with_extra_keys_no_longer_crashes_the_job(self):
  script="mkdir -p output; printf '%s' '{\"brief\":\"x\",\"project_id\":\"p\",\"findings\":[{\"id\":\"f1\",\"title\":\"T\",\"detail\":\"D\",\"source_ids\":[\"user_source_1\"]}],\"sources\":[]}' > output/research.json"
  r=self.cli_runner('/bin/sh',['-c',script]); j=dict(id=s.uid(),project_id=self.p['id'],type='research',runner_id=r['id'],context=s.get(self.p['context_id']),brief='the real brief',sources=self.SUP,instruction='t',events=[],status='queued',created_at=time.time()); s.save('job',j); s.execute(j)
  self.assertEqual(s.get(j['id'])['status'],'succeeded',s.get(j['id'])['events'][-1]['message']); rec=[x for x in s.allof('research') if x['job_id']==j['id']][0]; self.assertEqual(rec['brief'],'the real brief'); self.assertEqual(rec['project_id'],self.p['id']); self.assertEqual(rec['findings'][0]['verification'],'source_supplied_by_user')
 def test_supplied_sources_get_ids_at_launch(self):
  with patch.object(s.threading,'Thread'): j=s.launch(dict(brief='q',sources=[{'title':'a','text':'t'},{'title':'b','text':'u'}],runner_ids=[s.allof('runner')[0]['id']]),'research',self.p['id'])[0]
  self.assertEqual([x['id'] for x in j['sources']],['user_source_1','user_source_2']); self.assertIn('user_source_1',j['instruction']); self.assertIn('do not invent sources',j['instruction'])

 def test_every_prototype_frame_lets_generated_forms_fire_submit_events_but_never_post(self):
  # Agent-built flows use <form> + a JS submit handler; a sandbox without allow-forms never fires that event.
  root=Path(__file__).resolve().parents[1]
  for rel in ['apps/web/views.js','apps/web/app.js']+[str(f.relative_to(root)) for f in sorted((root/'apps/api').glob('*.py'))]:
   text=(root/rel).read_text(); frames=re.findall(r'sandbox="([^"]*)"',text)
   for f in frames:
    if 'allow-scripts' in f: self.assertIn('allow-forms',f,rel); self.assertNotIn('allow-same-origin',f,rel)
  self.assertIn('allow-forms',s.SHARE_PLAYER); self.assertIn("form-action 'none'",(root/'apps/api/web.py').read_text())

if __name__=='__main__': unittest.main()
