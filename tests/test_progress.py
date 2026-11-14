import sys, tempfile, unittest, time, threading
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/api'))
import server as s

SCRIPT='mkdir -p output/screens; echo "agent: planning screens"; echo hi > output/screens/0.html; echo "tokens used"; echo "1,234"; sleep 3'

class ProgressTest(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory(); self.old=s.STORE; s.STORE=Path(self.tmp.name); s.seed(); self.p=s.allof('project')[0]; self.b=s.allof('board')[0]; s.CANCEL.clear()
  r=s.save('runner',dict(id=s.uid(),name='cli',type='cli',executable='/bin/sh',args=['-c',SCRIPT],timeout=30,enabled=True))
  self.j=dict(id=s.uid(),project_id=self.p['id'],type='generate_board',runner_id=r['id'],context=s.get(self.p['context_id']),board_id=self.b['id'],parent_id=None,annotations=[],brief='b',instruction='t',events=[],status='queued',created_at=time.time()); s.save('job',self.j)
 def tearDown(self): s.STORE=self.old; self.tmp.cleanup()
 def start(self):
  t=threading.Thread(target=s.execute,args=(self.j,)); t.start(); time.sleep(1.2); return t
 def test_progress_shows_files_log_and_idle_while_running_then_usage_after(self):
  t=self.start(); pr=s.job_progress(self.j['id'])
  self.assertEqual(pr['status'],'running'); self.assertGreater(pr['elapsed_s'],0.5); self.assertEqual(pr['screens_written'],1); self.assertEqual(pr['screens_expected'],len(self.b['screens']))
  self.assertIn('planning screens',pr['log_tail']); self.assertIn('screens/0.html',[f['name'] for f in pr['files']]); self.assertFalse(pr['log_hidden'])
  t.join(15); u=s.get(self.j['id'])['usage']; self.assertEqual(u['tokens'],1234); self.assertGreater(u['duration_s'],2.5)
  self.assertGreater(s.job_progress(self.j['id'])['elapsed_s'],2.5)
 def test_blind_board_hides_log_files_and_usage(self):
  s.set_blind(self.b['id'],True); t=self.start(); pr=s.job_progress(self.j['id'])
  self.assertTrue(pr['log_hidden']); self.assertEqual(pr['log_tail'],''); self.assertEqual(pr['files'],[]); self.assertEqual(pr['screens_written'],1)
  t.join(15); st=s.mask_state({k:s.allof(k) for k in ['board','variant','job','prototype']})
  self.assertTrue(all('usage' not in j for j in st['job']))
 def test_queued_job_reports_position(self):
  self.j['status']='queued'; s.save('job',self.j); pr=s.job_progress(self.j['id']); self.assertEqual(pr['queue_position'],1); self.assertEqual(pr['elapsed_s'],0)
 def test_no_token_line_means_unknown_not_zero(self):
  r=s.get(self.j['runner_id']); r['args']=['-c','echo done']; s.save('runner',r); s.execute(self.j); self.assertIsNone(s.get(self.j['id'])['usage']['tokens'])

class BlockedAgentTest(unittest.TestCase):
 def test_claude_gets_run_permissions_only_inside_the_sandbox(self):
  import local_agents
  from unittest.mock import patch
  fake=[dict(id='claude',name='Claude Code',executable='/bin/true',models=[],model_source='',supported=True)]
  with patch.object(local_agents,'discover',return_value=fake):
   on=local_agents.configuration('claude','',sandbox=True)['args']; off=local_agents.configuration('claude','',sandbox=False)['args']
  self.assertTrue(any(a.startswith('--allowedTools=') and 'Bash(python3 *)' in a for a in on)); self.assertEqual(on[-1],'{prompt}')   # prompt stays positional
  self.assertFalse(any(a.startswith('--allowedTools') for a in off))
 def test_missing_manifest_with_blocked_log_says_so(self):
  tmp=tempfile.TemporaryDirectory(); old=s.STORE; s.STORE=Path(tmp.name)
  try:
   s.seed(); p=s.allof('project')[0]; b=s.allof('board')[0]
   r=s.save('runner',dict(id=s.uid(),name='cli',type='cli',executable='/bin/sh',args=['-c','echo "the sandbox blocked python3 gen.py and asked for approval"; echo x > output_note.txt; mkdir -p output; echo hi > output/notes.txt'],timeout=30,enabled=True))
   j=dict(id=s.uid(),project_id=p['id'],type='generate_board',runner_id=r['id'],context=s.get(p['context_id']),board_id=b['id'],parent_id=None,annotations=[],brief='b',instruction='t',events=[],status='queued',created_at=time.time()); s.save('job',j); s.execute(j)
   msg=s.get(j['id'])['events'][-1]['message']; self.assertIn('without writing output/manifest.json',msg); self.assertIn('could not run a command',msg)
  finally: s.STORE=old; tmp.cleanup()

class OldRunnerUpgradeTest(unittest.TestCase):
 def test_enabling_sandbox_on_a_pre_sandbox_runner_adds_bind_lists(self):
  import web, local_agents
  from unittest.mock import patch
  tmp=tempfile.TemporaryDirectory(); old=s.STORE; s.STORE=Path(tmp.name)
  try:
   s.seed(); r=s.save('runner',dict(id=s.uid(),name='old',type='cli',agent='claude',model='',executable='/bin/true',args=['--print','{prompt}'],timeout=30,enabled=True,sandbox=None))
   fake=[dict(id='claude',name='Claude Code',executable='/bin/true',models=[],model_source='',supported=True)]
   import threading, urllib.request, json
   srv=s.ThreadingHTTPServer(('127.0.0.1',0),s.Handler); threading.Thread(target=srv.serve_forever,daemon=True).start()
   try:
    with patch.object(local_agents,'discover',return_value=fake), patch.object(web,'bwrap_ok',return_value=True), patch.object(local_agents,'bwrap_ok',return_value=True):
     req=urllib.request.Request(f'http://127.0.0.1:{srv.server_address[1]}/api/update-runner',data=json.dumps(dict(id=r['id'],sandbox='bwrap')).encode(),headers={'Content-Type':'application/json'})
     out=json.loads(urllib.request.urlopen(req).read())
   finally: srv.shutdown(); srv.server_close()
   self.assertEqual(out['sandbox'],'bwrap'); self.assertTrue(out['sandbox_ro']); self.assertIn('~/.claude',out['sandbox_rw']); self.assertTrue(any(a.startswith('--allowedTools=') for a in out['args']))
  finally: s.STORE=old; tmp.cleanup()

class DismissJobTest(unittest.TestCase):
 def test_dismiss_hides_finished_jobs_only_and_keeps_the_record(self):
  import threading, urllib.request, urllib.error, json
  tmp=tempfile.TemporaryDirectory(); old=s.STORE; s.STORE=Path(tmp.name)
  srv=None
  try:
   s.seed(); p=s.allof('project')[0]
   def mk(status): return s.save('job',dict(id=s.uid(),project_id=p['id'],type='generate_board',status=status,events=[],created_at=time.time()))
   failed,running=mk('failed'),mk('running')
   srv=s.ThreadingHTTPServer(('127.0.0.1',0),s.Handler); threading.Thread(target=srv.serve_forever,daemon=True).start()
   def post(i):
    r=urllib.request.Request(f'http://127.0.0.1:{srv.server_address[1]}/api/dismiss-job',data=json.dumps(dict(id=i)).encode(),headers={'Content-Type':'application/json'})
    try: return urllib.request.urlopen(r).status
    except urllib.error.HTTPError as e: e.close(); return e.code
   self.assertEqual(post(failed['id']),200); self.assertTrue(s.get(failed['id'])['dismissed']); self.assertEqual(s.get(failed['id'])['status'],'failed')
   self.assertEqual(post(running['id']),400); self.assertFalse(s.get(running['id']).get('dismissed'))
  finally:
   if srv: srv.shutdown(); srv.server_close()
   s.STORE=old; tmp.cleanup()
