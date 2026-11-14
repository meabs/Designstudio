"""Approval, immutable prototype bundles, screen mixing and review state."""

import json, time, re, shutil
from boards import blind_choice
from core import LOCK, allof, digest, get, safe_path, save, uid
from validation import validate
import core

PLAYER_JS = '''(function(){var P=window.parent;function send(){P.postMessage({type:"screen",file:location.pathname.split("/").pop(),title:document.title,help:document.querySelectorAll("details").length>0,error:document.querySelectorAll("[role=alert]").length>0},"*")}
window.addEventListener("message",function(e){if(e.source!==P)return;var m=e.data||{};if(m.cmd==="back")history.back();else if(m.cmd==="forward")history.forward();else if(m.cmd==="state"){document.querySelectorAll("details").forEach(function(x){x.open=m.name==="help"});document.querySelectorAll("[role=alert]").forEach(function(x){x.hidden=m.name!=="error"})}});
window.addEventListener("pageshow",send);send()})();
'''


def build_prototype(v):
    existing = next(
        (
            p
            for p in allof('prototype')
            if p['variant_id'] == v['id'] and (core.STORE / 'prototypes' / p['id']).is_dir()
        ),
        None,
    )
    if existing:
        return existing
    pid = uid()
    src = core.STORE / 'variants' / v['id']
    dst = core.STORE / 'prototypes' / pid
    shutil.copytree(src, dst)
    (dst / '_player').mkdir()
    (dst / '_player' / 'nav.js').write_text(PLAYER_JS)
    tag = '<script src="../_player/nav.js"></script>'
    for sc in v['manifest']['screens']:
        f = safe_path(dst, sc['file'])
        t = f.read_text()
        f.write_text(t.replace('</body>', tag + '</body>', 1) if '</body>' in t else t + tag)
    (dst / 'index.html').write_text(
        f'<meta http-equiv="refresh" content="0;url=screens/{v["manifest"]["start_screen_id"]}.html">'
    )
    board = get(v['board_id'])
    ctx = get(v['context_id'])
    return save(
        'prototype',
        dict(
            id=pid,
            variant_id=v['id'],
            board_id=v['board_id'],
            project_id=v['project_id'],
            version=v['version'],
            runner_name=v['runner_name'],
            board_title=board['title'],
            context_hash=ctx['hash'],
            bundle_path=f'prototypes/{pid}',
            screens=v['manifest']['screens'],
            start_screen_id=v['manifest']['start_screen_id'],
            edges=v['manifest']['edges'],
            created_at=time.time(),
        ),
    )


DECISIONS = ('approved', 'set_aside', 'accepted', 'reverted')


def record_decision(board_id, variant_id, decision, note=''):
    # The decision log: why a version was chosen or set aside. Stored on the board, newest last, never edited.
    if decision not in DECISIONS:
        raise ValueError('Unknown decision')
    b = get(board_id)
    v = get(variant_id)
    if v['board_id'] != board_id:
        raise ValueError('Choose a version from this board')
    b.setdefault('decisions', []).append(
        dict(id=uid(), variant_id=variant_id, decision=decision, note=str(note or '').strip()[:500], at=time.time())
    )
    return save('board', b)


def set_aside(variant_id, note=''):
    v = get(variant_id)
    if v.get('approved'):
        raise ValueError('An approved version is locked; approve another version first')
    return record_decision(v['board_id'], variant_id, 'set_aside', note)


def approve(variant_id, note=''):
    v = get(variant_id)
    if v.get('review_state') == 'reverted':
        raise ValueError('A reverted version cannot be approved; approve its parent or another version')
    with LOCK:
        if v.get('review_state') == 'pending':
            v['review_state'] = 'accepted'
            v['decided_at'] = time.time()
        for other in allof('variant'):
            if other['board_id'] == v['board_id'] and other['id'] != v['id'] and other.get('approved'):
                other['approved'] = False
                other['superseded_approval_at'] = time.time()
                save('variant', other)
        if not v.get('approved'):
            v['approved'] = True
            v['approved_at'] = time.time()
        save('variant', v)
        b = get(v['board_id'])
        if b.get('blind') and not b.get('revealed'):
            blind_choice(b['id'], v['id'], 'Approved')
        proto = build_prototype(v)
        record_decision(v['board_id'], v['id'], 'approved', note)
    return dict(variant=v, prototype=proto)


# ---- mixing: compose one new immutable version from screens of different versions ----
LINK_RE = re.compile(r'(href|src|poster|action)\s*=\s*(["\'])([^"\']*)\2', re.I)


