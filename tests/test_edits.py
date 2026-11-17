import sys, tempfile, unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'apps/api'))
import server as s
import jobs


class EditTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.old = s.STORE; s.STORE = Path(self.tmp.name); s.seed()
        self.p = s.allof('project')[0]; self.ctx = s.get(self.p['context_id']); self.b = s.allof('board')[0] if s.allof('board') else None
        if not self.b:
            self.b = s.create_board(dict(project_id=self.p['id'], name='B', brief='b', screens=['One', 'Two']))
        j = dict(id=s.uid(), project_id=self.p['id'], type='generate_board', runner_id=s.allof('runner')[1]['id'], context=self.ctx,
                 board_id=self.b['id'], parent_id=None, annotations=[], brief=self.b['brief'], instruction='t', events=[])
        with patch.object(s.subprocess, 'run', return_value=None), patch.object(s.time, 'sleep'): s.execute(j)
        self.v = s.get(s.get(j['id'])['variant_id'])
        page = (s.STORE / 'variants' / self.v['id'] / 'screens/0.html').read_text()
        self.ids = __import__('re').findall(r'data-design-id="([^"]+)"', page)

    def tearDown(self): s.STORE = self.old; self.tmp.cleanup()

    def edit(self, edits, sid='0'):
        with patch.object(jobs, 'chrome_screenshot', return_value=False): return s.manual_edit(self.v['id'], {sid: edits})

    def test_style_creates_child_and_leaves_parent(self):
        parent_file = s.STORE / 'variants' / self.v['id'] / 'screens/0.html'; before = parent_file.read_bytes()
        did = self.ids[0]
        c = self.edit([dict(design_id=did, style={'color': '#112233', 'font-size': '20px'})])
        self.assertEqual(before, parent_file.read_bytes())
        self.assertEqual((c['parent_id'], c['version'], c['review_state'], c['kind']), (self.v['id'], self.v['version'] + 1, 'pending', 'edit'))
        text = (s.STORE / 'variants' / c['id'] / 'screens/0.html').read_text()
        self.assertIn('color: #112233', text); self.assertIn('font-size: 20px', text)
        self.assertEqual(c['changed_screens'], ['0']); self.assertIn(did, c['changed_regions']['0']['elements'])
        self.assertTrue(any(x['check'].startswith('Manual edit scope') and x['outcome'] == 'pass' for x in c['validation']))
        self.assertEqual(s.get(c['id'])['id'], c['id'])
        # other screens are byte-identical
        self.assertEqual((s.STORE / 'variants' / self.v['id'] / 'screens/1.html').read_bytes(), (s.STORE / 'variants' / c['id'] / 'screens/1.html').read_bytes())

    def test_style_merge_and_reset(self):
        did = self.ids[0]
        a = self.edit([dict(design_id=did, style={'color': '#111111'})])
        self.v = a
        b = self.edit([dict(design_id=did, style={'padding': '8px', 'color': ''})])
        t = (s.STORE / 'variants' / b['id'] / 'screens/0.html').read_text()
        self.assertIn('padding: 8px', t); self.assertNotIn('#111111', t)

    def test_text_edit_only_on_leaf(self):
        page = (s.STORE / 'variants' / self.v['id'] / 'screens/0.html').read_text()
        spans = s.element_spans(page)
        leafs = [i for i, (a, b) in spans.items() if '<' not in page[s.start_tag_end(page, a):page.rfind('</', a, b)] and page.rfind('</', a, b) > a]
        nested = [i for i, (a, b) in spans.items() if i not in leafs]
        c = self.edit([dict(design_id=leafs[0], text='Hello <b>&</b>')])
        self.assertIn('Hello &lt;b&gt;&amp;&lt;/b&gt;', (s.STORE / 'variants' / c['id'] / 'screens/0.html').read_text())
        if nested:
            with self.assertRaises(ValueError): self.edit([dict(design_id=nested[0], text='x')])

    def test_rejects_unsafe_input(self):
        did = self.ids[0]
        for style in [{'color': 'red;} body{display:none'}, {'background-color': 'url(http://x/y)'}, {'position': 'fixed'},
                      {'color': 'red" onclick="x'}, {'display': 'contents'}, {'font-family': '</style>'}]:
            with self.assertRaises(ValueError, msg=str(style)): self.edit([dict(design_id=did, style=style)])
        with self.assertRaises(ValueError): self.edit([dict(design_id='nope', style={'color': 'red'})])
        with self.assertRaises(ValueError): self.edit([dict(design_id=did, style={'color': 'red'})], sid='99')
        with self.assertRaises(ValueError): self.edit([dict(design_id=did)])
        self.assertEqual(len([x for x in s.allof('variant')]), 1)  # failures leave no stray versions
        self.assertEqual(len(list((s.STORE / 'variants').iterdir())), 1)

    def test_accept_and_revert_work_like_revisions(self):
        c = self.edit([dict(design_id=self.ids[0], style={'opacity': '0.5'})])
        self.assertEqual(s.set_review_state(c['id'], 'reverted')['review_state'], 'reverted')


if __name__ == '__main__':
    unittest.main()
