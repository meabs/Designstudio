import sys, tempfile, unittest, json, copy
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/api'))
import server as s
import local_agents

class StudioTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.old=s.STORE; s.STORE=Path(self.tmp.name); s.seed(); self.p=s.allof('project')[0]; self.ctx=s.get(self.p['context_id']); self.b=s.allof('board')[0]
 def tearDown(self): s.STORE=self.old; self.tmp.cleanup()
 def job(self,runner=0,parent=None,annotations=[]):
  j=dict(id=s.uid(),project_id=self.p['id'],type='revise_board' if parent else 'generate_board',runner_id=s.allof('runner')[runner]['id'],context=self.ctx,board_id=self.b['id'],parent_id=parent,annotations=annotations,brief=self.b['brief'],instruction='test',events=[])
  # Screenshot processes are integration-tested separately; no browser is needed for contracts.
  with patch.object(s.subprocess,'run',return_value=None),patch.object(s.time,'sleep'): s.execute(j)
  return s.get(j['id'])
 def test_stable_hash(self): self.assertEqual(s.digest({'a':1,'b':2}),s.digest({'b':2,'a':1}))
 def test_context_immutable(self):
  changed=s.context(self.p['id'],{'markdown':'New guide'}); self.assertNotEqual(changed['hash'],self.ctx['hash']); self.assertEqual(s.get(self.ctx['id'])['markdown'],s.GUIDE)
 def test_precedence(self):
  rules=[dict(s.RULES[0],scope=x,description=x) for x in ['workspace','project','job']]; c=s.context(self.p['id'],{'rules':rules}); self.assertEqual(c['effective_rules'][0]['description'],'job'); self.assertEqual(len(c['overrides']),2)
 def test_tokens_reject_nested(self):
  with self.assertRaises(ValueError): s.context(self.p['id'],{'tokens':{'color':{}}})
 def test_path_traversal(self):
  for p in ['../secret','/etc/passwd','screens/../../oops']:
   with self.assertRaises(ValueError): s.safe_path(s.STORE,p)
 def test_symlink(self):
  (s.STORE/'link').symlink_to('/etc/passwd')
  with self.assertRaises(ValueError): s.safe_path(s.STORE,'link')
 def test_generation_and_failure_evidence(self):
  j=self.job(1); self.assertEqual(j['status'],'succeeded'); v=s.get(j['variant_id']); self.assertTrue(any(x['outcome']=='fail' for x in v['validation'])); self.assertTrue(any(x['outcome']=='review' for x in v['validation']))
 def test_guidance_affects_output(self):
  a=s.render_screen('Eligibility',0,self.b['screens'],self.ctx,'a'); self.ctx['tokens']['accent']='#000001'; b=s.render_screen('Eligibility',0,self.b['screens'],self.ctx,'a'); self.assertNotEqual(a,b)
 def test_revision_preserves_parent_and_untargeted(self):
  parent=s.get(self.job(1)['variant_id']); path=s.STORE/'variants'/parent['id']; original=(path/'screens/0.html').read_bytes(); child=s.get(self.job(1,parent['id'],[{'screen':'0','comment':'Move explanatory text below heading'}])['variant_id']); other=s.STORE/'variants'/child['id']; self.assertEqual(original,(path/'screens/0.html').read_bytes()); self.assertNotEqual(original,(other/'screens/0.html').read_bytes()); self.assertEqual((path/'screens/1.html').read_bytes(),(other/'screens/1.html').read_bytes()); self.assertEqual(child['parent_id'],parent['id'])
 def test_missing_instrumentation_unknown(self):
  j=self.job();v=s.get(j['variant_id']);folder=s.STORE/'variants'/v['id']; f=folder/'screens/0.html';f.write_text(f.read_text().replace('data-role="primary-action"',''))
  self.assertEqual(s.validate(folder,v['manifest'],self.ctx['effective_rules'])[0]['outcome'],'not_assessable')
 def test_external_assets_rejected(self):
  v=s.get(self.job()['variant_id']);folder=s.STORE/'variants'/v['id'];f=folder/'screens/0.html';f.write_text(f.read_text()+'<img src="https://external.test/image">')
  with self.assertRaises(ValueError):s.validate(folder,v['manifest'],self.ctx['effective_rules'])
 def test_local_adapter_uses_selected_model(self):
  with patch.object(local_agents,'discover',return_value=[{'id':'codex','name':'Codex','supported':True,'executable':'/usr/bin/codex'}]):
   c=local_agents.configuration('codex','chosen-model');self.assertIn('chosen-model',c['args']);self.assertNotIn('--dangerously-bypass-approvals-and-sandbox',c['args'])
 def test_codex_confinement_follows_the_studio_sandbox_setting(self):
  with patch.object(local_agents,'discover',return_value=[{'id':'codex','name':'Codex','supported':True,'executable':'/usr/bin/codex'}]):
   on=local_agents.configuration('codex','',sandbox=True); off=local_agents.configuration('codex','',sandbox=False)
  self.assertIn('danger-full-access',on['args']); self.assertEqual(on['sandbox'],'bwrap'); self.assertIn('workspace-write',off['args']); self.assertNotIn('danger-full-access',off['args']); self.assertIsNone(off['sandbox'])
 def test_copilot_adapter_is_non_interactive_and_follows_the_sandbox_setting(self):
  fake=[{'id':'copilot','name':'GitHub Copilot','supported':True,'executable':'/usr/bin/copilot'}]
  with patch.object(local_agents,'discover',return_value=fake):
   on=local_agents.configuration('copilot','claude-haiku-4.5',sandbox=True); off=local_agents.configuration('copilot','',sandbox=False)
  for c in (on,off):
   self.assertEqual(c['args'][:2],['--prompt','{prompt}']); self.assertIn('--no-ask-user',c['args']); self.assertNotIn('--allow-all',c['args']); self.assertNotIn('--yolo',c['args']); self.assertNotIn('--allow-all-urls',c['args'])
  self.assertIn('--allow-all-tools',on['args']); self.assertIn('--model',on['args']); self.assertEqual(on['sandbox'],'bwrap'); self.assertIn('~/.copilot',on['sandbox_rw'])
  self.assertEqual([a for a in off['args'] if a.startswith('--allow')],['--allow-tool=write']); self.assertNotIn('--model',off['args']); self.assertIsNone(off['sandbox'])
  self.assertIn('COPILOT_GITHUB_TOKEN',on['env_allowlist'])
 def test_web_args_per_agent_and_off_by_default(self):
  fake=[{'id':a,'name':a,'supported':True,'executable':'/usr/bin/'+a} for a in ('codex','claude','copilot')]
  with patch.object(local_agents,'discover',return_value=fake):
   cfg={a:local_agents.configuration(a,'',sandbox=sb) for a in ('codex','claude','copilot') for sb in (True,)}
   off={a:local_agents.configuration(a,'',sandbox=False) for a in ('claude',)}
  for a,c in cfg.items(): self.assertFalse([x for x in c['args'] if 'search' in x.lower() or 'url' in x.lower() or 'WebFetch' in x], 'no web access by default: '+a)
  self.assertEqual(local_agents.web_args(cfg['codex'],cfg['codex']['args'])[0],'--search'); self.assertEqual(local_agents.web_args(cfg['codex'],cfg['codex']['args'])[1],'exec')
  cl=local_agents.web_args(cfg['claude'],cfg['claude']['args']); self.assertEqual([a for a in cl if a.startswith('--allowedTools')][0].count('WebSearch'),1); self.assertIn('Bash(python3 *)',[a for a in cl if a.startswith('--allowedTools')][0])
  cl2=local_agents.web_args(off['claude'],off['claude']['args']); self.assertEqual([a for a in cl2 if a.startswith('--allowedTools')],['--allowedTools=WebSearch,WebFetch'])
  self.assertIn('--allow-all-urls',local_agents.web_args(cfg['copilot'],cfg['copilot']['args']))
  with self.assertRaises(ValueError): local_agents.web_args({'agent':'opencode'},[])
 def test_web_flag_only_applies_to_research_jobs(self):
  p=s.allof('project')[0]; r=s.allof('runner')[0]
  with patch.object(s,'enqueue'):
   a=s.launch(dict(brief='What do people expect?',runner_ids=[r['id']],web=True),'research',p['id'])[0]
   b=s.launch(dict(brief='What do people expect?',runner_ids=[r['id']]),'research',p['id'])[0]
   g=s.launch(dict(brief='x',board_id=s.allof('board')[0]['id'],runner_ids=[r['id']],web=True),'generate_board',p['id'])[0]
  self.assertTrue(a['web']); self.assertIn('WEB SEARCH IS ENABLED',a['instruction']); self.assertFalse(b['web']); self.assertNotIn('WEB SEARCH IS ENABLED',b['instruction'])
  self.assertFalse(g['web']); self.assertNotIn('WEB SEARCH IS ENABLED',g['instruction'])
 def test_cited_urls_are_checked_without_touching_private_addresses(self):
  import research
  src=[dict(id='a',url='https://ok.example/x',verification='unverified_claim'),dict(id='b',url='https://gone.example/y',verification='unverified_claim'),dict(id='c',url='https://supplied.example',verification='source_supplied_by_user'),dict(id='d',title='no url',verification='unverified_claim')]
  fnd=[dict(id='f1',source_ids=['b']),dict(id='f2',source_ids=['a']),dict(id='f3',source_ids=['c'])]
  seen=[]
  def fake(u): seen.append(u); return 'not_found' if 'gone' in u else 'reachable'
  research.check_urls(src,fnd,fetch=fake)
  self.assertEqual(sorted(seen),['https://gone.example/y','https://ok.example/x'],'only agent-reported URLs are fetched')
  self.assertEqual([s.get('reachable') for s in src],['reachable','not_found',None,None]); self.assertEqual(fnd[0]['broken_sources'],['b']); self.assertNotIn('broken_sources',fnd[1])
  for u in ['http://127.0.0.1:1/','http://localhost/','http://10.0.0.5/','http://169.254.169.254/latest/','http://[::1]/','file:///etc/passwd','ftp://x/y']: self.assertEqual(research.fetch_status(u),'skipped',u)
 def test_no_installed_agent(self):
  with patch.object(local_agents,'discover',return_value=[]):
   with self.assertRaises(ValueError):local_agents.configuration('codex','model')
 def test_runner_failure_honest(self):
  runner=s.allof('runner')[0];runner.update(type='cli',executable='/nonexistent',args=[]);s.save('runner',runner);self.assertEqual(self.job(next(i for i,r in enumerate(s.allof('runner')) if r['id']==runner['id']))['status'],'failed')

if __name__=='__main__':unittest.main()
