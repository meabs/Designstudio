"""Manual (designer) edits: patch text, inline styles and simple layout (move, duplicate, delete, add) into a new child version.

An edit never touches the parent. It is stored like an agent revision (parent_id, pending accept/revert, changed regions)
but is produced by the designer in the browser, so it costs no agent run. Only a small, safe vocabulary is accepted.
"""

import base64, binascii, hashlib, json, os, re, shutil, time, html
from core import LOCK, db, get, safe_path, save, uid
from regions import VOID_TAGS, _masked, diff_regions, element_spans
from validation import validate
import core

ALLOWED_PROPS = {
    'color', 'background-color', 'font-size', 'font-weight', 'font-family', 'font-style', 'line-height',
    'letter-spacing', 'text-align', 'text-decoration', 'text-transform', 'opacity', 'border-radius',
    'border-width', 'border-style', 'border-color', 'width', 'height', 'min-height', 'max-width', 'gap',
    'padding', 'padding-top', 'padding-right', 'padding-bottom', 'padding-left',
    'margin', 'margin-top', 'margin-right', 'margin-bottom', 'margin-left', 'display',
    'position', 'left', 'top', 'box-sizing',
}
# Values are a conservative whitelist of characters: no quotes, braces, semicolons, angle brackets, backslashes or url().
VALUE_RE = re.compile(r'^[A-Za-z0-9#%.,()\s/_+-]{1,120}$')
POSITION_OK = {'static', 'relative'}  # never absolute or fixed: free positioning is an offset from the element's normal place
BOX_OK = {'border-box', 'content-box'}
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
    if prop == 'position' and value not in POSITION_OK:
        raise ValueError('Only relative positioning is supported')
    if prop == 'box-sizing' and value not in BOX_OK:
        raise ValueError('Unsupported box-sizing value')
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


ANY_ID_RE = re.compile(r'(data-design-id\s*=\s*)(["\'])([^"\']*)\2')
PROTECTED = {'html', 'body', 'head'}
POSITIONS = {'before', 'after', 'inside'}
NEW_KINDS = {'text': ('p', 'New text'), 'button': ('button', 'Button')}


# Width-specific edits live in one generated block of media rules (with !important, so they beat the element's own inline style):
#   @media (max-width: 600px){[data-design-id="x"]{color:#fff !important}}   mobile only
#   @media (min-width: 601px){...}                                            desktop only
BREAKPOINT = 600
EDIT_BLOCK_RE = re.compile(r'<style data-studio-edits>(.*?)</style>\n?', re.S)
RULE_RE = re.compile(r'@media \((max|min)-width: (\d+)px\)\{\[data-design-id="([^"]+)"\]\{([^}]*)\}\}')
SAFE_ID = re.compile(r'^[A-Za-z0-9_.:-]{1,100}$')
AT = {'m': ('max', BREAKPOINT), 'd': ('min', BREAKPOINT + 1)}


def strip_edit_block(text):
    return EDIT_BLOCK_RE.sub('', text)


def patch_responsive(text, did, style, at):
    if at not in AT:
        raise ValueError('Unknown width')
    if not isinstance(style, dict) or not style:
        raise ValueError('A width-specific edit needs a style')
    if did not in element_spans(text):
        raise ValueError(f'No element with id {did}')
    if not SAFE_ID.match(did):
        raise ValueError('That element id cannot be styled per width')
    new = dict(clean_style(k, v) for k, v in style.items())
    m = EDIT_BLOCK_RE.search(text)
    rules = {}
    for x in RULE_RE.finditer(m.group(1)) if m else []:
        decl = {}
        for d in x.group(4).split(';'):
            if ':' in d:
                k, v = d.split(':', 1)
                decl[k.strip()] = v.replace('!important', '').strip()
        rules[('m' if x.group(1) == 'max' else 'd', x.group(3))] = decl
    cur = rules.setdefault((at, did), {})
    for k, v in new.items():
        if v == '':
            cur.pop(k, None)
        else:
            cur[k] = v
    out = []
    for (a, rid), decl in sorted(rules.items()):
        if decl:
            kind, px = AT[a]
            out.append(f'@media ({kind}-width: {px}px){{[data-design-id="{rid}"]{{' + ';'.join(f'{k}:{v} !important' for k, v in decl.items()) + '}}')
    text = EDIT_BLOCK_RE.sub('', text)
    if not out:
        return text
    block = '<style data-studio-edits>' + ''.join(out) + '</style>\n'
    at_i = text.lower().rfind('</html>')
    return (text[:at_i] + block + text[at_i:]) if at_i >= 0 else text + '\n' + block


