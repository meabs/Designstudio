import sys, tempfile, unittest, json, io, zipfile, subprocess
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/api'))
import server as s, boards, assist
from handoff import build_handoff

class AssistTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.old=s.STORE; s.STORE=Path(self.tmp.name)/'store'; s.STORE.mkdir(); s.seed(); self.p=s.allof('project')[0]; self.b=s.allof('board')[0]
  self.r=[r['id'] for r in s.allof('runner')]
  self.cli=s.save('runner',dict(id='cli1',name='Agent',type='cli',executable='/bin/true',args=[],timeout=60,enabled=True))['id']
 def tearDown(self): s.STORE=self.old; self.tmp.cleanup()
 def variant(self,i=0):
  with patch.object(boards,'enqueue'): j=s.launch(dict(board_id=self.b['id'],brief='b',runner_ids=[self.r[i]]),'generate_board',self.p['id'])[0]
  with patch.object(s.subprocess,'run',return_value=None),patch.object(s.time,'sleep'): s.execute(j)
  return s.get(s.get(j['id'])['variant_id'])
 # default spread
 def test_spread_default_is_per_run_and_can_be_switched_off(self):
  with patch.object(boards,'enqueue'):
   on=s.launch(dict(board_id=self.b['id'],brief='b',runner_ids=self.r[:2]),'generate_board',self.p['id'])
   off=s.launch(dict(board_id=self.b['id'],brief='b',runner_ids=self.r[:2],spread=False),'generate_board',self.p['id'])
  self.assertTrue(all(j['angle'] for j in on)); self.assertTrue(all(not j['angle'] for j in off))
 # cut-off salvage
 def test_complete_output_survives_a_timeout_and_is_marked_cut_off(self):
  with patch.object(boards,'enqueue'): j=s.launch(dict(board_id=self.b['id'],brief='b',runner_ids=[self.cli]),'generate_board',self.p['id'])[0]
  def fake(command,out,timeout,job,runner=None):
   o=out/'output'; (o/'screens').mkdir(parents=True,exist_ok=True)
   n=len(self.b['screens']); m=dict(schema_version='1.0',kind='clickthrough-static',board_id=self.b['id'],start_screen_id='0',screens=[dict(id=str(i),title=t,file=f'screens/{i}.html',states=['default']) for i,t in enumerate(self.b['screens'])],edges=[dict({'from':str(i),'to':str(i+1),'trigger':'continue'}) for i in range(n-1)])
   (o/'manifest.json').write_text(json.dumps(m))
   for i in range(n): (o/'screens'/f'{i}.html').write_text('<!doctype html><title>x</title><h1 data-design-id="h">Hi</h1><a data-role="primary-action" href="#">Go</a>')
   raise subprocess.TimeoutExpired(command,timeout)
  with patch.object(s,'run_cli',fake,create=True),patch('jobs.run_cli',fake),patch.object(s.time,'sleep'),patch('jobs.chrome_screenshot',return_value=False): s.execute(j)
  self.assertEqual(s.get(j['id'])['status'],'succeeded'); v=s.get(s.get(j['id'])['variant_id']); self.assertTrue(v['cut_off'])
  self.assertIn('cut off',s.get(j['id'])['events'][-1]['message'])
 def test_incomplete_output_still_times_out(self):
  with patch.object(boards,'enqueue'): j=s.launch(dict(board_id=self.b['id'],brief='b',runner_ids=[self.cli]),'generate_board',self.p['id'])[0]
  def fake(command,out,timeout,job,runner=None): raise subprocess.TimeoutExpired(command,timeout)
  with patch('jobs.run_cli',fake),patch.object(s.time,'sleep'): s.execute(j)
  self.assertEqual(s.get(j['id'])['status'],'timed_out')
 # developer hand-off
 def test_handoff_is_a_clean_package_without_the_agent_name(self):
  v=self.variant(); name,data=build_handoff(v); z=zipfile.ZipFile(io.BytesIO(data)); names=z.namelist()
  base=name[:-4]; self.assertIn(f'{base}/site/index.html',names); self.assertIn(f'{base}/site/screens/0.html',names)
  for f in ('design/tokens.json','design/tokens.css','design/GUIDELINES.md','design/rules.json','README.md'): self.assertIn(f'{base}/{f}',names)
  self.assertFalse([n for n in names if 'thumbnails' in n or 'changes.json' in n])
  self.assertIn('--accent',z.read(f'{base}/design/tokens.css').decode()); self.assertNotIn(v['runner_name'],z.read(f'{base}/README.md').decode())
 # merge a part from another design
 def test_merge_stages_donor_and_scopes_to_one_screen(self):
  a=self.variant(0); b=self.variant(1)
  with patch.object(boards,'enqueue'): j=s.launch(dict(board_id=self.b['id'],parent_id=a['id'],runner_ids=[self.r[0]],brief='',merge=dict(donor_id=b['id'],screen='0',donor_screen='1',part='the summary table')),'revise_board',self.p['id'])[0]
  self.assertTrue((s.STORE/'jobs'/j['id']/'donor'/'manifest.json').is_file()); self.assertIn('MERGE TASK',j['instruction']); self.assertIn('the summary table',j['instruction'])
  self.assertEqual(list(j['scope']),['0']); self.assertEqual(j['scope']['0']['mode'],'screen')
  with self.assertRaises(ValueError): s.launch(dict(board_id=self.b['id'],parent_id=a['id'],runner_ids=[self.r[0]],merge=dict(donor_id=a['id'],screen='0',donor_screen='0',part='x')),'revise_board',self.p['id'])
  with self.assertRaises(ValueError): s.launch(dict(board_id=self.b['id'],parent_id=a['id'],runner_ids=[self.r[0]],merge=dict(donor_id=b['id'],screen='0',donor_screen='1',part=' ')),'revise_board',self.p['id'])
  with self.assertRaises(ValueError): s.launch(dict(board_id=self.b['id'],parent_id=a['id'],runner_ids=[self.r[0]],merge=dict(donor_id=b['id'],screen='9',donor_screen='1',part='x')),'revise_board',self.p['id'])
 # guidelines from a brief
 def test_guidelines_draft_needs_an_agent_and_a_real_brief(self):
  with self.assertRaises(ValueError): assist.launch_guidelines_draft(self.p['id'],self.cli,'too short')
  with self.assertRaises(ValueError): assist.launch_guidelines_draft(self.p['id'],self.r[0],'A long enough description of a company and its audience.')
 def test_guidelines_draft_is_sanitised_and_labelled(self):
  with patch('jobs.enqueue'): j=assist.launch_guidelines_draft(self.p['id'],self.cli,'Relay Ops sells IT agents to directors at mid-size firms.')
  out=s.STORE/'jobs'/j['id']; (out/'output').mkdir(exist_ok=True)
  (out/'output'/'draft.json').write_text(json.dumps(dict(markdown='# Guide\n- dark',tokens={'Accent Colour':'#4ade80','bad':'<script>','radius':10,'nested':{'a':1}},rules=[dict(id='CTA-001',description='One primary action',severity='error'),dict(id='CTA-001',description='Dup id'),dict(id='x y',description='Odd id'),dict(description=' ')],notes=['assumed dark'])))
  assist.finish_guidelines_draft(j,out); d=j['draft']
  self.assertEqual(d['tokens'],{'accent-colour':'#4ade80','radius':'10'}); self.assertEqual([r['id'] for r in d['rules']],['CTA-001','RULE-002','RULE-003']); self.assertEqual(d['label'],'agent_draft')
  (out/'output'/'draft.json').write_text('[]')
  with self.assertRaises(ValueError): assist.finish_guidelines_draft(j,out)
 def test_guidelines_draft_end_to_end_saves_nothing_to_the_project(self):
  before=len(s.allof('context'))
  with patch('jobs.enqueue'): j=assist.launch_guidelines_draft(self.p['id'],self.cli,'Relay Ops sells IT agents to directors at mid-size firms.')
  def fake(command,out,timeout,job,runner=None): (out/'output').mkdir(exist_ok=True); (out/'output'/'draft.json').write_text(json.dumps(dict(markdown='# G',tokens={'ink':'#111'},rules=[])))
  with patch('jobs.run_cli',fake),patch.object(s.time,'sleep'): s.execute(j)
  self.assertEqual(s.get(j['id'])['status'],'succeeded'); self.assertEqual(s.get(j['id'])['draft']['markdown'],'# G'); self.assertEqual(len(s.allof('context')),before)
 # ask about a pin
 def test_pin_ask_stages_package_and_stores_a_labelled_answer(self):
  v=self.variant()
  with patch('jobs.enqueue'): j=assist.launch_pin_ask(v['id'],'0','heading','Why is this so small?',self.cli)
  self.assertTrue((s.STORE/'jobs'/j['id']/'package'/'manifest.json').is_file()); self.assertIn('Do NOT change',j['instruction'])
  def fake(command,out,timeout,job,runner=None): (out/'output').mkdir(exist_ok=True); (out/'output'/'answer.json').write_text(json.dumps(dict(answer='It is 14px.',suggested_change='Use 18px',confidence='certain')))
  with patch('jobs.run_cli',fake),patch.object(s.time,'sleep'): s.execute(j)
  a=s.get(j['id'])['answer']; self.assertEqual(a['label'],'agent_opinion'); self.assertEqual(a['confidence'],'low'); self.assertEqual(s.get(v['id'])['manifest'],v['manifest'])
  with self.assertRaises(ValueError): assist.launch_pin_ask(v['id'],'9','x','Why?',self.cli)
  with self.assertRaises(ValueError): assist.launch_pin_ask(v['id'],'0','x','?',self.cli)
