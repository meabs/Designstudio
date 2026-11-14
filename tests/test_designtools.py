import sys, tempfile, unittest, time
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/api'))
import server as s, boards, audit

class DesignToolsTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.old=s.STORE; s.STORE=Path(self.tmp.name)/'store'; s.STORE.mkdir(); s.seed(); self.p=s.allof('project')[0]; self.b=s.allof('board')[0]
  self.r=[r['id'] for r in s.allof('runner')]; self.docs=Path(self.tmp.name)/'docs'; self.docs.mkdir()
 def tearDown(self): s.STORE=self.old; self.tmp.cleanup()
 def launch(self,kind='generate_board',**kw):
  with patch.object(boards,'enqueue'): return s.launch(dict(board_id=self.b['id'],brief='b',runner_ids=self.r[:2],**kw),kind,self.p['id'])
 def run_job(self,j):
  with patch.object(s.subprocess,'run',return_value=None),patch.object(s.time,'sleep'): s.execute(j)
  return s.get(s.get(j['id'])['variant_id'])
 # spread
 def test_spread_gives_each_runner_a_different_direction_and_rotates(self):
  a=self.launch(spread=True); self.assertEqual(len({j['angle'] for j in a}),2)
  for j in a: self.assertIn('DIRECTION FOR THIS VARIANT',j['instruction']); self.assertIn(j['angle'],j['instruction'])
  self.assertEqual(len({j['input_hash'] for j in a}),2)
  b=self.launch(spread=True); self.assertNotEqual([j['angle'] for j in a],[j['angle'] for j in b])
  plain=self.launch(); self.assertTrue(all(not j['angle'] for j in plain)); self.assertNotIn('DIRECTION',plain[0]['instruction'])
 def test_pair_offset_gives_matching_directions(self):
  n=boards.spread_offset(self.b['id']); a=self.launch(spread=True,spread_offset=n); b=self.launch(spread=True,spread_offset=n,overrides=dict(free='open'))
  self.assertEqual([j['angle'] for j in a],[j['angle'] for j in b])
 # rule-break log
 def test_free_run_records_what_saved_rules_would_say(self):
  v=self.run_job(self.launch(overrides=dict(free='open'))[0]); rb=v['rule_breaks']
  self.assertTrue(rb['results']); self.assertEqual(rb['context_version'],s.get(self.p['context_id'])['version'])
  self.assertIsNone(self.run_job(self.launch()[0]).get('rule_breaks'))
 # states
 def test_states_revision_needs_no_pins_and_covers_every_screen(self):
  v=self.run_job(self.launch()[0])
  with patch.object(boards,'enqueue'): j=s.launch(dict(board_id=self.b['id'],parent_id=v['id'],states=True,runner_ids=self.r[:1]),'revise_board',self.p['id'])[0]
  self.assertEqual(len(j['annotations']),len(self.b['screens'])); self.assertIn('empty state',j['instruction']); self.assertEqual(s.allof('annotation'),[])
  rv=self.run_job(j); self.assertEqual(rv['parent_id'],v['id'])
 # decisions
 def test_decision_log(self):
  v=self.run_job(self.launch()[0]); w=self.run_job(self.launch()[1])
  s.set_aside(w['id'],'too busy'); s.approve(v['id'],'clearest first step')
  d=s.get(self.b['id'])['decisions']; self.assertEqual([(x['decision'],x['note']) for x in d],[('set_aside','too busy'),('approved','clearest first step')])
  with self.assertRaises(ValueError): s.set_aside(v['id'])
  with self.assertRaises(ValueError): s.record_decision(self.b['id'],v['id'],'bogus')
 def test_blind_board_hides_decisions_and_angles(self):
  s.set_blind(self.b['id'],True); j=self.launch(spread=True)[0]; v=self.run_job(j); s.set_aside(v['id'],'x')
  st=s.mask_state({k:[dict(x) for x in s.allof(k)] for k in ('board','variant','job','prototype')})
  self.assertTrue(all('decisions' not in b for b in st['board'])); self.assertTrue(all('angle' not in x for x in st['job']))
 # review folder + audit
 def folder(self):
  (self.docs/'legal.md').write_text('# Legal & compliance\n- [ ] Must include "Representative APR"\n- [ ] Never say "guaranteed approval"\n- [ ] Legal has signed off the footer wording\n- plain note without a verb\n')
  (self.docs/'a11y.md').write_text('## Accessibility\n- [ ] Every screen has a visible focus state\n')
  (self.docs/'big.md').write_text('x'*(audit.MAX_DOC_BYTES+10)); (self.docs/'link.md').symlink_to(self.docs/'legal.md')
 def test_review_folder_reads_markdown_safely_and_classifies(self):
  self.folder(); info=audit.read_review_folder(str(self.docs)); names={d['file'] for d in info['docs']}
  self.assertEqual(names,{'legal.md','a11y.md'}); self.assertEqual(len(info['skipped']),2)
  c={x['text']:x for x in next(d for d in info['docs'] if d['file']=='legal.md')['criteria']}
  self.assertEqual(c['Must include "Representative APR"']['kind'],'require'); self.assertEqual(c['Never say "guaranteed approval"']['kind'],'forbid')
  self.assertEqual(c['Legal has signed off the footer wording']['kind'],'review'); self.assertEqual(c['Legal has signed off the footer wording']['area'],'legal')
  self.assertEqual(audit.read_review_folder(str(self.docs/'nope'))['docs'],[]); self.assertTrue(audit.read_review_folder(str(self.docs/'nope'))['error'])
 def test_audit_runs_checks_and_document_criteria(self):
  self.folder(); p=s.get(self.p['id']); p['review_folder']=str(self.docs); s.save('project',p)
  v=self.run_job(self.launch()[0]); a=s.audit_variant(v['id']); by={f['check']:f for f in a['findings']}
  self.assertEqual(by['Page language declared (WCAG 3.1.1)']['outcome'],'pass')
  self.assertTrue(any(f['check'].startswith('Text contrast') for f in a['findings']))
  req=next(f for f in a['findings'] if f['check']=='Must include "Representative APR"'); self.assertEqual(req['outcome'],'fail'); self.assertEqual(req['source'],'legal.md:2')
  self.assertEqual(next(f for f in a['findings'] if f['check'].startswith('Never say'))['outcome'],'pass')
  self.assertEqual(next(f for f in a['findings'] if f['check'].startswith('Legal has signed'))['outcome'],'review')
  self.assertEqual(sum(a['counts'].values()),len(a['findings'])); self.assertEqual(len(a['docs']),2); self.assertEqual(len(s.get(v['id'])['audits']),1)
  s.audit_review(v['id'],a['id'],req['index'],'accepted','known gap'); self.assertEqual(s.get(v['id'])['audits'][0]['findings'][req['index']]['review']['decision'],'accepted')
  with self.assertRaises(ValueError): s.audit_review(v['id'],a['id'],999,'accepted')
 def test_audit_without_folder_still_does_accessibility(self):
  v=self.run_job(self.launch()[0]); a=s.audit_variant(v['id']); self.assertEqual(a['docs'],[]); self.assertTrue(all(f['area']=='accessibility' for f in a['findings']))
 def test_audit_finds_real_problems(self):
  html='<html><head><style>body{color:#999;background:#fff}button{height:30px;font-size:10px}</style></head><body><h1>A</h1><h3>B</h3><img src="x.png"><input type="text"><button></button><a href="#">click here</a></body></html>'
  res,_,_=audit.audit_screen(html,{}); by={r['check']:r for r in res}
  for k in ('Page language declared (WCAG 3.1.1)','Page title (WCAG 2.4.2)','Responsive viewport declared','One main heading, no skipped levels (WCAG 1.3.1)','Images have alternative text (WCAG 1.1.1)','Form fields have labels (WCAG 3.3.2 / 4.1.2)','Buttons and links have a name (WCAG 4.1.2)','Text contrast, minimum 4.5:1 (WCAG 1.4.3)','Tap targets, 44px recommended'): self.assertEqual(by[k]['outcome'],'fail',k)
  self.assertEqual(by['Text is not smaller than 12px']['outcome'],'review'); self.assertEqual(by['Link text describes its destination (WCAG 2.4.4)']['outcome'],'review')
 def test_contrast_maths_and_vars(self):
  self.assertAlmostEqual(audit.contrast((0,0,0),(255,255,255)),21,1); self.assertEqual(audit.parse_color('var(--ink,#111)',{'--ink':'#ffffff'}),(255,255,255)); self.assertEqual(audit.parse_color('var(--x,#abc)',{}),(170,187,204))
  ok='<html lang="en"><head><title>t</title><meta name="viewport" content="width=device-width"><style>body{color:#111;background:#fff}</style></head><body><h1>A</h1><label>Name <input></label></body></html>'
  by={r['check']:r['outcome'] for r in audit.audit_screen(ok,{})[0]}; self.assertNotIn('fail',by.values())
 # style extraction
 def test_extract_and_apply_style_creates_new_guideline_version(self):
  v=self.run_job(self.launch()[0]); ex=s.extract_style(v['id']); self.assertTrue(any(x['kind']=='color' for x in ex)); n=len(s.allof('context'))
  c=s.apply_style(self.p['id'],{'brand-blue':'#2563eb'}); self.assertEqual(c['tokens']['brand-blue'],'#2563eb'); self.assertEqual(len(s.allof('context')),n+1); self.assertEqual(s.get(self.p['id'])['context_id'],c['id'])
  for bad in ({'Bad Name':'#fff'},{'ok':'<script>'},{'ok':5}):
   with self.assertRaises(ValueError): s.apply_style(self.p['id'],bad)
 # agent reading of documents
 def doc_variant(self):
  self.folder(); p=s.get(self.p['id']); p['review_folder']=str(self.docs); s.save('project',p); return self.run_job(self.launch()[0])
 def test_doc_review_stages_inputs_and_fixture_reports_unclear(self):
  v=self.doc_variant()
  with patch.object(audit,'enqueue',create=True), patch('jobs.enqueue') as enq: j=s.launch_doc_review(v['id'],self.r[0])
  enq.assert_called_once(); out=s.STORE/'jobs'/j['id']
  self.assertTrue((out/'docs'/'legal.md').is_file()); self.assertTrue((out/'package'/'manifest.json').is_file())
  self.assertEqual([c['text'] for c in j['criteria']],['Every screen has a visible focus state','Legal has signed off the footer wording']); self.assertIn('Criteria:',j['instruction']); self.assertEqual(j['type'],'audit_review'); self.assertNotIn('variant_id',j)
  with patch.object(s.subprocess,'run',return_value=None),patch.object(s.time,'sleep'): s.execute(j)
  self.assertEqual(s.get(j['id'])['status'],'succeeded'); dr=s.get(v['id'])['doc_reviews'][0]
  self.assertEqual(dr['counts'],{'meets':0,'fails':0,'unclear':2}); self.assertTrue(all(f['label']=='agent_opinion' for f in dr['findings'])); self.assertIn('fixture runner cannot read',dr['findings'][0]['evidence'])
 def test_doc_review_sanitises_agent_output(self):
  import json
  v=self.doc_variant()
  with patch('jobs.enqueue'): j=s.launch_doc_review(v['id'],self.r[0])
  out=s.STORE/'jobs'/j['id']; (out/'output').mkdir(exist_ok=True)
  (out/'output'/'audit.json').write_text(json.dumps(dict(summary='ok',findings=[dict(criterion_id='c1',outcome='meets',screen_ids=['0',1],evidence='Footer says X'),dict(criterion_id='c1',outcome='fails'),dict(criterion_id='zzz',outcome='meets'),dict(criterion_id='c2',outcome='verified!!')],limitations='static only')))
  audit.finish_doc_review(j,out,'cli'); dr=s.get(v['id'])['doc_reviews'][-1]
  by={f['criterion_id']:f for f in dr['findings']}; self.assertEqual(by['c1']['outcome'],'meets'); self.assertEqual(by['c1']['screen_ids'],['0','1']); self.assertEqual(by['c2']['outcome'],'unclear'); self.assertEqual(len(dr['findings']),2); self.assertEqual(dr['limitations'],['static only'])
  (out/'output'/'audit.json').write_text('not json')
  with self.assertRaises(ValueError): audit.finish_doc_review(j,out,'cli')
  (out/'output'/'audit.json').unlink()
  with self.assertRaises(ValueError): audit.finish_doc_review(j,out,'cli')
 def test_doc_review_needs_folder_and_criteria(self):
  v=self.run_job(self.launch()[0])
  with self.assertRaises(ValueError): s.launch_doc_review(v['id'],self.r[0])
  (self.docs/'only.md').write_text('# Legal\n- [ ] Must include "Representative APR"\n'); p=s.get(self.p['id']); p['review_folder']=str(self.docs); s.save('project',p)
  with patch('jobs.enqueue'),self.assertRaises(ValueError): s.launch_doc_review(v['id'],self.r[0])
if __name__=='__main__': unittest.main()
