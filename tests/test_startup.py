import errno
import io
import os
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from unittest.mock import MagicMock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'apps/api'))
import server

class StartupTest(unittest.TestCase):
 def test_busy_port_explains_alternative_without_modifying_jobs(self):
  output=io.StringIO()
  with patch.dict(os.environ,{'PORT':'5173'}), patch.object(server,'ThreadingHTTPServer',side_effect=OSError(errno.EADDRINUSE,'Address already in use')), patch.object(server,'seed') as seed, redirect_stderr(output):
   self.assertEqual(server.main(),1)
   seed.assert_not_called()
  self.assertIn('PORT=5174',output.getvalue())
 def test_invalid_port(self):
  with patch.dict(os.environ,{'PORT':'invalid'}), patch.object(server,'ThreadingHTTPServer') as factory, redirect_stderr(io.StringIO()):
   self.assertEqual(server.main(),1);factory.assert_not_called()
 def test_actual_port_is_printed(self):
  fake=MagicMock();out=io.StringIO()
  with patch.dict(os.environ,{'PORT':'5174'}),patch.object(server,'ThreadingHTTPServer',return_value=fake) as factory,patch.object(server,'seed'),patch.object(server,'allof',return_value=[]),redirect_stdout(out):
   self.assertEqual(server.main(),0)
  factory.assert_called_once_with(('127.0.0.1',5174),server.Handler)
  self.assertIn('http://localhost:5174',out.getvalue())
 def test_permission_error_is_reported(self):
  out=io.StringIO()
  with patch.object(server,'ThreadingHTTPServer',side_effect=PermissionError(errno.EPERM,'Denied')),redirect_stderr(out):
   self.assertEqual(server.main(),1)
  self.assertIn('permission denied',out.getvalue())
