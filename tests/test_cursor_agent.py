"""Cursor Agent (cursor-agent / agent) local runner adapter."""
import sys, unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/api'))
import local_agents


class CursorAgentTest(unittest.TestCase):
    def fake(self, exe='/usr/bin/cursor-agent'):
        return [dict(id='cursor', name='Cursor Agent', executable=exe, models=[''], model_source='x', supported=True)]

    def test_discover_prefers_cursor_agent_binary_name(self):
        which = {'cursor-agent': '/opt/cursor-agent', 'agent': '/opt/agent-alias'}

        def fake_which(name):
            return which.get(name)

        with patch.object(local_agents.shutil, 'which', side_effect=fake_which):
            with patch.object(local_agents.subprocess, 'run', side_effect=OSError):
                found = {a['id']: a for a in local_agents.discover()}
        self.assertIn('cursor', found)
        self.assertEqual(found['cursor']['executable'], '/opt/cursor-agent')
        self.assertTrue(found['cursor']['supported'])
        self.assertEqual(found['cursor']['name'], 'Cursor Agent')

    def test_generic_agent_name_is_not_treated_as_cursor(self):
        with patch.object(local_agents.shutil, 'which', side_effect=lambda n: '/home/u/.local/bin/agent' if n == 'agent' else None):
            with patch.object(local_agents.subprocess, 'run', side_effect=OSError):
                found = {a['id']: a for a in local_agents.discover()}
        self.assertNotIn('cursor', found)  # a bare `agent` on PATH could be any program; only `cursor-agent` counts

    def test_configuration_print_force_trust_and_sandbox_toggle(self):
        with patch.object(local_agents, 'discover', return_value=self.fake()):
            with patch.object(local_agents, 'bwrap_ok', return_value=True):
                on = local_agents.configuration('cursor', '', sandbox=True)
                off = local_agents.configuration('cursor', 'composer-2', sandbox=False)
        self.assertEqual(on['agent'], 'cursor')
        self.assertEqual(on['type'], 'cli')
        self.assertIn('--print', on['args'])
        self.assertIn('--force', on['args'])
        self.assertIn('--trust', on['args'])
        self.assertIn('--workspace', on['args'])
        self.assertEqual(on['args'][on['args'].index('--workspace') + 1], '.')
        self.assertIn('disabled', on['args'])
        self.assertEqual(on['sandbox'], 'bwrap')
        self.assertIn('CURSOR_API_KEY', on['env_allowlist'])
        self.assertIn('~/.cursor', on['sandbox_rw'])
        self.assertIn('~/.local/share/cursor-agent', on['sandbox_rw'])
        self.assertIn('{prompt}', on['args'])
        self.assertIn('enabled', off['args'])
        self.assertIsNone(off['sandbox'])
        self.assertIn('composer-2', off['args'])
        self.assertIn('composer-2', off['name'])

    def test_unsupported_without_binary(self):
        with patch.object(local_agents, 'discover', return_value=[]):
            with self.assertRaises(ValueError):
                local_agents.configuration('cursor', '')

    def test_discover_parses_list_models_output(self):
        which = {'cursor-agent': '/opt/cursor-agent'}

        def fake_run(cmd, **kw):
            class P:
                returncode = 0
                stdout = 'Available models\n---\ncomposer-2\nauto\n'

            self.assertEqual(cmd[0], '/opt/cursor-agent')
            self.assertEqual(cmd[1], '--list-models')
            return P()

        with patch.object(local_agents.shutil, 'which', side_effect=lambda n: which.get(n)):
            with patch.object(local_agents.subprocess, 'run', side_effect=fake_run):
                found = {a['id']: a for a in local_agents.discover()}
        self.assertEqual(found['cursor']['models'][:2], ['composer-2', 'auto'])
        self.assertIn('list-models', found['cursor']['model_source'])


if __name__ == '__main__':
    unittest.main()
