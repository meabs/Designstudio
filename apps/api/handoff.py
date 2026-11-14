"""Developer hand-off package: the approved design as a clean folder a developer can open, plus the guidelines it was built to."""

import io, json, time, zipfile
import core
from core import get

SKIP = {'thumbnails', 'changes.json'}


def slug(s):
    return ''.join(c.lower() if c.isalnum() else '-' for c in s).strip('-')[:40] or 'design'


def build_handoff(rec):
    """rec: an approved prototype or a variant. Returns (filename, zip bytes). Never names the agent that made it."""
    proto = 'variant_id' in rec
    v = get(rec['variant_id']) if proto else rec
    folder = core.STORE / ('prototypes' if proto else 'variants') / rec['id']
    ctx = get(v['context_id'])
    board = get(v['board_id'])
    project = get(v['project_id'])
    tokens = ctx.get('tokens') or {}
    name = slug(f'{project["name"]}-{board["title"]}-v{v["version"]}')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        for f in sorted(folder.rglob('*')):
            rel = f.relative_to(folder)
            if f.is_file() and not f.is_symlink() and not (set(rel.parts) & SKIP):
                z.write(f, f'{name}/site/{rel}')
        start = (v.get('manifest') or {}).get('start_screen_id', '0')
        z.writestr(f'{name}/site/index.html', f'<meta http-equiv="refresh" content="0;url=screens/{start}.html">')
        z.writestr(f'{name}/design/tokens.json', json.dumps(tokens, indent=2))
        z.writestr(f'{name}/design/tokens.css', ':root {\n' + ''.join(f'  --{k}: {val};\n' for k, val in tokens.items()) + '}\n')
        z.writestr(f'{name}/design/GUIDELINES.md', ctx.get('markdown') or '')
        z.writestr(f'{name}/design/rules.json', json.dumps(ctx.get('effective_rules', []), indent=2))
        screens = '\n'.join(f'- {s["title"]}: `site/{s["file"]}`' for s in (v.get('manifest') or {}).get('screens', []))
        checks = v.get('validation') or []
        passed = sum(1 for c in checks if c.get('outcome') == 'pass')
        note = rec.get('approval_note') or rec.get('note') or ''
        z.writestr(
            f'{name}/README.md',
            f'# {project["name"]} / {board["title"]} (version {v["version"]})\n\n'
            f'Exported {time.strftime("%Y-%m-%d")} from Design Studio. Open `site/index.html` in a browser; it is static HTML, CSS and JS with no build step.\n\n'
            f'## Screens\n{screens}\n\n'
            f'## Design inputs\n- `design/GUIDELINES.md`: the guidelines this was built against\n- `design/tokens.json` and `design/tokens.css`: design tokens\n- `design/rules.json`: the rules in force\n\n'
            f'## Checks\n{passed} of {len(checks)} automated checks passed when this was generated. '
            f'These are structural checks, not a compliance certification; an agent built the screens and a person approved them.\n'
            + (f'\n## Approval note\n{note}\n' if note else ''),
        )
    return name + '.zip', buf.getvalue()
