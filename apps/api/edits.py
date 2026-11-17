"""Manual (designer) edits: patch text and inline styles of identified elements into a new child version.

An edit never touches the parent. It is stored like an agent revision (parent_id, pending accept/revert, changed regions)
but is produced by the designer in the browser, so it costs no agent run. Only a small, safe vocabulary is accepted.
"""

import json, re, shutil, time, html
from core import LOCK, get, safe_path, save, uid
from regions import VOID_TAGS, diff_regions, element_spans
from validation import validate
import core

ALLOWED_PROPS = {
    'color', 'background-color', 'font-size', 'font-weight', 'font-family', 'font-style', 'line-height',
    'letter-spacing', 'text-align', 'text-decoration', 'text-transform', 'opacity', 'border-radius',
    'border-width', 'border-style', 'border-color', 'width', 'height', 'min-height', 'max-width', 'gap',
    'padding', 'padding-top', 'padding-right', 'padding-bottom', 'padding-left',
    'margin', 'margin-top', 'margin-right', 'margin-bottom', 'margin-left', 'display',
}
# Values are a conservative whitelist of characters: no quotes, braces, semicolons, angle brackets, backslashes or url().
VALUE_RE = re.compile(r'^[A-Za-z0-9#%.,()\s/_+-]{1,120}$')
DISPLAY_OK = {'none', 'block', 'flex', 'grid', 'inline', 'inline-block', 'inline-flex'}
MAX_EDITS = 200


def clean_style(prop, value):
    prop = str(prop).strip().lower()
    value = str(value).strip()
    if prop not in ALLOWED_PROPS:
        raise ValueError(f'Property not editable: {prop}')
    if value == '':
        return prop, ''  # empty removes this override
    if not VALUE_RE.match(value) or re.search(r'url\s*\(|expression|import|javascript', value, re.I):
        raise ValueError(f'Unsafe value for {prop}')
    if prop == 'display' and value not in DISPLAY_OK:
        raise ValueError('Unsupported display value')
    return prop, value


def start_tag_end(text, start):
    # Index just past the '>' that closes the start tag, skipping quoted attribute values.
    quote = None
    for i in range(start, len(text)):
        c = text[i]
        if quote:
            if c == quote:
                quote = None
        elif c in '"\'':
            quote = c
        elif c == '>':
            return i + 1
    raise ValueError('Malformed start tag')


STYLE_RE = re.compile(r'\sstyle\s*=\s*(?:"([^"]*)"|\'([^\']*)\')', re.I)


def parse_declarations(css):
    out = {}
    for part in (css or '').split(';'):
        if ':' in part:
            k, v = part.split(':', 1)
            if k.strip():
                out[k.strip().lower()] = v.strip()
    return out


def patch_element(text, design_id, style=None, new_text=None):
    spans = element_spans(text)
    if design_id not in spans:
        raise ValueError(f'No element with id {design_id}')
    a, b = spans[design_id]
    tag_end = start_tag_end(text, a)
    tag = text[a:tag_end]
    tag_name = re.match(r'<([A-Za-z][\w-]*)', tag).group(1).lower()
    inner_start, inner_end = tag_end, b
    if tag_name not in VOID_TAGS:
        inner_end = text.rfind('</', a, b)
    if style:
        m = STYLE_RE.search(tag)
        decl = parse_declarations(m.group(1) if m and m.group(1) is not None else (m.group(2) if m else ''))
        for k, v in style.items():
            k, v = clean_style(k, v)
            if v == '':
                decl.pop(k, None)
            else:
                decl[k] = v
        css = '; '.join(f'{k}: {v}' for k, v in decl.items())
        if m:
            tag = tag[: m.start()] + (f' style="{css}"' if css else '') + tag[m.end() :]
        elif css:
            tag = re.sub(r'(\s*/?>)$', lambda mm: f' style="{css}"' + mm.group(1), tag, count=1)
    if new_text is not None:
        if tag_name in VOID_TAGS or inner_end < inner_start:
            raise ValueError(f'{design_id} has no editable text')
        if '<' in text[inner_start:inner_end]:
            raise ValueError(f'{design_id} contains other elements; edit its children instead')
        if len(new_text) > 2000:
            raise ValueError('Text is too long')
        return text[:a] + tag + html.escape(str(new_text), quote=False) + text[inner_end:b] + text[b:]
    return text[:a] + tag + text[tag_end:]


def apply_edits(text, edits):
    for e in edits:
        did = e.get('design_id')
        if not isinstance(did, str) or not did:
            raise ValueError('Every edit needs a design_id')
        style = e.get('style')
        if style is not None and not isinstance(style, dict):
            raise ValueError('style must be an object')
        new_text = e.get('text')
        if style is None and new_text is None:
            continue
        text = patch_element(text, did, style, new_text)
    return text


def describe(screen_title, edits):
    out = []
    for e in edits:
        bits = [f'{k}: {v or "reset"}' for k, v in (e.get('style') or {}).items()]
        if e.get('text') is not None:
            bits.append('text')
        if bits:
            out.append(f'{screen_title} · {e["design_id"]}: ' + ', '.join(bits))
    return out


