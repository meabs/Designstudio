import sys, tempfile, unittest, time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/api'))
import server as s

class OverrideTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.old=s.STORE; s.STORE=Path(self.tmp.name); s.seed(); self.p=s.allof('project')[0]; self.b=s.allof('board')[0]
  self.r=[r['id'] for r in s.allof('runner')]
 def tearDown(self): s.STORE=self.old; self.tmp.cleanup()
 def launch(self,**kw):
  with patch.object(s,'enqueue'): return s.launch(dict(board_id=self.b['id'],brief='b',runner_ids=self.r[:2],**kw),'generate_board',self.p['id'])
 def test_overrides_stay_out_of_project_context(self):
  before=s.get(self.p['context_id']); jobs=self.launch(overrides=dict(rules=[dict(id='CTA-001',description='Up to three equal actions')],prose='Break the style guide.'))
  self.assertEqual(s.get(self.p['id'])['context_id'],before['id']); self.assertEqual(s.get(before['id'])['effective_rules'],before['effective_rules']); self.assertEqual(len(s.allof('context')),1)
  c=jobs[0]['context']; self.assertEqual(next(r for r in c['effective_rules'] if r['id']=='CTA-001')['description'],'Up to three equal actions'); self.assertNotEqual(c['hash'],before['hash'])
  self.assertTrue(any(o['id']=='CTA-001' for o in c['overrides']))
 def test_prose_in_instruction_and_shared_hash_for_all_runners(self):
  jobs=self.launch(overrides=dict(prose='EXPERIMENT: three doors'))
  for j in jobs: self.assertIn('RUN-ONLY EXPERIMENT BRIEF',j['instruction']); self.assertIn('EXPERIMENT: three doors',j['instruction']); self.assertIn('TAKES PRECEDENCE',j['instruction'])
  self.assertEqual(len({j['input_hash'] for j in jobs}),1)
  plain=self.launch(); self.assertNotEqual(plain[0]['input_hash'],jobs[0]['input_hash']); self.assertNotIn('RUN-ONLY',plain[0]['instruction'])
 def test_suspend_removes_rule_for_run_only(self):
  j=self.launch(overrides=dict(suspend=['CTA-001']))[0]
  self.assertNotIn('CTA-001',[r['id'] for r in j['context']['effective_rules']]); self.assertIn('CTA-001',[r['id'] for r in s.get(self.p['context_id'])['effective_rules']])
 def test_revision_inherits_parent_job_overrides(self):
  j=self.launch(overrides=dict(prose='keep going'))[0]
  with patch.object(s.subprocess,'run',return_value=None),patch.object(s.time,'sleep'): s.execute(j)
  v=s.get(s.get(j['id'])['variant_id']); a=s.save('annotation',dict(id=s.uid(),variant_id=v['id'],screen='0',x=.5,y=.2,comment='c',status='open',selected=True,created_at=time.time()))
  with patch.object(s,'enqueue'): rj=s.launch(dict(board_id=self.b['id'],parent_id=v['id'],annotation_ids=[a['id']],runner_ids=self.r[:1]),'revise_board',self.p['id'])[0]
  self.assertIn('keep going',rj['instruction'])
 def test_override_rule_keeps_deterministic_check(self):
  j=self.launch(overrides=dict(rules=[dict(id='CTA-001',description='Up to 3',verification='deterministic',check='primary_action_count',parameters={'max':3})]))[0]
  r=next(x for x in j['context']['effective_rules'] if x['id']=='CTA-001'); self.assertEqual(r['parameters'],{'max':3}); self.assertEqual(r['check'],'primary_action_count')
 def test_blank_overrides_are_ignored(self):
  j=self.launch(overrides=dict(rules=[dict(id='',description='x')],prose='  '))[0]; self.assertNotIn('run_overrides',j['context'])
 def test_conflict_preview(self):
  w=s.conflict_preview(self.p['id'],'Show three equal action buttons and a woodcut illustration')
  self.assertEqual({x['id'] for x in w if x['topic']=='actions'},{'CTA-001'}); self.assertTrue(w); self.assertFalse(s.conflict_preview(self.p['id'],'A calm form'))
  w2=s.conflict_preview(self.p['id'],'three equal actions',dict(rules=[dict(id='CTA-001',description='Up to three equal actions')])); self.assertTrue(all(x['overridden'] for x in w2 if x['id']=='CTA-001'))
 def test_voice_conflict_does_not_flag_copy_rule(self):
  ids={x['id'] for x in s.conflict_preview(self.p['id'],'Use a playful voice and humour')}; self.assertNotIn('COPY-001',ids)
 def test_report_parser(self):
  log='noise\nCreated the static package.\n\n**Not followed**\n- **Reference notes:** I ignored the woodcut mood note.\n- **Reference images:** I did not view them.\n- Placeholder 24h.\nSessionEnd hook [x] failed\n'
  r=s.parse_agent_report(log,True); self.assertFalse(r['viewed_references']); self.assertTrue(any('woodcut' in l for l in r['ignored'])); self.assertNotIn('SessionEnd',r['text'])
  self.assertIsNone(s.parse_agent_report('Created files.',True)['viewed_references']); self.assertIsNone(s.parse_agent_report('I did not view them',False)['viewed_references'])
  self.assertTrue(s.parse_agent_report('I viewed the reference images and used the palette.',True)['viewed_references'])
 def test_report_recorded_and_review_item_added(self):
  j=self.launch()[0]; runner=s.get(j['runner_id'])
  with patch.object(s.subprocess,'run',return_value=None),patch.object(s.time,'sleep'): s.execute(j)
  d=STORE=s.STORE/'jobs'/j['id']; d.mkdir(parents=True,exist_ok=True); (d/'runner.log').write_text('Done.\n- I ignored the brief request for three doors.\n')
  s.record_report(j); jd=s.get(j['id']); self.assertEqual(jd['agent_report']['ignored'],['I ignored the brief request for three doors.'])
  v=s.get(jd['variant_id']); self.assertTrue(any(c['outcome']=='review' and 'self-report' in c['check'] for c in v['validation']))
 def test_blind_masks_report(self):
  j=self.launch()[0]; jd=s.get(j['id']); jd['agent_report']=dict(text='x',ignored=[],viewed_references=None); s.save('job',jd); b=s.get(self.b['id']); b['blind']=True; s.save('board',b)
  st=s.mask_state({'board':[s.get(self.b['id'])],'variant':[],'job':[s.get(j['id'])],'prototype':[]}); self.assertNotIn('agent_report',st['job'][0])
if __name__=='__main__': unittest.main()
