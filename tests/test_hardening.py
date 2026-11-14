import json, sys, tempfile, threading, unittest, urllib.request, urllib.error
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/api'))
import server as s, web

class HardeningTest(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory(); cls.old=s.STORE; s.STORE=Path(cls.tmp.name); s.seed()
  cls.srv=s.ThreadingHTTPServer(('127.0.0.1',0),s.Handler); cls.port=cls.srv.server_address[1]
  threading.Thread(target=cls.srv.serve_forever,daemon=True).start()
 @classmethod
 def tearDownClass(cls): cls.srv.shutdown(); cls.srv.server_close(); s.STORE=cls.old; cls.tmp.cleanup()
 def call(self,path,data=None,headers=None,raw=None):
  h=dict(headers or {})
  if (data is not None or raw is not None) and 'Content-Type' not in h: h['Content-Type']='application/json'
  r=urllib.request.Request(f'http://127.0.0.1:{self.port}{path}',data=raw if raw is not None else (json.dumps(data).encode() if data is not None else None),headers=h)
  try:
   with urllib.request.urlopen(r) as x: return x.status,json.loads(x.read() or b'null'),x.headers
  except urllib.error.HTTPError as e: return e.code,json.loads(e.read() or b'null'),e.headers
 def test_health(self):
  code,body,_=self.call('/api/health'); self.assertEqual(code,200); self.assertTrue(body['ok']); self.assertIn('free_disk_mb',body)
 def test_rebinding_host_rejected_on_get_and_post(self):
  self.assertEqual(self.call('/api/state',headers={'Host':'evil.example:5173'})[0],403)
  self.assertEqual(self.call('/api/project',{'name':'x'},headers={'Host':'evil.example','Origin':'http://evil.example'})[0],403)
  self.assertEqual(self.call('/api/state',headers={'Host':'localhost:5173'})[0],200)
  self.assertEqual(self.call('/api/state',headers={'Host':'[::1]:5173'})[0],200)
 def test_extra_hosts_are_opt_in(self):
  with patch.dict('os.environ',{'STUDIO_ALLOWED_HOSTS':'studio.lan'}): self.assertEqual(self.call('/api/state',headers={'Host':'studio.lan:5173'})[0],200)
 def test_post_needs_json_content_type_and_object(self):
  self.assertEqual(self.call('/api/project',raw=b'{}',headers={'Content-Type':'text/plain'})[0],400)
  self.assertEqual(self.call('/api/project',raw=b'not json')[0],400)
  self.assertEqual(self.call('/api/project',raw=b'[1]')[0],400)
 def test_missing_field_is_400_with_name_internal_error_is_500_without_details(self):
  code,body,_=self.call('/api/context',{}); self.assertEqual(code,400); self.assertIn('project_id',body['message'])
  with patch.object(web,'project',side_effect=RuntimeError('secret path /home/x')):
   code,body,_=self.call('/api/project',{'name':'x'}); self.assertEqual(code,500); self.assertNotIn('secret',json.dumps(body)); self.assertIn('request_id',body)
 def test_state_etag_gives_304_until_something_changes(self):
  _,_,h=self.call('/api/state'); tag=h['ETag']
  r=urllib.request.Request(f'http://127.0.0.1:{self.port}/api/state',headers={'If-None-Match':tag})
  with self.assertRaises(urllib.error.HTTPError) as e: urllib.request.urlopen(r)
  self.assertEqual(e.exception.code,304)
  self.call('/api/project',{'name':'Another'})
  self.assertNotEqual(self.call('/api/state')[2]['ETag'],tag)
 def test_concurrent_writes_do_not_lock_the_database(self):
  errs=[]
  def w():
   try:
    for _ in range(25): s.save('reference',dict(id=s.uid(),project_id='p',name='n'))
   except Exception as e: errs.append(e)
  ts=[threading.Thread(target=w) for _ in range(6)]; [t.start() for t in ts]; [t.join() for t in ts]
  self.assertEqual(errs,[]); self.assertGreaterEqual(len(s.allof('reference')),150)
 def test_share_listener_defaults_to_loopback(self):
  import inspect, re; self.assertRegex(inspect.getsource(web.main),r"STUDIO_SHARE_HOST',\s*'127\.0\.0\.1'")

if __name__=='__main__': unittest.main()

class BackupTest(unittest.TestCase):
 def test_backup_is_a_usable_copy(self):
  import backup, sqlite3
  with tempfile.TemporaryDirectory() as a, tempfile.TemporaryDirectory() as b:
   old=s.STORE; s.STORE=Path(a)
   try: s.seed(); (Path(a)/'jobs'/'j1').mkdir(parents=True); (Path(a)/'jobs'/'j1'/'x.txt').write_text('hi'); n=len(s.allof('project'))
   finally: s.STORE=old
   backup.backup(a,Path(b)/'out')
   self.assertEqual(sqlite3.connect(Path(b)/'out'/'studio.db').execute("select count(*) from entities where type='project'").fetchone()[0],n)
   self.assertEqual((Path(b)/'out'/'jobs'/'j1'/'x.txt').read_text(),'hi')

class LanModeTest(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory(); cls.old=s.STORE; s.STORE=Path(cls.tmp.name); s.seed()
  cls.srv=s.ThreadingHTTPServer(('127.0.0.1',0),s.Handler); cls.port=cls.srv.server_address[1]
  threading.Thread(target=cls.srv.serve_forever,daemon=True).start()
 @classmethod
 def tearDownClass(cls): cls.srv.shutdown(); cls.srv.server_close(); s.STORE=cls.old; cls.tmp.cleanup()
 call=HardeningTest.call
 def test_default_mode_rejects_lan_ip_hosts(self):
  self.assertEqual(self.call('/api/state',headers={'Host':'192.168.1.20:5173'})[0],403)
 def test_lan_mode_accepts_ip_literals_and_own_name_but_not_other_names(self):
  with patch.dict('os.environ',{'STUDIO_HOST':'0.0.0.0'}):
   self.assertEqual(self.call('/api/state',headers={'Host':'192.168.1.20:5173'})[0],200)
   self.assertEqual(self.call('/api/state',headers={'Host':'[fe80::1]:5173'})[0],200)
   self.assertEqual(self.call('/api/state',headers={'Host':'evil.example:5173'})[0],403)
   self.assertEqual(self.call('/api/state',headers={'Host':'rebind.attacker.test'})[0],403)
   import socket; self.assertEqual(self.call('/api/state',headers={'Host':socket.gethostname()+'.local:5173'})[0],200)
 def test_lan_mode_blocks_runner_admin_from_other_machines_only(self):
  with patch.dict('os.environ',{'STUDIO_HOST':'0.0.0.0'}):
   with patch.object(web,'is_local_client',return_value=False):
    for a in ('runner','local-runner','update-runner','delete-runner','test-runner'):
     code,body,_=self.call('/api/'+a,{'type':'cli','executable':'/bin/sh','agent':'claude','id':'x'}); self.assertEqual(code,400); self.assertIn('computer running the studio',body['message'],a)
    self.assertEqual(len(s.allof('runner')),2)
    self.assertEqual(self.call('/api/project',{'name':'from phone'})[0],200)   # normal design work is allowed
   self.assertEqual(self.call('/api/test-runner',{'id':s.allof('runner')[0]['id']})[0],200)  # local machine still can
 def test_a_computer_using_its_own_network_address_counts_as_local(self):
  self.assertTrue(web.is_local_client('192.168.1.152','192.168.1.152')); self.assertTrue(web.is_local_client('::ffff:192.168.1.152','192.168.1.152')); self.assertTrue(web.is_local_client('127.0.0.1','192.168.1.152'))
  self.assertFalse(web.is_local_client('192.168.1.77','192.168.1.152'))
 def test_loopback_detection(self):
  self.assertTrue(web.is_loopback_client('127.0.0.1')); self.assertTrue(web.is_loopback_client('::1')); self.assertFalse(web.is_loopback_client('192.168.1.5'))

class UiServingTest(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.dist=tempfile.TemporaryDirectory(); d=Path(cls.dist.name); (d/'ui').mkdir(); (d/'index.html').write_text('<!doctype html><div id="root"></div>'); (d/'ui'/'app-abc123.js').write_text('console.log(1)')
  cls.patch=patch.object(web,'UI_DIST',d); cls.patch.start()
  cls.srv=s.ThreadingHTTPServer(('127.0.0.1',0),s.Handler); cls.port=cls.srv.server_address[1]; threading.Thread(target=cls.srv.serve_forever,daemon=True).start()
 @classmethod
 def tearDownClass(cls): cls.srv.shutdown(); cls.srv.server_close(); cls.patch.stop(); cls.dist.cleanup()
 def get(self,path,headers=None):
  r=urllib.request.Request(f'http://127.0.0.1:{self.port}{path}',headers=headers or {})
  try:
   with urllib.request.urlopen(r) as x: return x.status,x.read().decode(),x.headers
  except urllib.error.HTTPError as e: e.close(); return e.code,'',e.headers
 def test_index_revalidates_and_hashed_assets_are_immutable(self):
  code,html,h=self.get('/'); self.assertEqual(code,200); self.assertEqual(h['Cache-Control'],'no-cache'); self.assertIn('id="root"',html)
  self.assertEqual(self.get('/',{'If-None-Match':h['ETag']})[0],304)
  code,_,h2=self.get('/ui/app-abc123.js'); self.assertEqual(code,200); self.assertIn('immutable',h2['Cache-Control'])
 def test_deep_links_get_the_app_and_traversal_is_refused(self):
  code,html,_=self.get('/projects/abc/boards/def/review/ghi'); self.assertEqual(code,200); self.assertIn('id="root"',html)
  self.assertNotEqual(self.get('/ui/../../api/server.py')[0],200)
 def test_missing_build_gives_a_clear_503(self):
  with patch.object(web,'UI_DIST',Path('/nonexistent-dist')): code,body,_=self.get('/')
  self.assertEqual(code,503)
