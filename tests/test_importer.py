import sys, os, tempfile, unittest, json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/api'))
import importer as im

DESIGN='# Acme Design\n\nUse a calm, neutral financial-services style.\n\n## Principles\n- Explain why sensitive details are requested\n- CTA-001: One primary action per screen\n\n## Notes\n- Plain bullet about the logo\n- Never use red for errors alone\n\n```css\n:root { --brand-teal: #0f766e; }\n```\n'
RULES='# Rules\n- [ ] **COPY-002** Headlines must be under 8 words\n- Avoid jargon\n- ok\n'
class ImporterTest(unittest.TestCase):
 def parse(self,**files): return im.parse_files([dict(name=k.replace('__','/'),text=v) for k,v in files.items()])
 def test_design_file_is_prose_and_rules_files_stay_out(self):
  r=self.parse(**{'DESIGN.md':DESIGN,'rules.md':RULES}); d={x['file']:x for x in r['docs']}
  self.assertTrue(d['DESIGN.md']['use']); self.assertFalse(d['rules.md']['use']); self.assertEqual(d['rules.md']['kind'],'rules'); self.assertEqual(d['DESIGN.md']['kind'],'design')
 def test_rules_ids_severity_sources_and_dedupe(self):
  r=self.parse(**{'DESIGN.md':DESIGN,'rules.md':RULES,'copy.md':'# Copy\n- Explain why sensitive details are requested\n'}); by={x['description']:x for x in r['rules']}
  self.assertEqual(by['One primary action per screen']['id'],'CTA-001'); self.assertEqual(by['Headlines must be under 8 words']['id'],'COPY-002'); self.assertEqual(by['Headlines must be under 8 words']['severity'],'error')
  self.assertEqual(by['Avoid jargon']['severity'],'warning'); self.assertIsNone(by['Avoid jargon']['id']); self.assertNotIn('ok',by)
  self.assertNotIn('Plain bullet about the logo',by); self.assertIn('Never use red for errors alone',by)
  self.assertEqual(sum(1 for x in r['rules'] if x['description']=='Explain why sensitive details are requested'),1)
  self.assertTrue(by['Avoid jargon']['source'].startswith('rules.md:'))
 def test_tokens_flat_nested_w3c_and_css(self):
  r=self.parse(**{'tokens.json':json.dumps({'accent':'#52614c','radius':8,'color':{'ink':{'$value':'#111'},'bg':{'value':'#fff','type':'color'}},'bad':'<x>','list':[1],'flag':True}),'theme.css':':root{--font-body: Inter, sans-serif; --space-1: 4px;}','DESIGN.md':DESIGN})
  t={x['name']:x['value'] for x in r['tokens']}
  self.assertEqual(t['accent'],'#52614c'); self.assertEqual(t['radius'],'8'); self.assertEqual(t['color-ink'],'#111'); self.assertEqual(t['color-bg'],'#fff'); self.assertEqual(t['font-body'],'Inter, sans-serif'); self.assertEqual(t['brand-teal'],'#0f766e')
  for k in ('bad','list','flag'): self.assertNotIn(k,t)
 def test_bad_inputs_are_skipped_not_fatal(self):
  r=self.parse(**{'x.txt':'hi','broken.json':'{','empty.json':'{"a":[1]}','big.md':'x'*(im.MAX_BYTES+1)}); self.assertEqual(r['docs'],[]); self.assertEqual(len(r['skipped']),4)
 def test_folder_scan_is_bounded_and_read_only(self):
  with tempfile.TemporaryDirectory() as t:
   t=Path(t).resolve(); os.environ['STUDIO_FOLDER_ROOTS']=str(t); self.addCleanup(os.environ.pop,'STUDIO_FOLDER_ROOTS',None); (t/'DESIGN.md').write_text(DESIGN); (t/'sub').mkdir(); (t/'sub'/'rules.md').write_text(RULES); (t/'.hidden').mkdir(); (t/'.hidden'/'secret.md').write_text('# x\n- must hide this one'); (t/'link.md').symlink_to(t/'DESIGN.md')
   r=im.read_folder(str(t)); names={d['file'] for d in r['docs']}
   self.assertEqual(names,{'DESIGN.md',str(Path('sub')/'rules.md')}); self.assertTrue(any('symlink' in s for s in r['skipped'])); self.assertEqual(r['folder'],str(t.resolve()))
   with self.assertRaises(ValueError): im.read_folder(str(t/'nope'))
   with self.assertRaises(ValueError): im.read_folder('')
 def test_duplicate_rule_keeps_the_copy_with_an_id(self):
  r=self.parse(**{'DESIGN.md':'# D\n\n## Principles\n- Explain why sensitive details are requested\n','rules.md':'# Rules\n- [ ] **COPY-001** Explain why sensitive details are requested\n'})
  self.assertEqual([(x['id'],x['description']) for x in r['rules']],[('COPY-001','Explain why sensitive details are requested')])
