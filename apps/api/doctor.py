"""Contract doctor: run a real local agent through the studio's own runner path on a throwaway project and report
which contract stage passes or fails. Uses a temporary storage directory; never touches your projects.

  python3 apps/api/doctor.py claude [--model ID] [--timeout 600] [--guidance]

--guidance runs a second job with a changed accent token and checks the output actually reflects it
(guidance must change generation, not just be displayed)."""
import argparse, sys, tempfile, time, json
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
    ap = argparse.ArgumentParser(); ap.add_argument('agent'); ap.add_argument('--model', default=''); ap.add_argument('--timeout', type=int, default=600); ap.add_argument('--guidance', action='store_true'); ap.add_argument('--references', action='store_true', help='also check the agent actually reads a reference image'); ap.add_argument('--keep', action='store_true', help='keep the temporary storage for inspection')
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