def manual_edit(variant_id, by_screen, note=''):
    """by_screen: {screen_id: [{design_id, style?: {prop: value}, text?: str}]} -> new child version."""
    parent = get(variant_id)
    if 'manifest' not in parent:
        raise ValueError('Only a finished version can be edited')
    if not isinstance(by_screen, dict) or not by_screen:
        raise ValueError('Nothing to change')
    if sum(len(v) for v in by_screen.values() if isinstance(v, list)) > MAX_EDITS:
        raise ValueError('Too many edits in one version')
    board = get(parent['board_id'])
    screens = {s['id']: s for s in parent['manifest']['screens']}
    for sid, edits in by_screen.items():
        if sid not in screens or not isinstance(edits, list):
            raise ValueError(f'Unknown screen {sid}')
    ctx = get(parent['context_id'])
    vid = uid()
    jid = uid()
    folder = core.STORE / 'variants' / vid
    src = core.STORE / 'variants' / parent['id']
    try:
        shutil.copytree(src, folder, ignore=shutil.ignore_patterns('changes.json'), symlinks=True)
        changes = []
        scope = {}
        for sid, edits in by_screen.items():
            entry = screens[sid]
            page = safe_path(folder, entry['file'])
            before = page.read_text(errors='replace')
            after = apply_edits(before, edits)
            if after == before:
                continue
            page.write_text(after)
            changes += describe(entry['title'], edits)
            scope[sid] = {'mode': 'region', 'elements': sorted({e['design_id'] for e in edits})}
        if not changes:
            raise ValueError('Those edits do not change anything')
        manifest = parent['manifest']
        validation = validate(folder, manifest, ctx['effective_rules'], ctx['tokens'])
        changed_regions = {}
        for sid, entry in screens.items():
            was = safe_path(src, entry['file']).read_text(errors='replace')
            now = safe_path(folder, entry['file']).read_text(errors='replace')
            if was == now:
                continue
            d = diff_regions(was, now)
            changed_regions[sid] = d
            extra = [x for x in d['elements'] if x not in scope.get(sid, {}).get('elements', [])]
            validation.append(
                dict(
                    check='Manual edit scope · ' + entry['title'],
                    outcome='fail' if (extra or d['outside']) else 'pass',
                    evidence=(
                        'Changed beyond the edited element(s): ' + ', '.join(extra + (['page content'] if d['outside'] else []))
                        if (extra or d['outside'])
                        else 'Only the edited element(s) changed: ' + ', '.join(d['elements'])
                    ),
                )
            )
        validation.append(
            dict(
                check='Manual edit',
                outcome='review',
                evidence='Made by hand in the studio, not by an agent. Text and inline-style overrides only; review the result on screen.',
            )
        )
        (folder / 'changes.json').write_text(json.dumps(changes))
        from boards import frame_of
        from jobs import chrome_screenshot

        (folder / 'thumbnails').mkdir(exist_ok=True)
        for sid in changed_regions:
            entry = screens[sid]
            page = safe_path(folder, entry['file'])
            png = folder / 'thumbnails' / f'{sid}.png'
            png.unlink(missing_ok=True)
            chrome_screenshot(jid, page, png, size=frame_of(board, 'd'))
            if board.get('target') == 'both':
                pm = folder / 'thumbnails' / f'{sid}-m.png'
                pm.unlink(missing_ok=True)
                chrome_screenshot(jid, page, pm, size=frame_of(board, 'm'))
            if not png.is_file():
                validation.append(
                    dict(check='Screenshot capture · ' + entry['title'], outcome='not_assessable', evidence='Local Chrome capture unavailable')
                )
        shutil.rmtree(f'/tmp/studio-chrome-{jid}', ignore_errors=True)
    except Exception:
        shutil.rmtree(folder, ignore_errors=True)
        raise
    with LOCK:
        variant = dict(
            id=vid,
            project_id=parent['project_id'],
            board_id=parent['board_id'],
            job_id=jid,
            runner_id=parent.get('runner_id'),
            runner_name=parent['runner_name'],
            kind='edit',
            style=parent.get('style'),
            parent_id=parent['id'],
            context_id=parent['context_id'],
            profile_id=parent.get('profile_id', 'main'),
            profile_name=parent.get('profile_name', 'Main'),
            blind_label=parent.get('blind_label'),
            version=parent['version'] + 1,
            approved=False,
            review_state='pending',
            created_at=time.time(),
            changes=changes,
            changed_screens=sorted(changed_regions),
            changed_regions=changed_regions,
            revision_scope=scope,
            references=[],
            manifest=manifest,
            validation=validation,
            edit_note=note[:500],
        )
        save('variant', variant)
        save(
            'job',
            dict(
                id=jid,
                project_id=parent['project_id'],
                type='manual_edit',
                runner_id=parent.get('runner_id'),
                runner_name='Manual edit',
                status='succeeded',
                events=[dict(time=time.time(), message='Edited ' + str(len(changes)) + ' element(s) by hand')],
                created_at=time.time(),
                board_id=parent['board_id'],
                variant_id=vid,
                context=ctx,
                input_hash=uid(),
                references=[],
                parent_id=parent['id'],
                annotations=[],
                brief=board['brief'],
            ),
        )
    return variant
