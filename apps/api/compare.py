"""Same brief, several real agents, one table: time, tokens (when the agent reports them), validation and screenshots.
Runs one agent at a time in a temporary store so the timings are comparable. Never touches your projects.

  python3 apps/api/compare.py claude codex copilot [--model claude=ID ...] [--timeout 600] [--out DIR] [--repeat N]

--out copies each agent's screenshots and writes results.json. Cost: only tokens are reported, because only Codex prints a count;
Claude Code and Copilot expose none in non-interactive mode, so a money figure would be a guess and is not shown."""
import argparse, json, shutil, sys, tempfile, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import server as s, local_agents
from doctor import wait

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('agents', nargs='+'); ap.add_argument('--model', action='append', default=[], help='agent=model')
    ap.add_argument('--timeout', type=int, default=600); ap.add_argument('--out', default=''); ap.add_argument('--repeat', type=int, default=1)
    a = ap.parse_args(); models = dict(m.split('=', 1) for m in a.model)
    s.start_workers(); tmp = tempfile.TemporaryDirectory(); s.STORE = Path(tmp.name); s.seed()
    p = s.allof('project')[0]; b = s.allof('board')[0]; rows = []
    print(f"Brief: {b['brief']}\nScreens: {', '.join(b['screens'])}\n")
    for agent in a.agents:
        try: cfg = local_agents.configuration(agent, models.get(agent, ''))
        except ValueError as e: print(f'{agent}: skipped ({e})'); continue
        cfg['timeout'] = a.timeout; runner = s.save('runner', dict(id=s.uid(), enabled=True, **cfg))
        for n in range(a.repeat):
            t = time.time(); j = s.launch(dict(board_id=b['id'], brief=b['brief'], runner_ids=[runner['id']]), 'generate_board', p['id'])[0]
            j = wait(j['id'], a.timeout); wall = round(time.time() - t, 1); v = s.get(j['variant_id']) if j.get('variant_id') else None
            val = [c['outcome'] for c in (v or {}).get('validation', [])]; folder = s.STORE / 'variants' / v['id'] if v else None
            shots = sorted((folder / 'thumbnails').glob('*.png')) if folder and (folder / 'thumbnails').is_dir() else []
            size = sum(f.stat().st_size for f in (folder.rglob('*') if folder else []) if f.is_file() and f.suffix in ('.html', '.css', '.js'))
            u = j.get('usage') or {}
            row = dict(agent=agent, run=n + 1, status=j['status'], seconds=wall, per_screen_s=round(wall / max(1, len(b['screens'])), 1), tokens=u.get('tokens'),
                       passed=val.count('pass'), review=val.count('review'), failed=val.count('fail'), screenshots=f"{len(shots)} of {len(b['screens'])}", output_kb=round(size / 1024, 1))
            rows.append(row); print(json.dumps(row))
            if a.out and v:
                d = Path(a.out) / f'{agent}-{n + 1}'; d.mkdir(parents=True, exist_ok=True)
                for f in shots: shutil.copyfile(f, d / f.name)
    cols = ['agent', 'run', 'status', 'seconds', 'per_screen_s', 'tokens', 'passed', 'review', 'failed', 'screenshots', 'output_kb']
    print('\n| ' + ' | '.join(cols) + ' |\n|' + '---|' * len(cols))
    for r in rows: print('| ' + ' | '.join('n/a' if r[c] is None else str(r[c]) for c in cols) + ' |')
    if a.out: (Path(a.out) / 'results.json').write_text(json.dumps(rows, indent=1)); print('\nSaved to', a.out)
    tmp.cleanup()

if __name__ == '__main__': main()
