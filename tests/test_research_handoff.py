import sys, tempfile, unittest, copy
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/api'))
import server as s

class HandoffTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.old=s.STORE;s.STORE=Path(self.tmp.name);s.seed();self.p=s.allof('project')[0]
  self.r=s.save('research',dict(id=s.uid(),project_id=self.p['id'],brief='Make eligibility clear',findings=[dict(id='first',title='Explain why',detail='Explain sensitive questions',verification='unverified_claim',source_ids=['src'],selected=False),dict(id='second',title='Progress',detail='Show progress',verification='unverified_claim',source_ids=[],selected=True)],sources=[dict(id='src',title='User excerpt',text='Authorised source text',verification='source_supplied_by_user')]))
 def tearDown(self):s.STORE=self.old;self.tmp.cleanup()
 def board(self,**extra):return s.create_board(dict(project_id=self.p['id'],title='From research',brief=self.r['brief'],screens=['Eligibility','Details'],research_id=self.r['id'],finding_ids=['first'],**extra))
 def test_findings_and_provenance_snapshot_survive_selection_change(self):
  b=self.board();self.r['findings'][0]['detail']='Changed later';self.r['findings'][0]['selected']=True;s.save('research',self.r)
  self.assertEqual(s.get(b['id'])['research_findings'][0]['detail'],'Explain sensitive questions')
  self.assertEqual(b['research_sources'][0]['text'],'Authorised source text')
 def test_every_runner_receives_board_findings_and_sources(self):
  b=self.board()
  with patch.object(s.threading,'Thread'):
   jobs=s.launch(dict(board_id=b['id'],brief=b['brief'],runner_ids=[r['id'] for r in s.allof('runner')]),'generate_board',self.p['id'])
  self.assertEqual(len(jobs),2);self.assertEqual(jobs[0]['input_hash'],jobs[1]['input_hash'])
  for j in jobs:
   self.assertEqual([f['id'] for f in j['findings']],['first'])
   self.assertEqual(j['sources'],b['research_sources']);self.assertIn('Authorised source text',j['instruction']);self.assertIn('unverified_claim',j['instruction'])
 def test_invalid_finding_rejected(self):
  with self.assertRaises(ValueError):s.create_board(dict(project_id=self.p['id'],screens=['One','Two'],research_id=self.r['id'],finding_ids=['missing']))
 def test_cross_project_research_rejected(self):
  p=s.project({'name':'Other'})
  with self.assertRaises(ValueError):s.create_board(dict(project_id=p['id'],screens=['One','Two'],research_id=self.r['id'],finding_ids=['first']))
 def test_pink_text_rule_changes_emitted_css_without_mutating_tokens(self):
  ctx=s.get(self.p['context_id']);ctx['effective_rules'].append(dict(id='PINK',description='use pink text',enabled=True))
  original=copy.deepcopy(ctx['tokens']);page=s.render_screen('Eligibility',0,['Eligibility','Details'],ctx,'a')
  self.assertIn('--ink:#db2777',page);self.assertIn('color:var(--ink',page);self.assertEqual(ctx['tokens'],original)
 def test_markdown_color_directive(self):
  ctx=s.get(self.p['context_id']);ctx['markdown']='Use blue text. Use pink buttons.'
  self.assertEqual(s.fixture_tokens(ctx)['ink'],'#2563eb');self.assertEqual(s.fixture_tokens(ctx)['accent'],'#db2777')
 def test_later_rule_directive_wins(self):
  ctx=s.get(self.p['context_id']);ctx['markdown']='Use blue text';ctx['effective_rules']=[dict(description='Use pink text')]
  self.assertEqual(s.fixture_tokens(ctx)['ink'],'#db2777')

 def test_negated_color_instruction_is_not_applied(self):
  ctx=s.get(self.p['context_id']);ctx['markdown']='Do not use pink text.'
  self.assertEqual(s.fixture_tokens(ctx)['ink'],ctx['tokens']['ink'])