def used_ids(text):
    return {m.group(3) for m in ANY_ID_RE.finditer(text)}


def fresh_copy_id(base, taken):
    # Deterministic: the browser preview uses the same rule, so ids agree before and after saving.
    c, n = base + '-copy', 2
    while c in taken:
        c, n = f'{base}-copy-{n}', n + 1
    taken.add(c)
    return c


def span_of(text, did):
    spans = element_spans(text)
    if did not in spans:
        raise ValueError(f'No element with id {did}')
    a, b = spans[did]
    name = re.match(r'<([A-Za-z][\w-]*)', text[a:]).group(1).lower()
    if name in PROTECTED:
        raise ValueError('That element cannot be changed')
    return a, b, name


def insertion_point(text, target, position):
    if position not in POSITIONS:
        raise ValueError('Unknown position')
    spans = element_spans(text)
    if target not in spans:
        raise ValueError(f'No element with id {target}')
    a, b = spans[target]
    name = re.match(r'<([A-Za-z][\w-]*)', text[a:]).group(1).lower()
    if position == 'before' or position == 'after':
        if name in PROTECTED:
            raise ValueError('Place it inside the page content instead')
        return a if position == 'before' else b
    if name in VOID_TAGS:
        raise ValueError(f'{target} cannot contain other elements')
    return text.rfind('</', a, b)


PRIMARY_RE = re.compile(r'\sdata-role\s*=\s*(["\'])primary-action\1', re.I)


def demote_primary(seg):
    # A copy is never the screen's primary action: the original keeps that role, so "one primary action" stays honest.
    return PRIMARY_RE.sub('', seg)


def op_delete(text, did):
    a, b, _ = span_of(text, did)
    return text[:a] + text[b:], set()


def op_duplicate(text, did):
    a, b, _ = span_of(text, did)
    taken = used_ids(text)
    made = []

    def rename(m):
        new = fresh_copy_id(m.group(3), taken)
        made.append(new)
        return f'{m.group(1)}"{new}"'

    seg = demote_primary(ANY_ID_RE.sub(rename, text[a:b]))
    return text[:b] + seg + text[b:], set(made)


def op_move(text, did, target, position):
    if did == target:
        raise ValueError('Cannot move an element relative to itself')
    a, b, _ = span_of(text, did)
    seg = text[a:b]
    rest = text[:a] + text[b:]
    if target not in element_spans(rest):
        raise ValueError('Cannot move an element into itself')
    at = insertion_point(rest, target, position)
    return rest[:at] + seg + rest[at:], {target}


def op_insert(text, target, position, kind):
    if kind not in NEW_KINDS:
        raise ValueError('Unknown element kind')
    tag, label = NEW_KINDS[kind]
    taken = used_ids(text)
    n = 1
    while f'new-{kind}-{n}' in taken:
        n += 1
    new = f'new-{kind}-{n}'
    attrs = ' type="button"' if tag == 'button' else ''
    snippet = f'<{tag}{attrs} data-design-id="{new}">{label}</{tag}>'
    at = insertion_point(text, target, position)
    return text[:at] + snippet + text[at:], {new, target}


IMG_RE = re.compile(r'^data:image/(png|jpeg);base64,([A-Za-z0-9+/=]+)$')
IMG_MAGIC = {'png': b'\x89PNG\r\n\x1a\n', 'jpeg': b'\xff\xd8\xff'}
MAX_IMAGE = 700_000