def style_fingerprint(folder, page):
    text = page.read_text(errors='replace')
    for link in re.findall(r'<link[^>]+href\s*=\s*["\']([^"\']+\.css)[^"\']*["\']', text, re.I):
        f = (page.parent / link).resolve()
        if f.is_file() and f.is_relative_to(folder.resolve()):
            text += f.read_text(errors='replace')
    fonts = re.findall(r'font-family\s*:\s*([^;}{]+)', text, re.I)
    first = lambda x: re.split(r',', x)[0].strip().strip('"\'').lower()
    hexes = {}
    for h in re.findall(r'#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b', text):
        hexes[h.lower()] = hexes.get(h.lower(), 0) + 1
    return dict(
        font=first(fonts[0]) if fonts else None, colors=[h for h, _ in sorted(hexes.items(), key=lambda x: -x[1])[:3]]
    )


def mix_consistency(folder, entries, provenance):
    prints = {e['id']: style_fingerprint(folder, folder / e['file']) for e in entries}
    fonts = {p['font'] for p in prints.values() if p['font']}
    palettes = [set(p['colors']) for p in prints.values()]
    problems = []
    if len(fonts) > 1:
        problems.append('different primary fonts: ' + ', '.join(sorted(fonts)))
    if palettes and len(set.intersection(*palettes)) == 0 and all(palettes):
        problems.append('no dominant colour is shared by every screen')
    detail = '; '.join(
        f"screen {e['id']} ({next(p['name'] for p in provenance if p['screen']==e['id'])}): {prints[e['id']]['font'] or 'no font set'}, {', '.join(prints[e['id']]['colors']) or 'no colours'}"
        for e in entries
    )
    return dict(
        check='Cross-screen consistency (heuristic)',
        outcome='review',
        evidence=(
            ('Possible inconsistencies: ' + '; '.join(problems) + '. ')
            if problems
            else 'No differences in primary font or dominant colours were detected. '
        )
        + 'This compares CSS text only and is not a visual review. '
        + detail,
    )


