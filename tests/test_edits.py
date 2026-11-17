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

    def structure(self):
        page = (s.STORE / 'variants' / self.v['id'] / 'screens/0.html').read_text()
        spans = s.element_spans(page)
        tag = lambda i: __import__('re').match(r'<(\w+)', page[spans[i][0]:]).group(1)
        return page, spans, tag

    def test_duplicate_gets_unique_ids_and_leaves_parent(self):
        page, spans, tag = self.structure()
        did = next(i for i in self.ids if tag(i) in ('p', 'h1', 'h2', 'li', 'button', 'a'))
        c = self.edit([dict(op='duplicate', design_id=did)])
        text = (s.STORE / 'variants' / c['id'] / 'screens/0.html').read_text()
        self.assertIn(f'"{did}-copy"', text)
        ids = __import__('re').findall(r'data-design-id="([^"]+)"', text)
        self.assertEqual(len(ids), len(set(ids)), 'every id stays unique')
        self.assertEqual(c['changed_screens'], ['0'])
        self.assertTrue(any(x['check'].startswith('Manual edit scope') and x['outcome'] == 'pass' for x in c['validation']), c['validation'])
        c2 = self.edit([dict(op='duplicate', design_id=did), dict(op='duplicate', design_id=did)])
        t2 = (s.STORE / 'variants' / c2['id'] / 'screens/0.html').read_text()
        self.assertIn(f'"{did}-copy-2"', t2)

    def test_delete_move_insert(self):
        page, spans, tag = self.structure()
        sibs = [i for i in self.ids if tag(i) in ('p', 'h1', 'h2', 'li', 'button', 'a')]
        a, b = sibs[0], sibs[1]
        c = self.edit([dict(op='delete', design_id=a)])
        self.assertNotIn(f'data-design-id="{a}"', (s.STORE / 'variants' / c['id'] / 'screens/0.html').read_text())
        c = self.edit([dict(op='move', design_id=a, target_id=b, position='after')])
        t = (s.STORE / 'variants' / c['id'] / 'screens/0.html').read_text()
        self.assertLess(t.index(f'data-design-id="{b}"'), t.index(f'data-design-id="{a}"'))
        self.assertTrue(all(x['outcome'] != 'fail' or not x['check'].startswith('Manual edit scope') for x in c['validation']))
        c = self.edit([dict(op='insert', target_id=b, position='after', kind='button')])
        t = (s.STORE / 'variants' / c['id'] / 'screens/0.html').read_text()
        self.assertIn('data-design-id="new-button-1"', t); self.assertIn('<button type="button"', t)
        # a later edit in the same save can address the new element
        c = self.edit([dict(op='insert', target_id=b, position='after', kind='text'), dict(design_id='new-text-1', text='Hi', style={'color': '#123456'})])
        self.assertIn('>Hi</p>', (s.STORE / 'variants' / c['id'] / 'screens/0.html').read_text())

    def test_structural_rejections(self):
        page, spans, tag = self.structure()
        did = self.ids[0]
        for e in [dict(op='move', design_id=did, target_id=did, position='after'), dict(op='nope', design_id=did),
                  dict(op='insert', target_id=did, position='sideways', kind='text'), dict(op='insert', target_id=did, kind='iframe'),
                  dict(op='delete', design_id='missing')]:
            with self.assertRaises(ValueError, msg=str(e)): self.edit([e])
        outer = next((i for i in self.ids if any(spans[j][0] > spans[i][0] and spans[j][1] < spans[i][1] for j in self.ids if j != i)), None)
        if outer:
            inner = next(j for j in self.ids if j != outer and spans[j][0] > spans[outer][0] and spans[j][1] < spans[outer][1])
            with self.assertRaises(ValueError): self.edit([dict(op='move', design_id=outer, target_id=inner, position='inside')])
        self.assertEqual(len(list((s.STORE / 'variants').iterdir())), 1)

    PNG = 'data:image/png;base64,' + __import__('base64').b64encode(b'\x89PNG\r\n\x1a\n' + b'0' * 40).decode()

    def test_duplicate_drops_primary_role_so_check_stays_green(self):
        page = (s.STORE / 'variants' / self.v['id'] / 'screens/0.html').read_text()
        import re
        prim = re.search(r'<[^>]*data-role="primary-action"[^>]*data-design-id="([^"]+)"|<[^>]*data-design-id="([^"]+)"[^>]*data-role="primary-action"', page)
        if not prim: self.skipTest('fixture screen has no identified primary action')
        did = prim.group(1) or prim.group(2)
        c = self.edit([dict(op='duplicate', design_id=did)])
        t = (s.STORE / 'variants' / c['id'] / 'screens/0.html').read_text()
        self.assertEqual(t.count('data-role="primary-action"'), page.count('data-role="primary-action"'))
        evid = lambda v: [x['evidence'] for x in v['validation'] if x['check'].startswith('Primary action') and x.get('screen') == '0']
        self.assertEqual(evid(c), evid(self.v), 'the copy adds no primary action')

    def test_free_position_and_resize_styles(self):
        did = self.ids[0]
        c = self.edit([dict(design_id=did, style={'position': 'relative', 'left': '-12px', 'top': '8px', 'width': '240px', 'box-sizing': 'border-box'})])
        t = (s.STORE / 'variants' / c['id'] / 'screens/0.html').read_text()
        self.assertIn('left: -12px', t.replace(':', ': ').replace(':  ', ': ')) if 'left: -12px' not in t else None
        for bad in [{'position': 'absolute'}, {'position': 'fixed'}, {'box-sizing': 'x'}]:
            with self.assertRaises(ValueError): self.edit([dict(design_id=did, style=bad)])

    def test_insert_and_replace_image(self):
        page, spans, tag = self.structure()
        target = next(i for i in self.ids if tag(i) in ('p', 'h1', 'h2', 'li', 'button', 'a'))
        c = self.edit([dict(op='insert', target_id=target, position='after', kind='image', data_url=self.PNG, alt='Hero')])
        folder = s.STORE / 'variants' / c['id']; t = (folder / 'screens/0.html').read_text()
        self.assertIn('data-design-id="new-image-1"', t); self.assertIn('alt="Hero"', t)
        src = __import__('re').search(r'<img data-design-id="new-image-1" src="([^"]+)"', t).group(1)
        self.assertTrue((folder / 'screens' / src).resolve().is_file(), src)
        self.assertFalse([x for x in c['validation'] if x['outcome'] == 'fail' and ('Manual edit scope' in x['check'] or 'link' in x['check'].lower())], c['validation'])
        c2 = self.edit([dict(op='insert', target_id=target, position='after', kind='image', data_url=self.PNG), dict(op='image', design_id='new-image-1', alt='Changed')])
        self.assertIn('alt="Changed"', (s.STORE / 'variants' / c2['id'] / 'screens/0.html').read_text())
        for bad in ['data:image/svg+xml;base64,PHN2Zz4=', 'data:image/png;base64,' + 'AAAA', 'http://x/y.png', 'data:image/png;base64,' + __import__('base64').b64encode(b'x' * 50).decode()]:
            with self.assertRaises(ValueError, msg=bad): self.edit([dict(op='insert', target_id=target, position='after', kind='image', data_url=bad)])
        with self.assertRaises(ValueError): self.edit([dict(op='image', design_id=target, data_url=self.PNG)])

    def test_component_from_other_screen_is_copied_by_the_server(self):
        other = (s.STORE / 'variants' / self.v['id'] / 'screens/1.html').read_text()
        src_id = __import__('re').findall(r'data-design-id="([^"]+)"', other)[0]
        target = self.ids[-1]
        c = self.edit([dict(op='component', source_screen='1', source_id=src_id, target_id=target, position='after', html='<script>alert(1)</script>')])
        t = (s.STORE / 'variants' / c['id'] / 'screens/0.html').read_text()
        self.assertNotIn('alert(1)', t, 'the browser-supplied html is ignored')
        ids = __import__('re').findall(r'data-design-id="([^"]+)"', t)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(any(i.startswith(src_id) and i.endswith('-copy') or '-copy' in i for i in ids))
        with self.assertRaises(ValueError): self.edit([dict(op='component', source_screen='9', source_id=src_id, target_id=target)])
        with self.assertRaises(ValueError): self.edit([dict(op='component', source_screen='1', source_id='nope', target_id=target)])

    def test_server_drafts_round_trip(self):
        vid = self.v['id']
        self.assertEqual(s.draft_get(vid)['logs'], {})
        s.draft_save(vid, {'0': [dict(design_id=self.ids[0], style={'color': '#123456'})]})
        self.assertEqual(s.draft_get(vid)['logs']['0'][0]['style']['color'], '#123456')
        s.draft_save(vid, {'0': []})
        self.assertEqual(s.draft_get(vid)['logs'], {})
        with self.assertRaises(ValueError): s.draft_save('missing', {'0': [{}]})
        with self.assertRaises(ValueError): s.draft_save(vid, [])


if __name__ == '__main__':
    unittest.main()