class Assets:
    """What an edit may reach beyond the page text: image files stored in the new version, and elements of the parent's other screens."""

    def __init__(self, folder=None, page=None, source=None):
        self.folder, self.page, self.source = folder, page, source

    def save_image(self, data_url):
        m = IMG_RE.match(data_url) if isinstance(data_url, str) else None
        if not m:
            raise ValueError('Images must be PNG or JPEG')
        try:
            raw = base64.b64decode(m.group(2), validate=True)
        except (binascii.Error, ValueError):
            raise ValueError('Image data is not valid')
        if len(raw) > MAX_IMAGE or not raw.startswith(IMG_MAGIC[m.group(1)]):
            raise ValueError('Image is too large or not a real image')
        if self.folder is None:
            raise ValueError('Images cannot be added here')
        name = 'img-' + hashlib.sha1(raw).hexdigest()[:10] + ('.png' if m.group(1) == 'png' else '.jpg')
        (self.folder / 'assets').mkdir(exist_ok=True)
        (self.folder / 'assets' / name).write_bytes(raw)
        return os.path.relpath(self.folder / 'assets' / name, self.page.parent).replace(os.sep, '/')

    def component(self, screen, did):
        if self.source is None:
            raise ValueError('Components are not available here')
        text = self.source(screen)
        a, b, _ = span_of(text, did)
        return text[a:b]


def set_attrs(text, did, attrs):
    a, b, name = span_of(text, did)
    end = start_tag_end(text, a)
    tag = text[a:end]
    for k, v in attrs.items():
        pat = re.compile(r'\s' + k + r'\s*=\s*(?:"[^"]*"|\'[^\']*\')', re.I)
        new = f' {k}="{html.escape(v, quote=True)}"'
        tag = pat.sub(new, tag, count=1) if pat.search(tag) else re.sub(r'\s*/?>$', lambda m: new + m.group(0).lstrip(), tag, count=1)
    return text[:a] + tag + text[end:], name


def op_image(text, did, data_url, alt, assets):
    if data_url is None and alt is None:
        raise ValueError('Nothing to change on that image')
    a, b, name = span_of(text, did)
    if name != 'img':
        raise ValueError('Only an image can take a picture')
    attrs = {}
    if data_url is not None:
        attrs['src'] = assets.save_image(data_url)
    if alt is not None:
        attrs['alt'] = str(alt)[:200]
    return set_attrs(text, did, attrs)[0], set()


def op_insert_image(text, target, position, data_url, alt, assets):
    taken = used_ids(text)
    n = 1
    while f'new-image-{n}' in taken:
        n += 1
    new = f'new-image-{n}'
    src = assets.save_image(data_url)
    at = insertion_point(text, target, position)
    snippet = f'<img data-design-id="{new}" src="{html.escape(src, quote=True)}" alt="{html.escape(str(alt or "Image")[:200], quote=True)}" style="max-width:100%;height:auto">'
    return text[:at] + snippet + text[at:], {new, target}


def op_component(text, screen, source_id, target, position, assets):
    seg = assets.component(screen, source_id)
    taken = used_ids(text)
    made = []

    def rename(m):
        new = fresh_copy_id(m.group(3), taken)
        made.append(new)
        return f'{m.group(1)}"{new}"'

    seg = demote_primary(ANY_ID_RE.sub(rename, seg))
    at = insertion_point(text, target, position)
    return text[:at] + seg + text[at:], set(made) | {target}


