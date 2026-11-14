import sys, tempfile, unittest, time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/api'))
import server as s, boards

class ProfilesTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.old=s.STORE; s.STORE=Path(self.tmp.name); s.seed(); self.p=s.allof('project')[0]; self.b=s.allof('board')[0]; self.r=[r['id'] for r in s.allof('runner')]
 def tearDown(self): s.STORE=self.old; self.tmp.cleanup()
 def proj(self): return s.get(self.p['id'])
 def launch(self,**kw):
  with patch.object(boards,'enqueue'): return s.launch(dict(board_id=self.b['id'],brief='b',runner_ids=self.r[:2],**kw),'generate_board',self.p['id'])
 def run_job(self,j):
  with patch.object(s.subprocess,'run',return_value=None),patch.object(s.time,'sleep'): s.execute(j)
  return s.get(s.get(j['id'])['variant_id'])
 def new_profile(self,name='Experimental',**kw):
  p=s.profile_create(self.p['id'],name,**kw); return next(x for x in p['profiles'] if x['name']==name)
 def test_legacy_project_has_one_implicit_main_profile(self):
  p=self.proj(); self.assertEqual([x['name'] for x in s.profiles_of(p)],['Main']); self.assertEqual(s.active_profile_id(p),'main'); self.assertEqual(s.current_context(p['id'])['id'],p['context_id'])
 def test_create_copies_current_version_with_its_own_history(self):
  main_ctx=s.get(self.proj()['context_id']); pr=self.new_profile(); c=s.get(pr['context_id'])
  self.assertEqual(c['profile_id'],pr['id']); self.assertEqual(c['version'],1); self.assertEqual(c['markdown'],main_ctx['markdown']); self.assertEqual([r['id'] for r in c['rules']],[r['id'] for r in main_ctx['rules']])
  self.assertEqual(self.proj()['context_id'],main_ctx['id'],'default profile and project.context_id unchanged')
  rules=[dict(id='X-1',description='Experimental rule')]; c2=s.context(self.p['id'],dict(profile_id=pr['id'],rules=rules,markdown='# Wild',tokens={'accent':'#f00'}))
  self.assertEqual(c2['version'],2); self.assertEqual(c2['parent_id'],c['id']); self.assertEqual(self.proj()['context_id'],main_ctx['id']); self.assertEqual(len(s.get(main_ctx['id'])['rules']),len(main_ctx['rules']))
  self.assertEqual(s.context(self.p['id'],dict(profile_id=pr['id'],rules=rules,markdown='# Wild',tokens={'accent':'#f00'}))['id'],c2['id'],'unchanged save is deduped per profile')
 def test_blank_profile_starts_from_defaults(self):
  pr=self.new_profile('Blank',copy_from='blank'); self.assertEqual(s.get(pr['context_id'])['markdown'],s.GUIDE)
 def test_names_validated_and_unique(self):
  self.new_profile()
  for bad in ('','  ','x'*41,'experimental','main'):
   with self.assertRaises(ValueError): s.profile_create(self.p['id'],bad)
 def test_default_profile_switch_updates_project_context_and_cannot_delete_default(self):
  pr=self.new_profile(); s.context(self.p['id'],dict(profile_id=pr['id'],markdown='# Wild')); cur=s.get(pr['id'] if False else self.proj()['profiles'][1]['context_id'])
  with self.assertRaises(ValueError): s.profile_delete(self.p['id'],'main')
  s.profile_update(self.p['id'],pr['id'],make_default=True); p=self.proj(); self.assertEqual(p['context_id'],cur['id']); self.assertEqual(s.active_profile_id(p),pr['id'])
  s.context(self.p['id'],dict(profile_id=pr['id'],markdown='# Wilder')); self.assertEqual(self.proj()['context_id'],s.current_context(self.p['id'])['id'])
  s.context(self.p['id'],dict(profile_id='main',markdown='# Main edit')); self.assertEqual(s.active_profile_id(self.proj()),pr['id']); self.assertNotEqual(self.proj()['context_id'],s.current_context(self.p['id'],'main')['id'])
  s.profile_delete(self.p['id'],'main'); self.assertEqual([x['name'] for x in s.profiles_of(self.proj())],['Experimental'])
  with self.assertRaises(ValueError): s.profile_delete(self.p['id'],pr['id'])
 def test_rename(self):
  pr=self.new_profile(); s.profile_update(self.p['id'],pr['id'],name='Loose'); self.assertEqual([x['name'] for x in s.profiles_of(self.proj())],['Main','Loose'])
  with self.assertRaises(ValueError): s.profile_update(self.p['id'],pr['id'],name='main')
 def test_generate_uses_requested_profile_and_defaults_to_active(self):
  pr=self.new_profile(); s.context(self.p['id'],dict(profile_id=pr['id'],markdown='# EXPERIMENTAL TONE',rules=[dict(id='ONLY-1',description='Only rule')]))
  a=self.launch()[0]; b=self.launch(profile_id=pr['id'])[0]
  self.assertEqual(a['context']['profile_id'],'main'); self.assertEqual(b['context']['profile_id'],pr['id']); self.assertEqual(b['context']['profile_name'],'Experimental')
  self.assertIn('EXPERIMENTAL TONE',b['instruction']); self.assertNotIn('EXPERIMENTAL TONE',a['instruction']); self.assertEqual([r['id'] for r in b['context']['effective_rules']],['ONLY-1']); self.assertNotEqual(a['input_hash'],b['input_hash'])
  with self.assertRaises(ValueError): self.launch(profile_id='nope')
 def test_variant_records_profile_and_revision_keeps_it(self):
  pr=self.new_profile(); v=self.run_job(self.launch(profile_id=pr['id'])[0]); self.assertEqual(v['profile_id'],pr['id']); self.assertEqual(v['profile_name'],'Experimental')
  a=s.save('annotation',dict(id=s.uid(),variant_id=v['id'],screen='0',x=.5,y=.2,comment='c',status='open',selected=True,created_at=time.time()))
  with patch.object(boards,'enqueue'): rj=s.launch(dict(board_id=self.b['id'],parent_id=v['id'],annotation_ids=[a['id']],runner_ids=self.r[:1]),'revise_board',self.p['id'])[0]
  self.assertEqual(rj['context']['profile_id'],pr['id'])
  s.profile_update(self.p['id'],'main',make_default=True); s.profile_delete(self.p['id'],pr['id'])
  a2=s.save('annotation',dict(id=s.uid(),variant_id=v['id'],screen='1',x=.5,y=.2,comment='d',status='open',selected=True,created_at=time.time()))
  with patch.object(boards,'enqueue'): rj2=s.launch(dict(board_id=self.b['id'],parent_id=v['id'],annotation_ids=[a2['id']],runner_ids=self.r[:1]),'revise_board',self.p['id'])[0]
  self.assertEqual(rj2['context']['profile_id'],'main','deleted profile falls back to the default')
 def test_free_run_rule_breaks_use_the_runs_own_profile(self):
  pr=self.new_profile(); s.context(self.p['id'],dict(profile_id=pr['id'],rules=[dict(id='ONLY-1',description='Only rule')]))
  v=self.run_job(self.launch(profile_id=pr['id'],overrides=dict(free='open'))[0]); self.assertEqual(v['rule_breaks']['context_id'],s.current_context(self.p['id'],pr['id'])['id'])
  self.assertTrue(any(c['check']=='Only rule' for c in v['rule_breaks']['results']))
 def test_style_apply_goes_to_the_variants_profile(self):
  pr=self.new_profile(); main_before=self.proj()['context_id']; c=s.apply_style(self.p['id'],{'brand-x':'#123456'},pr['id'])
  self.assertEqual(c['profile_id'],pr['id']); self.assertEqual(self.proj()['context_id'],main_before); self.assertEqual(s.current_context(self.p['id'],pr['id'])['tokens']['brand-x'],'#123456'); self.assertNotIn('brand-x',s.current_context(self.p['id'],'main')['tokens'])
 def test_conflict_preview_uses_profile(self):
  pr=self.new_profile(); s.context(self.p['id'],dict(profile_id=pr['id'],rules=[dict(id='CTA-001',description='Up to three equal actions allowed')]))
  w_main=s.conflict_preview(self.p['id'],'Show three equal action buttons'); w_exp=s.conflict_preview(self.p['id'],'Show three equal action buttons',None,None,pr['id'])
  self.assertTrue(w_main); self.assertFalse([x for x in w_exp if x['topic']=='actions' and x['id']=='CTA-001' and 'one primary' in x['message'].lower()])
if __name__=='__main__': unittest.main()