if __name__=='__main__': unittest.main()

class SafetyTest(unittest.TestCase):
 def setUp(self): self.t=tempfile.TemporaryDirectory(); self.root=Path(self.t.name).resolve(); self.addCleanup(self.t.cleanup); self.addCleanup(os.environ.pop,'STUDIO_FOLDER_ROOTS',None)
 def test_folders_outside_the_allowlist_are_refused_and_nothing_is_read(self):
  os.environ['STUDIO_FOLDER_ROOTS']=str(self.root/'allowed'); (self.root/'allowed').mkdir(); (self.root/'secret').mkdir(); (self.root/'secret'/'tokens.json').write_text('{"password":"hunter2hunter2"}')
  with self.assertRaises(ValueError) as e: im.read_folder(str(self.root/'secret'))
  self.assertIn('outside',str(e.exception)); self.assertNotIn('hunter2',str(e.exception))
  (self.root/'allowed'/'ok').mkdir(); (self.root/'allowed'/'ok'/'DESIGN.md').write_text('# D\n- must be calm\n'); self.assertEqual(len(im.read_folder(str(self.root/'allowed'/'ok'))['docs']),1)
 def test_symlink_out_of_the_allowlist_and_hidden_folders_are_refused(self):
  os.environ['STUDIO_FOLDER_ROOTS']=str(self.root/'allowed'); (self.root/'allowed').mkdir(); (self.root/'outside').mkdir(); (self.root/'allowed'/'link').symlink_to(self.root/'outside'); (self.root/'allowed'/'.ssh').mkdir()
  for p in ('link','.ssh'):
   with self.assertRaises(ValueError): im.read_folder(str(self.root/'allowed'/p))
 def test_default_allowlist_is_the_home_folder(self):
  os.environ.pop('STUDIO_FOLDER_ROOTS',None)
  with self.assertRaises(ValueError): im.read_folder('/etc')
 def test_review_folder_reader_applies_the_same_allowlist(self):
  import audit; os.environ['STUDIO_FOLDER_ROOTS']=str(self.root/'allowed'); (self.root/'allowed').mkdir(); (self.root/'x').mkdir(); (self.root/'x'/'a.md').write_text('# A\n- [ ] Must include "Foo bar"\n')
  r=audit.read_review_folder(str(self.root/'x')); self.assertEqual(r['docs'],[]); self.assertIn('outside',r['error'])
 def test_rules_json_is_imported_in_list_and_object_shapes(self):
  lst=json.dumps([dict(id='COPY-9',description='Explain why we ask',severity='error'),dict(description='Avoid jargon'),dict(id='bad id!',description='Keep it short')])
  r=im.parse_files([dict(name='rules.json',text=lst)]); by={x['description']:x for x in r['rules']}
  self.assertEqual(by['Explain why we ask']['id'],'COPY-9'); self.assertEqual(by['Explain why we ask']['severity'],'error'); self.assertIsNone(by['Avoid jargon']['id']); self.assertIsNone(by['Keep it short']['id']); self.assertEqual(r['tokens'],[])
  obj=json.dumps(dict(rules=[dict(id='A-1',description='Be calm')],tokens=dict(accent='#123456')))
  r=im.parse_files([dict(name='guidelines/rules.json',text=obj)]); self.assertEqual([x['id'] for x in r['rules']],['A-1']); self.assertEqual([(t['name'],t['value']) for t in r['tokens']],[('accent','#123456')])
  r=im.parse_files([dict(name='tokens.json',text='{"accent":"#123456"}')]); self.assertEqual(r['rules'],[]); self.assertEqual(len(r['tokens']),1)
 def test_model_ids_cannot_inject_arguments(self):
  import local_agents as la
  for bad in ('--dangerously-skip-permissions','-x','a b','a;b','$(x)'):
   with self.assertRaises(ValueError): la.configuration('claude',bad)

class ChromeTest(unittest.TestCase):
 def test_a_hung_chrome_is_killed_with_its_whole_process_group(self):
  import jobs, subprocess, time, shutil
  from unittest.mock import patch
  pids=[]; real=subprocess.Popen
  def fake(cmd,**kw):
   p=real(['sh','-c','sleep 300 & echo $! > /tmp/_chrome_child; sleep 300'],**{k:v for k,v in kw.items()}); pids.append(p.pid); return p
  with patch.object(jobs.subprocess,'Popen',side_effect=fake):
   t=time.time(); ok=jobs.chrome_screenshot('hangtest',Path('/tmp/x.html'),Path('/tmp/_nope.png'),timeout=1)
  self.assertFalse(ok); self.assertLess(time.time()-t,8)
  child=int(Path('/tmp/_chrome_child').read_text()); time.sleep(0.3)
  with self.assertRaises(ProcessLookupError): os.kill(child,0)
  with self.assertRaises(ProcessLookupError): os.kill(pids[0],0)