def mix_variants(board_id, picks):
    board = get(board_id)
    ids = [str(i) for i in range(len(board['screens']))]
    if not isinstance(picks, dict) or set(map(str, picks)) != set(ids):
        raise ValueError('Choose a source version for every screen')
    sources = {}
    for sid in ids:
        v = sources.get(picks[sid]) or get(picks[sid])
        if v.get('board_id') != board_id or 'manifest' not in v:
            raise ValueError('Sources must be versions of this board')
        sources[v['id']] = v
    if len(sources) < 2:
        raise ValueError('Pick screens from at least two different versions; to keep one version, just use it')
    vid = uid()
    folder = core.STORE / 'variants' / vid
    (folder / 'screens').mkdir(parents=True)
    (folder / 'thumbnails').mkdir()
    try:
        for v in sources.values():
            src = core.STORE / 'variants' / v['id']
            for item in src.iterdir():
                if item.name in ('manifest.json', 'changes.json', 'screens', 'thumbnails') or item.is_symlink():
                    continue
                dst = folder / 'shared' / v['id'] / item.name
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(item, dst, symlinks=False) if item.is_dir() else shutil.copyfile(item, dst)

        def rewrite(text, src_id):
            root = (core.STORE / 'variants' / src_id).resolve()

            def sub(m):
                attr, q, link = m.groups()
                if link.startswith(('#', 'data:', 'mailto:', 'tel:', 'http:', 'https:', '//')) or not link:
                    return m.group(0)
                base = re.split(r'[?#]', link)[0]
                tail = link[len(base) :]
                target = (root / 'screens' / base).resolve()
                if not target.is_relative_to(root):
                    return m.group(0)
                rel = target.relative_to(root)
                if len(rel.parts) == 2 and rel.parts[0] == 'screens' and rel.suffix == '.html':
                    return m.group(0)
                return f'{attr}={q}../shared/{src_id}/{rel.as_posix()}{tail}{q}'

            return LINK_RE.sub(sub, text)

        entries = []
        edges = []
        changes = []
        provenance = []
        ctxs = [get(v['context_id']) for v in sources.values()]
        ctx = max(ctxs, key=lambda c: c['created_at'])
        blind = board.get('blind') and not board.get('revealed')
        name_of = lambda v: ('Option ' + str(v.get('blind_label') or '?')) if blind else v['runner_name']
        for sid in ids:
            v = sources[picks[sid]]
            src = core.STORE / 'variants' / v['id']
            entry = next((e for e in v['manifest']['screens'] if e['id'] == sid), None)
            if not entry:
                raise ValueError(f'{name_of(v)} v{v["version"]} has no screen {sid}')
            text = safe_path(src, entry['file']).read_text(errors='replace')
            (folder / 'screens' / f'{sid}.html').write_text(rewrite(text, v['id']))
            entries.append(
                dict(id=sid, title=entry['title'], file=f'screens/{sid}.html', states=entry.get('states', ['default']))
            )
            for e in v['manifest'].get('edges', []):
                if e['from'] == sid and e not in edges:
                    edges.append(e)
            thumb = src / 'thumbnails' / f'{sid}.png'
            if thumb.is_file():
                shutil.copyfile(thumb, folder / 'thumbnails' / f'{sid}.png')
            thumb_m = src / 'thumbnails' / f'{sid}-m.png'
            if thumb_m.is_file():
                shutil.copyfile(thumb_m, folder / 'thumbnails' / f'{sid}-m.png')
            changes.append(f"{entry['title']}: from {name_of(v)} v{v['version']}")
            provenance.append(dict(screen=sid, variant_id=v['id'], name=name_of(v), version=v['version']))
        first = sources[picks[ids[0]]]['manifest']
        manifest = dict(
            schema_version='1.0',
            kind='clickthrough-static',
            board_id=board_id,
            start_screen_id=first.get('start_screen_id', ids[0]) if first.get('start_screen_id') in ids else ids[0],
            screens=entries,
            edges=[e for e in edges if e['from'] in ids and e['to'] in ids],
        )
        (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2))
        validation = validate(folder, manifest, ctx['effective_rules'], ctx['tokens'])
        validation.append(mix_consistency(folder, entries, provenance))
        names = sorted({p['name'] + ' v' + str(p['version']) for p in provenance})
        validation.append(
            dict(
                check='Mixed provenance',
                outcome='review',
                evidence='Screens come from '
                + ', '.join(names)
                + '. Visual and copy consistency across screens is not checked automatically.',
            )
        )
        if len({c['id'] for c in ctxs}) > 1:
            validation.append(
                dict(
                    check='Mixed context versions',
                    outcome='review',
                    evidence='Sources were generated under different guideline versions (v'
                    + ', v'.join(str(c.get('version', '?')) for c in sorted(ctxs, key=lambda c: c['created_at']))
                    + '); the newest is recorded.',
                )
            )
        for sid in ids:
            if not (folder / 'thumbnails' / f'{sid}.png').is_file():
                validation.append(
                    dict(
                        check='Screenshot capture · ' + next(e['title'] for e in entries if e['id'] == sid),
                        outcome='not_assessable',
                        evidence='Source had no screenshot',
                    )
                )
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    jid = uid()
    count = len([v for v in allof('variant') if v['board_id'] == board_id and v.get('kind') == 'mix']) + 1
    label = 'Mix of ' + ' + '.join(dict.fromkeys(p['name'] for p in provenance))
    variant = dict(
        id=vid,
        project_id=board['project_id'],
        board_id=board_id,
        job_id=jid,
        runner_id=None,
        runner_name=label,
        kind='mix',
        style=None,
        parent_id=None,
        context_id=ctx['id'],
        version=count,
        approved=False,
        review_state=None,
        created_at=time.time(),
        changes=changes,
        changed_screens=[],
        references=[],
        mix_sources=provenance,
        manifest=manifest,
        validation=validation,
    )
    save('variant', variant)
    save(
        'job',
        dict(
            id=jid,
            project_id=board['project_id'],
            type='mix_board',
            runner_id=None,
            runner_name='Mix',
            status='succeeded',
            events=[
                dict(
                    time=time.time(),
                    message='Mixed ' + str(len(ids)) + ' screens from ' + str(len(sources)) + ' versions',
                )
            ],
            created_at=time.time(),
            board_id=board_id,
            variant_id=vid,
            context=ctx,
            input_hash=digest(picks),
            references=[],
            parent_id=None,
            annotations=[],
            brief=board['brief'],
        ),
    )
    return variant


def set_review_state(variant_id, state, note=''):
    v = get(variant_id)
    if not v.get('parent_id'):
        raise ValueError('Only revisions can be accepted or reverted')
    if v.get('approved') and state == 'reverted':
        raise ValueError('An approved version is locked; approve another version first')
    v['review_state'] = state
    v['decided_at'] = time.time()
    out = save('variant', v)
    record_decision(v['board_id'], v['id'], state, note)
    return out