def apply_edits(text, edits, assets=None):
    """Apply an ordered list of edits. Returns (html, ids of every element an edit touched)."""
    touched = set()
    for e in edits:
        if not isinstance(e, dict):
            raise ValueError('Each edit must be an object')
        op = e.get('op')
        did = e.get('design_id')
        assets = assets or Assets()
        if op == 'insert':
            if e.get('kind') == 'image':
                text, t = op_insert_image(text, e.get('target_id'), e.get('position', 'after'), e.get('data_url'), e.get('alt'), assets)
            else:
                text, t = op_insert(text, e.get('target_id'), e.get('position', 'after'), e.get('kind'))
            touched |= t
            continue
        if op == 'component':
            text, t = op_component(text, str(e.get('source_screen')), e.get('source_id'), e.get('target_id'), e.get('position', 'after'), assets)
            touched |= t
            continue
        if not isinstance(did, str) or not did:
            raise ValueError('Every edit needs a design_id')
        if op == 'delete':
            text, t = op_delete(text, did)
        elif op == 'duplicate':
            text, t = op_duplicate(text, did)
        elif op == 'move':
            text, t = op_move(text, did, e.get('target_id'), e.get('position', 'after'))
        elif op == 'image':
            text, t = op_image(text, did, e.get('data_url'), e.get('alt'), assets)
        elif op is None:
            style = e.get('style')
            if style is not None and not isinstance(style, dict):
                raise ValueError('style must be an object')
            new_text = e.get('text')
            if style is None and new_text is None:
                continue
            if e.get('at'):
                if new_text is not None:
                    raise ValueError('Text cannot be set for one width only')
                text = patch_responsive(text, did, style, e['at'])
            else:
                text = patch_element(text, did, style, new_text)
            t = set()
        else:
            raise ValueError('Unknown edit operation')
        touched |= t | {did}
    return text, touched


PLACEHOLDER_RE = re.compile('\u27e6[^\u27e7]*\u27e7')


def outside_changed(before, after):
    # Content outside every identified element, ignoring where identified elements sit: adding, moving or removing one is expected.
    strip = lambda text: re.sub(r'\s+', ' ', PLACEHOLDER_RE.sub('', _masked(text, element_spans(text)))).strip()
    return strip(before) != strip(after)


def ancestors_of(text, ids):
    spans = element_spans(text)
    out = set()
    for i in ids:
        if i in spans:
            a, b = spans[i]
            out |= {j for j, (x, y) in spans.items() if x <= a and b <= y and j != i}
    return out


def describe(screen_title, edits):
    out = []
    for e in edits:
        op = e.get('op')
        if op == 'delete':
            out.append(f'{screen_title} · {e["design_id"]}: deleted')
        elif op == 'duplicate':
            out.append(f'{screen_title} · {e["design_id"]}: duplicated')
        elif op == 'move':
            out.append(f'{screen_title} · {e["design_id"]}: moved {e.get("position", "after")} {e.get("target_id")}')
        elif op == 'insert':
            out.append(f'{screen_title} · added {e.get("kind")} {e.get("position", "after")} {e.get("target_id")}')
        elif op == 'component':
            out.append(f'{screen_title} · inserted {e.get("source_id")} from screen {e.get("source_screen")} {e.get("position", "after")} {e.get("target_id")}')
        elif op == 'image':
            out.append(f'{screen_title} · {e["design_id"]}: ' + ('picture replaced' if e.get('data_url') else 'alt text'))
        else:
            where = {'m': ' (mobile only)', 'd': ' (desktop only)'}.get(e.get('at'), '')
            bits = [f'{k}{where}: {v or "reset"}' for k, v in (e.get('style') or {}).items()]
            if e.get('text') is not None:
                bits.append('text')
            if bits:
                out.append(f'{screen_title} · {e["design_id"]}: ' + ', '.join(bits))
    return out


COLOR_PROPS = ('color', 'background-color', 'border-color')
NEUTRAL = {'transparent', 'inherit', 'initial', 'currentcolor', 'unset'}


def hex_norm(v):
    v = v.strip().lower()
    m = re.fullmatch(r'#([0-9a-f]{3})', v)
    return '#' + ''.join(c * 2 for c in m.group(1)) if m else v


