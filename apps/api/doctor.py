"""Contract doctor: run a real local agent through the studio's own runner path on a throwaway project and report
which contract stage passes or fails. Uses a temporary storage directory; never touches your projects.

  python3 apps/api/doctor.py claude [--model ID] [--timeout 600] [--guidance]

--guidance runs a second job with a changed accent token and checks the output actually reflects it
(guidance must change generation, not just be displayed)."""
import argparse, re, sys, tempfile, time, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import server as s, local_agents

def wait(jid, limit):
    end = time.time() + limit + 30
    while time.time() < end:
        j = s.get(jid)
        if j['status'] in ('succeeded', 'failed', 'timed_out', 'cancelled'): return j
        time.sleep(1)
    return s.get(jid)

def report(label, j, started):
    ok = j['status'] == 'succeeded'; print(f"\n== {label}: {j['status'].upper()} in {time.time() - started:.0f}s")
    for e in j['events']: print('   ·', e['message'])
    log = s.STORE / 'jobs' / j['id'] / 'runner.log'
    if not ok and log.is_file(): print('   runner.log (first 25 lines):\n     ' + '\n     '.join(log.read_text().strip().splitlines()[:25]))
    if ok:
        v = s.get(j['variant_id']); counts = {}
        for c in v['validation']: counts[c['outcome']] = counts.get(c['outcome'], 0) + 1
        print('   validation:', counts)
        for c in v['validation']:
            if c['outcome'] in ('fail', 'not_assessable'): print(f"   - {c['outcome']}: {c['check']} — {c['evidence']}")
        print('   screenshots:', sum(1 for _ in (s.STORE / 'variants' / v['id'] / 'thumbnails').glob('*.png')), 'of', len(v['manifest']['screens']))
    return ok

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('agent'); ap.add_argument('--model', default=''); ap.add_argument('--timeout', type=int, default=600); ap.add_argument('--guidance', action='store_true'); ap.add_argument('--mix', action='store_true', help='also generate a second version and check a mixed version renders identically to its sources'); ap.add_argument('--region', action='store_true', help='also check a pinned-element revision changes only that element'); ap.add_argument('--references', action='store_true', help='also check the agent actually reads a reference image'); ap.add_argument('--keep', action='store_true', help='keep the temporary storage for inspection')
    a = ap.parse_args(); s.start_workers(); tmp = tempfile.TemporaryDirectory(); s.STORE = Path(tmp.name); s.seed()
    p = s.allof('project')[0]; b = s.allof('board')[0]
    try: cfg = local_agents.configuration(a.agent, a.model)
    except ValueError as e: print('Cannot configure agent:', e); return 2
    cfg['timeout'] = a.timeout; runner = s.save('runner', dict(id=s.uid(), enabled=True, **cfg))
    print(f"Agent: {cfg['name']}  executable: {cfg['executable']}\nEnvironment passed through: {', '.join(cfg['env_allowlist'])}\nStorage: {tmp.name} (temporary)")
    t = time.time(); j = s.launch(dict(board_id=b['id'], brief=b['brief'], runner_ids=[runner['id']]), 'generate_board', p['id'])[0]
    ok = report('baseline generation', wait(j['id'], a.timeout), t)
    if ok and a.guidance:
        c = s.get(p['context_id']); tokens = dict(c['tokens'], accent='#c2185b')
        s.context(p['id'], dict(markdown=c['markdown'] + '\nPrimary buttons must use the accent token #c2185b.\n', tokens=tokens, rules=c['rules']))
        t = time.time(); j2 = s.launch(dict(board_id=b['id'], brief=b['brief'], runner_ids=[runner['id']]), 'generate_board', p['id'])[0]
        ok2 = report('guidance-changed generation', wait(j2['id'], a.timeout), t)
        if ok2:
            v1, v2 = s.get(s.get(j['id'])['variant_id']), s.get(s.get(j2['id'])['variant_id'])
            txt = lambda v: ''.join(f.read_text(errors='replace').lower() for f in (s.STORE / 'variants' / v['id']).rglob('*') if f.suffix in ('.html', '.css'))
            used, differs = '#c2185b' in txt(v2), txt(v1) != txt(v2)
            print(f"\n== guidance check: output differs={differs}, new accent #c2185b present={used}"); ok = ok and differs and used
        else: ok = False
    if ok and a.mix:
        import subprocess
        t = time.time(); jm = s.launch(dict(board_id=b['id'], brief=b['brief'], runner_ids=[runner['id']]), 'generate_board', p['id'])[0]
        okm = report('second generation (for mixing)', wait(jm['id'], a.timeout), t)
        if okm:
            v1, v2 = s.get(s.get(j['id'])['variant_id']), s.get(s.get(jm['id'])['variant_id']); n = len(b['screens'])
            picks = {str(i): (v1 if i % 2 == 0 else v2)['id'] for i in range(n)}; mixed = s.mix_variants(b['id'], picks)
            bad = [c for c in mixed['validation'] if c['outcome'] == 'fail']; print('\n== mixed version:', mixed['runner_name'], '| failed checks:', bad or 'none')
            same = []
            for sid in (str(i) for i in range(n)):
                src = s.STORE / 'variants' / picks[sid]; out = Path(tmp.name) / f'mixcmp-{sid}'
                shots = []
                for label, folder in (('src', src), ('mix', s.STORE / 'variants' / mixed['id'])):
                    png = Path(tmp.name) / f'{label}-{sid}.png'
                    subprocess.run(['google-chrome', '--headless', '--no-sandbox', '--disable-gpu', '--hide-scrollbars', '--window-size=720,960', f'--user-data-dir={tmp.name}/chr-{label}-{sid}', f'--screenshot={png}', (folder / 'screens' / f'{sid}.html').as_uri()], capture_output=True, timeout=60); shots.append(png.read_bytes() if png.is_file() else None)
                same.append(shots[0] is not None and shots[0] == shots[1])
            print(f"== mix render check: mixed screens render identically to their sources = {same}"); ok = ok and not bad and all(same)
        else: ok = False
    if ok and a.region:
        base = s.get(s.get(j['id'])['variant_id']); html0 = (s.STORE / 'variants' / base['id'] / 'screens' / '0.html').read_text(errors='replace'); ids = list(s.element_spans(html0))
        target = next((i for i in ids if re.search(r'head|title|h1', i, re.I)), ids[0] if ids else None)
        if not target: print('\n== region check: SKIPPED (the agent output has no data-design-id elements to pin)'); ok = False
        else:
            pin = s.save('annotation', dict(id=s.uid(), variant_id=base['id'], screen='0', x=.5, y=.2, comment='Change this element\'s text to exactly "Quietly Certain".', element_id=target, status='open', selected=True, created_at=time.time()))
            t = time.time(); jr = s.launch(dict(board_id=b['id'], parent_id=base['id'], annotation_ids=[pin['id']], runner_ids=[runner['id']], brief=b['brief']), 'revise_board', p['id'])[0]
            okr = report(f'region revision of element "{target}"', wait(jr['id'], a.timeout), t)
            if okr:
                child = s.get(s.get(jr['id'])['variant_id']); scope = [c for c in child['validation'] if c['check'].startswith('Revision scope')]
                changed = 'quietly certain' in (s.STORE / 'variants' / child['id'] / 'screens' / '0.html').read_text(errors='replace').lower()
                for c in scope: print(f"   - {c['outcome']}: {c['check']} — {c['evidence']}")
                print(f"\n== region check: text changed={changed}, scope check passed={bool(scope) and all(c['outcome']=='pass' for c in scope)}"); ok = ok and changed and bool(scope) and all(c['outcome'] == 'pass' for c in scope)
            else: ok = False
    if ok and a.references:
        import base64, subprocess, os
        word = 'PINEAPPLE-42'; html = Path(tmp.name) / 'ref.html'; png = Path(tmp.name) / 'ref.png'
        html.write_text(f'<body style="margin:0;width:700px;height:300px;background:#fffbe6;display:grid;place-items:center;font:700 64px sans-serif;color:#222">{word}</body>')
        subprocess.run(['google-chrome', '--headless', '--no-sandbox', '--disable-gpu', '--window-size=700,300', f'--user-data-dir={tmp.name}/chr', f'--screenshot={png}', html.as_uri()], capture_output=True, timeout=60)
        if not png.is_file(): print('\n== reference check: SKIPPED (Chrome unavailable to render the test image)')
        else:
            ref = s.add_reference(dict(project_id=p['id'], name='Heading text', note='Use the exact words shown in this image as the main heading of the first screen.', data=base64.b64encode(png.read_bytes()).decode()))
            t = time.time(); j3 = s.launch(dict(board_id=b['id'], brief=b['brief'], runner_ids=[runner['id']], reference_ids=[ref['id']]), 'generate_board', p['id'])[0]
            ok3 = report('generation with a reference image', wait(j3['id'], a.timeout), t)
            if ok3:
                v3 = s.get(s.get(j3['id'])['variant_id']); found = word.lower() in ''.join(f.read_text(errors='replace').lower() for f in (s.STORE / 'variants' / v3['id']).rglob('*.html'))
                print(f"\n== reference check: the agent used text from the image ({word}) = {found}"); ok = ok and found
            else: ok = False
    print('\nRESULT:', 'PASS' if ok else 'FAIL')
    if a.keep: print('Kept:', tmp.name); tmp._finalizer.detach()
    else: tmp.cleanup()
    return 0 if ok else 1
if __name__ == '__main__': raise SystemExit(main())