def colour_review(by_screen, tokens):
    """Colours typed or picked by hand that are not project tokens. Token colours are written as var(--name, #hex) and are fine."""
    known = {hex_norm(str(v)): k for k, v in (tokens or {}).items() if re.fullmatch(r'#[0-9a-fA-F]{3,8}', str(v))}
    off, on = set(), set()
    for edits in by_screen.values():
        for e in edits:
            for prop, val in ((e.get('style') or {}) if isinstance(e, dict) else {}).items():
                if prop not in COLOR_PROPS or not val or val.lower() in NEUTRAL:
                    continue
                if val.startswith('var('):
                    on.add(val)
                elif hex_norm(val) in known:
                    on.add(known[hex_norm(val)])
                else:
                    off.add(val.lower())
    return sorted(off), len(on)


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

        def source_text(s):
            if s not in screens:
                raise ValueError(f'Unknown screen {s}')
            return safe_path(src, screens[s]['file']).read_text(errors='replace')

        for sid, edits in by_screen.items():
            entry = screens[sid]
            page = safe_path(folder, entry['file'])
            before = page.read_text(errors='replace')
            after, touched = apply_edits(before, edits, Assets(folder, page, source_text))
            if after == before:
                continue
            page.write_text(after)
            changes += describe(entry['title'], edits)
            scope[sid] = {'mode': 'region', 'elements': sorted(touched)}
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
            d = diff_regions(strip_edit_block(was), strip_edit_block(now))
            d['elements'] = sorted(set(d['elements']) | {e['design_id'] for e in by_screen[sid] if isinstance(e, dict) and e.get('at') and e.get('design_id')})
            changed_regions[sid] = d
            allowed = set(scope.get(sid, {}).get('elements', []))
            allowed |= ancestors_of(was, allowed) | ancestors_of(now, allowed)  # moving or adding a child changes its containers too
            extra = [x for x in d['elements'] if x not in allowed]
            if any(isinstance(e, dict) and e.get('op') for e in by_screen[sid]):
                d = dict(d, outside=outside_changed(strip_edit_block(was), strip_edit_block(now)))
                changed_regions[sid] = d
            validation.append(
                dict(
                    check='Manual edit scope · ' + entry['title'],
                    outcome='fail' if (extra or d['outside']) else 'pass',
                    evidence=(
                        'Changed beyond the edited element(s): ' + ', '.join(extra + (['page content'] if d['outside'] else []))
                        if (extra or d['outside'])
                        else 'Only the edited element(s) and their containers changed: ' + ', '.join(d['elements'])
                    ),
                )
            )
        off, n_tok = colour_review(by_screen, ctx.get('tokens'))
        if off:
            validation.append(
                dict(
                    check='Manual edit colours',
                    outcome='review',
                    evidence='Not a project token: ' + ', '.join(off[:8]) + '. Use a token swatch so a later token change reaches this element, or add the colour to the tokens.',
                )
            )
        elif n_tok:
            validation.append(dict(check='Manual edit colours', outcome='pass', evidence=f'{n_tok} colour change(s) use project tokens'))
        validation.append(
            dict(
                check='Manual edit',
                outcome='review',
                evidence='Made by hand in the studio, not by an agent. Text, inline-style overrides, offsets and sizes, images, and layout changes (move, duplicate, delete, add, insert from another screen); review the result on screen.',
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


# ---------- server-side drafts: the same edit log, kept so a draft follows the designer to another browser ----------
MAX_DRAFT_BYTES = 6_000_000


def draft_get(variant_id):
    try:
        d = get('draft-' + variant_id)
    except ValueError:
        return dict(variant_id=variant_id, logs={}, updated_at=0)
    return d


def draft_save(variant_id, logs):
    v = get(variant_id)
    if 'manifest' not in v:
        raise ValueError('Only a finished version can be edited')
    if not isinstance(logs, dict):
        raise ValueError('Draft must be an object')
    logs = {k: x for k, x in logs.items() if isinstance(x, list) and x}
    if sum(len(x) for x in logs.values()) > MAX_EDITS or len(json.dumps(logs)) > MAX_DRAFT_BYTES:
        raise ValueError('Draft is too large')
    if not logs:
        with LOCK, db() as c:
            c.execute('DELETE FROM entities WHERE id=?', ('draft-' + variant_id,))
        return dict(variant_id=variant_id, logs={}, updated_at=0)
    return save('draft', dict(id='draft-' + variant_id, variant_id=variant_id, logs=logs, updated_at=time.time()))
