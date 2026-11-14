"""Manual audit of a finished design, plus the review-documents folder and style extraction.

Everything here is deterministic and evidence-based: it reads the static package, never runs it, and never claims
conformance. Criteria from the designer's own markdown documents are either checked as literal phrases (when the
document says what must or must not appear) or listed for human review with the source file and line.
"""

import re, time, html as htmllib
from html.parser import HTMLParser
from pathlib import Path
import core
from contexts import current_context
from core import allof, digest, get, save, uid, safe_path

MAX_DOCS = 60
MAX_DOC_BYTES = 200_000
MAX_CRITERIA = 300
AREAS = ('accessibility', 'legal', 'content', 'design-review')
VOID = {'br', 'hr', 'img', 'input', 'meta', 'link', 'source', 'area', 'base', 'col', 'embed', 'param', 'track', 'wbr'}
NAMELESS_LINK = re.compile(r'^(click here|here|read more|more|link|this)$', re.I)


# ---------- review documents ----------
def doc_area(heading):
    h = heading.lower()
    if re.search(r'accessib|a11y|wcag|inclusi|contrast|screen ?reader', h):
        return 'accessibility'
    if re.search(r'legal|compliance|regulat|fca|gdpr|privacy|consent|consumer|terms|disclos|risk|policy|ccpa|sec\b', h):
        return 'legal'
    if re.search(r'content|copy|voice|tone|plain|language|writing', h):
        return 'content'
    return 'design-review'


def read_review_folder(path):
    # Read-only. Markdown only, no symlinks, bounded size and count, never leaves the chosen folder.
    path = str(path or '').strip()
    if not path:
        return dict(folder='', docs=[], skipped=[], error='')
    root = Path(path).expanduser()
    if not root.is_dir():
        return dict(folder=path, docs=[], skipped=[], error='Folder not found. Enter the full path to a folder of .md files.')
    root = root.resolve()
    docs, skipped = [], []
    for f in sorted(root.rglob('*.md')):
        if len(docs) >= MAX_DOCS:
            skipped.append(f'{f.relative_to(root)} (over the {MAX_DOCS}-file limit)')
            continue
        if f.is_symlink() or not f.is_file() or not f.resolve().is_relative_to(root):
            skipped.append(f'{f.relative_to(root)} (symlink or outside the folder)')
            continue
        if f.stat().st_size > MAX_DOC_BYTES:
            skipped.append(f'{f.relative_to(root)} (over {MAX_DOC_BYTES // 1000} KB)')
            continue
        text = f.read_text(errors='replace')
        title = next((l.lstrip('# ').strip() for l in text.splitlines() if l.startswith('#')), f.stem)
        docs.append(dict(file=str(f.relative_to(root)), title=title, text=text, criteria=criteria_of(text)))
    return dict(folder=str(root), docs=docs, skipped=skipped, error='')


CHECKBOX = re.compile(r'^\s*[-*+]\s*\[( |x|X)\]\s*(.+)$')
BULLET = re.compile(r'^\s*(?:[-*+]|\d+[.)])\s+(.+)$')
STRONG = re.compile(r'\b(must|must not|never|always|required|do not|don\'t|shall)\b', re.I)
QUOTED = re.compile(r'["“‘\']([^"”’\']{2,120})["”’\']')
MUST_HAVE = re.compile(r'\b(?:must|should|need to|needs to|shall|always)\s+(?:also\s+)?(?:include|mention|show|display|contain|state|say|have|use)\b', re.I)
MUST_NOT = re.compile(r'\b(?:must not|should not|never|do not|don\'t|shall not|avoid)\s+(?:use|include|say|mention|show|display|contain|state)?\b', re.I)


def criteria_of(text):
    out, area = [], 'design-review'
    for n, line in enumerate(text.splitlines(), 1):
        if line.startswith('#'):
            area = doc_area(line.lstrip('# '))
            continue
        m = CHECKBOX.match(line)
        body = m.group(2).strip() if m else None
        if body is None:
            b = BULLET.match(line)
            if b and STRONG.search(b.group(1)):
                body = b.group(1).strip()
        if not body:
            continue
        phrases = [p.strip() for p in QUOTED.findall(body)]
        kind = 'review'
        if phrases and MUST_NOT.search(body) and not MUST_HAVE.search(body):
            kind = 'forbid'
        elif phrases and MUST_HAVE.search(body):
            kind = 'require'
        out.append(dict(line=n, area=area, text=body[:400], kind=kind, phrases=phrases[:6] if kind != 'review' else []))
        if len(out) >= MAX_CRITERIA:
            break
    return out


# ---------- colour maths ----------
def parse_color(value, vars_):
    v = (value or '').strip().lower()
    for _ in range(4):
        m = re.match(r'var\(\s*(--[\w-]+)\s*(?:,\s*(.+))?\)$', v)
        if not m:
            break
        v = (vars_.get(m.group(1)) or (m.group(2) or '')).strip().lower()
    names = {'white': '#ffffff', 'black': '#000000', 'transparent': ''}
    v = names.get(v, v)
    m = re.match(r'#([0-9a-f]{3}|[0-9a-f]{6})$', v)
    if m:
        h = m.group(1)
        h = ''.join(c * 2 for c in h) if len(h) == 3 else h
        return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))
    m = re.match(r'rgba?\(\s*(\d+)[ ,]+(\d+)[ ,]+(\d+)', v)
    if m:
        return tuple(int(x) for x in m.groups())
    return None


def luminance(rgb):
    def f(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4

    r, g, b = (f(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    la, lb = luminance(a), luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


# ---------- page facts ----------
class Page(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lang = None
        self.title = ''
        self.viewport = False
        self.headings, self.imgs, self.controls, self.names, self.links = [], [], [], [], []
        self.labels_for, self.text, self.styles, self.tabindex = set(), [], [], []
        self.inline = []
        self._stack, self._in_title, self._in_style, self._skip = [], False, False, 0
        self._label = 0

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == 'html':
            self.lang = a.get('lang')
        if tag == 'title':
            self._in_title = True
        if tag == 'style':
            self._in_style = True
        if tag in ('script', 'style'):
            self._skip += 1
        if tag == 'meta' and a.get('name', '').lower() == 'viewport':
            self.viewport = 'width=device-width' in a.get('content', '').replace(' ', '')
        if re.fullmatch(r'h[1-6]', tag):
            self.headings.append([int(tag[1]), ''])
        if tag == 'img':
            self.imgs.append(a)
        if tag == 'label':
            self._label += 1
            if a.get('for'):
                self.labels_for.add(a['for'])
        if tag in ('input', 'select', 'textarea') and a.get('type', '').lower() not in ('hidden', 'submit', 'button', 'image', 'reset'):
            self.controls.append(dict(a, _tag=tag, _wrapped=self._label > 0))
        if tag in ('button', 'a'):
            self.names.append(dict(a, _tag=tag, _text=''))
        if a.get('tabindex', '').lstrip('-').isdigit() and int(a['tabindex']) > 0:
            self.tabindex.append(tag)
        if a.get('style'):
            self.inline.append((tag, a['style'], a))
        if tag not in VOID:
            self._stack.append(tag)

    def handle_endtag(self, tag):
        if tag == 'title':
            self._in_title = False
        if tag == 'style':
            self._in_style = False
        if tag in ('script', 'style'):
            self._skip = max(0, self._skip - 1)
        if tag == 'label':
            self._label = max(0, self._label - 1)
        if tag in self._stack:
            while self._stack and self._stack.pop() != tag:
                pass

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        if self._in_style:
            self.styles.append(data)
        if self._skip:
            return
        t = data.strip()
        if not t:
            return
        self.text.append(t)
        if self.headings and any(re.fullmatch(r'h[1-6]', s) for s in self._stack[-1:]):
            self.headings[-1][1] += t
        for n in reversed(self.names):
            if n['_tag'] in self._stack:
                n['_text'] += t
                break


def css_rules(css, vars_):
    out = []
    for sel, body in re.findall(r'([^{}@]+)\{([^{}]*)\}', css):
        props = {}
        for p in body.split(';'):
            if ':' in p:
                k, v = p.split(':', 1)
                props[k.strip().lower()] = v.strip()
        for k, v in props.items():
            if k.startswith('--'):
                vars_.setdefault(k, v)
        out.append((' '.join(sel.split()), props))
    return out


def px(v):
    m = re.match(r'(-?[\d.]+)px$', (v or '').strip())
    return float(m.group(1)) if m else None


def snippet(tag, a):
    bits = ''.join(f' {k}="{str(v)[:30]}"' for k, v in a.items() if not k.startswith('_') and k in ('id', 'class', 'name', 'type', 'href', 'src', 'data-design-id'))
    return f'<{tag}{bits}>'


def audit_screen(raw, tokens):
    p = Page()
    p.feed(raw)
    vars_ = {'--' + k: str(v) for k, v in (tokens or {}).items()}
    rules = []
    for css in p.styles:
        rules += css_rules(css, vars_)
    res = []

    def add(area, check, outcome, evidence):
        res.append(dict(area=area, check=check, outcome=outcome, evidence=evidence))

    add('accessibility', 'Page language declared (WCAG 3.1.1)', 'pass' if p.lang else 'fail', f'lang="{p.lang}"' if p.lang else 'The <html> element has no lang attribute.')
    add('accessibility', 'Page title (WCAG 2.4.2)', 'pass' if p.title.strip() else 'fail', p.title.strip() or 'No <title> text.')
    add('accessibility', 'Responsive viewport declared', 'pass' if p.viewport else 'fail', 'meta viewport has width=device-width' if p.viewport else 'Missing <meta name="viewport" content="width=device-width, initial-scale=1">; phones will render a zoomed-out desktop page.')
    h1 = [h for h in p.headings if h[0] == 1]
    levels = [h[0] for h in p.headings]
    skipped = [f'h{b} after h{a}' for a, b in zip(levels, levels[1:]) if b > a + 1]
    add('accessibility', 'One main heading, no skipped levels (WCAG 1.3.1)', 'pass' if len(h1) == 1 and not skipped else 'fail', (f'{len(h1)} h1' + (f'; skipped: {", ".join(skipped)}' if skipped else '')) if (len(h1) != 1 or skipped) else 'One h1; heading levels in order.')
    bad_img = [i for i in p.imgs if 'alt' not in i]
    add('accessibility', 'Images have alternative text (WCAG 1.1.1)', 'fail' if bad_img else ('pass' if p.imgs else 'not_assessable'), (f'{len(bad_img)} image(s) without alt: ' + ', '.join(snippet('img', i) for i in bad_img[:3])) if bad_img else (f'{len(p.imgs)} image(s), all with alt.' if p.imgs else 'No images on this screen.'))
    unl = [c for c in p.controls if not (c.get('aria-label') or c.get('aria-labelledby') or c.get('title') or c['_wrapped'] or (c.get('id') and c['id'] in p.labels_for))]
    add('accessibility', 'Form fields have labels (WCAG 3.3.2 / 4.1.2)', 'fail' if unl else ('pass' if p.controls else 'not_assessable'), ('Unlabelled: ' + ', '.join(snippet(c['_tag'], c) for c in unl[:3])) if unl else (f'{len(p.controls)} field(s) labelled.' if p.controls else 'No form fields on this screen.'))
    unnamed = [n for n in p.names if not (n['_text'].strip() or n.get('aria-label') or n.get('aria-labelledby') or n.get('title'))]
    add('accessibility', 'Buttons and links have a name (WCAG 4.1.2)', 'fail' if unnamed else 'pass', ('No accessible name: ' + ', '.join(snippet(n['_tag'], n) for n in unnamed[:3])) if unnamed else f'{len(p.names)} buttons/links named.')
    vague = [n['_text'].strip() for n in p.names if n['_tag'] == 'a' and NAMELESS_LINK.match(n['_text'].strip())]
    if vague:
        add('accessibility', 'Link text describes its destination (WCAG 2.4.4)', 'review', 'Vague link text: ' + ', '.join(f'“{v}”' for v in vague[:4]))
    if p.tabindex:
        add('accessibility', 'No positive tabindex (WCAG 2.4.3)', 'fail', 'Positive tabindex on: ' + ', '.join(p.tabindex[:4]))
    # contrast: every rule that sets a text colour; background from the same rule, else the body background, else white
    body_bg = next((parse_color(pr.get('background') or pr.get('background-color'), vars_) for s, pr in rules if re.fullmatch(r'(html|body|html,\s*body|body,\s*html)', s) and (pr.get('background') or pr.get('background-color'))), None) or (255, 255, 255)
    body_fg = next((parse_color(pr.get('color'), vars_) for s, pr in rules if re.fullmatch(r'(html|body|html,\s*body|body,\s*html)', s) and pr.get('color')), None)
    pairs = []
    for s, pr in rules:
        fg = parse_color(pr.get('color'), vars_)
        if not fg:
            continue
        bg = parse_color(pr.get('background') or pr.get('background-color'), vars_) or body_bg
        pairs.append((s[:40], fg, bg))
    if body_fg is None and not pairs:
        add('accessibility', 'Text contrast (WCAG 1.4.3)', 'not_assessable', 'No explicit text colours found in CSS to measure.')
    else:
        low = [(s, round(contrast(fg, bg), 2)) for s, fg, bg in pairs if contrast(fg, bg) < 4.5]
        worst = min((round(contrast(fg, bg), 2) for s, fg, bg in pairs), default=None)
        add('accessibility', 'Text contrast, minimum 4.5:1 (WCAG 1.4.3)', 'fail' if low else 'pass', ('Below 4.5:1: ' + '; '.join(f'{s} = {c}:1' for s, c in low[:4]) + '. Large text (24px, or 19px bold) may use 3:1; check manually.') if low else f'{len(pairs)} colour pair(s) measured; lowest {worst}:1. Opacity, gradients and images are not measured.')
    small = []
    undersized = []
    for s, pr in rules:
        fs = px(pr.get('font-size'))
        if fs is not None and fs < 12:
            small.append(f'{s[:30]} {fs:g}px')
        if re.search(r'(^|[ ,.])(button|input|select|a\.primary|\.primary|\.btn|\.button)\b', s):
            for key in ('height', 'min-height'):
                h = px(pr.get(key))
                if h is not None and h < 44:
                    undersized.append(f'{s[:30]} {key} {h:g}px')
    for tag, style, a in p.inline:
        for m in re.finditer(r'font-size\s*:\s*([\d.]+)px', style):
            if float(m.group(1)) < 12:
                small.append(f'{snippet(tag, a)} {m.group(1)}px')
    add('accessibility', 'Text is not smaller than 12px', 'review' if small else 'pass', ('Small text: ' + '; '.join(small[:5])) if small else 'No font-size under 12px declared.')
    add('accessibility', 'Tap targets, 44px recommended', 'fail' if undersized else 'not_assessable', ('Declared smaller than 44px: ' + '; '.join(undersized[:4])) if undersized else 'No explicit sizes under 44px; rendered size from padding is not measured by this static check.')
    wide = [f'{s[:30]} {k} {v}' for s, pr in rules for k, v in pr.items() if k in ('width', 'min-width') and (px(v) or 0) > 480]
    add('accessibility', 'No fixed width that overflows a phone (WCAG 1.4.10)', 'review' if wide else 'pass', ('Fixed widths above 480px: ' + '; '.join(wide[:4])) if wide else 'No fixed widths over 480px declared.')
    return res, ' '.join(p.text), p


def audit_variant(variant_id):
    v = get(variant_id)
    folder = core.STORE / 'variants' / v['id']
    manifest = v.get('manifest') or {}
    p = get(v['project_id']) if v.get('project_id') else None
    tokens = {}
    ctx = None
    try:
        ctx = get(v.get('context_id') or (p or {}).get('context_id'))
        tokens = v.get('applied_tokens') or ctx.get('tokens', {})
    except ValueError:
        pass
    findings, texts = [], {}
    for s in manifest.get('screens', []):
        f = safe_path(folder, s['file'])
        raw = f.read_text(errors='replace')
        res, text, _ = audit_screen(raw, tokens)
        texts[s['id']] = (s['title'], text)
        for r in res:
            findings.append(dict(r, screen=s['id'], screen_title=s['title'], source=''))
    folder_info = read_review_folder((p or {}).get('review_folder', ''))
    for d in folder_info['docs']:
        for c in d['criteria']:
            src = f'{d["file"]}:{c["line"]}'
            if c['kind'] == 'require':
                for ph in c['phrases']:
                    where = [t for t, tx in texts.values() if ph.lower() in tx.lower()]
                    findings.append(dict(area=c['area'], check=c['text'], outcome='pass' if where else 'fail', evidence=(f'“{ph}” found on: {", ".join(where)}' if where else f'“{ph}” does not appear on any screen.'), screen='', screen_title='All screens', source=src))
            elif c['kind'] == 'forbid':
                for ph in c['phrases']:
                    where = [t for t, tx in texts.values() if ph.lower() in tx.lower()]
                    findings.append(dict(area=c['area'], check=c['text'], outcome='fail' if where else 'pass', evidence=(f'“{ph}” appears on: {", ".join(where)}' if where else f'“{ph}” does not appear on any screen.'), screen='', screen_title='All screens', source=src))
            else:
                findings.append(dict(area=c['area'], check=c['text'], outcome='review', evidence='From your document; needs a designer or specialist to judge. Not checked automatically.', screen='', screen_title='All screens', source=src))
    # The same finding on several screens is one row that names them all, so a shared footer isn't reported seven times.
    merged = {}
    for f in findings:
        k = (f['area'], f['check'], f['outcome'], f['evidence'], f['source'])
        if k in merged and f['screen']:
            m = merged[k]
            m['screens'].append(f['screen'])
            m['screen_title'] += ', ' + f['screen_title']
        else:
            merged[k] = dict(f, screens=[f['screen']] if f['screen'] else [])
    findings = list(merged.values())
    for i, f in enumerate(findings):
        f['index'] = i
    counts = {k: sum(1 for f in findings if f['outcome'] == k) for k in ('pass', 'fail', 'review', 'not_assessable')}
    a = dict(
        id=uid(),
        at=time.time(),
        folder=folder_info['folder'],
        folder_error=folder_info['error'],
        docs=[dict(file=d['file'], title=d['title'], criteria=len(d['criteria'])) for d in folder_info['docs']],
        skipped=folder_info['skipped'],
        docs_hash=digest([(d['file'], d['text']) for d in folder_info['docs']]),
        counts=counts,
        findings=findings,
        note='Static checks on the delivered HTML/CSS plus literal phrase checks from your documents. This is evidence for a human reviewer, not a certification of accessibility or legal compliance.',
    )
    v.setdefault('audits', []).append(a)
    v['audits'] = v['audits'][-10:]
    save('variant', v)
    return a


def audit_review(variant_id, audit_id, index, decision, note=''):
    v = get(variant_id)
    a = next((x for x in v.get('audits', []) if x['id'] == audit_id), None)
    if not a or not 0 <= int(index) < len(a['findings']):
        raise ValueError('Audit finding not found')
    if decision not in ('accepted', 'needs_change', 'open'):
        raise ValueError('Unknown decision')
    a['findings'][int(index)]['review'] = dict(decision=decision, note=str(note)[:500], time=time.time())
    return save('variant', v)


# ---------- extract style from a variant ----------
def extract_style(variant_id):
    v = get(variant_id)
    folder = core.STORE / 'variants' / v['id']
    colors, fonts, radii = {}, {}, {}
    for f in folder.rglob('*'):
        if not f.is_file() or f.suffix.lower() not in ('.html', '.css'):
            continue
        t = f.read_text(errors='replace')
        for c in re.findall(r'#[0-9a-fA-F]{6}\b|#[0-9a-fA-F]{3}\b', t):
            c = c.lower()
            if len(c) == 4:
                c = '#' + ''.join(x * 2 for x in c[1:])
            colors[c] = colors.get(c, 0) + 1
        for m in re.findall(r'font-family\s*:\s*([^;}"]+)', t):
            m = m.strip()
            fonts[m] = fonts.get(m, 0) + 1
        for m in re.findall(r'border-radius\s*:\s*(\d+px)', t):
            radii[m] = radii.get(m, 0) + 1
    ctx = current_context(v['project_id'], v.get('profile_id')) if v.get('project_id') else {'tokens': {}}
    existing = {str(x).lower() for x in ctx.get('tokens', {}).values()}
    out = []
    for n, (c, k) in enumerate(sorted(colors.items(), key=lambda x: -x[1])[:8], 1):
        out.append(dict(name=f'color-{n}', value=c, count=k, kind='color', known=c in existing))
    for n, (c, k) in enumerate(sorted(fonts.items(), key=lambda x: -x[1])[:2], 1):
        out.append(dict(name='font' if n == 1 and 'font' not in ctx.get('tokens', {}) else f'font-{n}', value=c, count=k, kind='font', known=c.lower() in existing))
    for n, (c, k) in enumerate(sorted(radii.items(), key=lambda x: -x[1])[:2], 1):
        out.append(dict(name=f'radius-{n}', value=c, count=k, kind='radius', known=c in existing))
    return out


def apply_style(project_id, picks, profile_id=None):
    from contexts import context

    c = current_context(project_id, profile_id)
    tokens = dict(c['tokens'])
    for k, val in (picks or {}).items():
        if not re.fullmatch(r'[a-z][a-z0-9-]{0,30}', str(k)):
            raise ValueError(f'Token name “{k}” must be lowercase letters, numbers and dashes')
        if not isinstance(val, str) or len(val) > 200 or any(ch in val for ch in '<>{}'):
            raise ValueError('Token values must be short plain values')
        tokens[k] = val
    rules = [{k: v for k, v in r.items() if k != 'version'} for r in c['rules']]
    return context(project_id, dict(markdown=c['markdown'], tokens=tokens, rules=rules, profile_id=c['profile_id']))


# ---------- agent reading of the review documents (manual, unverified opinion) ----------
DOC_OUTCOMES = {'meets': 'meets', 'fails': 'fails', 'unclear': 'unclear'}
MAX_AGENT_CRITERIA = 120


def doc_review_criteria(info):
    out = []
    for d in info['docs']:
        for c in d['criteria']:
            if c['kind'] == 'review' and len(out) < MAX_AGENT_CRITERIA:
                out.append(dict(id=f'c{len(out) + 1}', doc=d['file'], line=c['line'], area=c['area'], text=c['text']))
    return out


def launch_doc_review(variant_id, runner_id):
    # Manual trigger. Stages the screens and the designer's documents inside the job folder, then queues an agent job.
    import shutil, json
    from jobs import enqueue

    v = get(variant_id)
    p = get(v['project_id'])
    info = read_review_folder(p.get('review_folder', ''))
    if not info['docs']:
        raise ValueError('Set a review documents folder containing at least one .md file first (Settings → Review documents)')
    criteria = doc_review_criteria(info)
    if not criteria:
        raise ValueError('Your documents have no checklist items for an agent to judge; literal “must include / never say” rules are already checked by the audit')
    runner = get(runner_id)
    if not runner.get('enabled', True):
        raise ValueError('Runner is disabled or no longer exists')
    jid = uid()
    out = core.STORE / 'jobs' / jid
    (out / 'docs').mkdir(parents=True)
    for d in info['docs']:
        t = out / 'docs' / d['file']
        t.parent.mkdir(parents=True, exist_ok=True)
        t.write_text(d['text'])
    shutil.copytree(core.STORE / 'variants' / v['id'], out / 'package', ignore=shutil.ignore_patterns('thumbnails', 'changes.json'))
    ctx = get(v['context_id'])
    j = dict(
        id=jid,
        project_id=v['project_id'],
        board_id=v['board_id'],
        type='audit_review',
        target_variant_id=v['id'],
        runner_id=runner_id,
        runner_name=runner.get('name', ''),
        status='queued',
        events=[],
        created_at=time.time(),
        context=ctx,
        criteria=criteria,
        docs_hash=digest([(d['file'], d['text']) for d in info['docs']]),
        references=[],
        input_hash=digest([v['id'], criteria]),
        instruction=(
            'Task: audit_review. You are reviewing FINISHED screens against the designer\'s own review documents.\n'
            'package/ holds the screens (manifest.json and screens/*.html, with any css/js). docs/ holds the designer\'s Markdown documents. Read both.\n'
            'For each criterion below, judge from the files only whether the screens meet it. Do not invent evidence. If static HTML cannot tell you (for example real behaviour, imagery you cannot see, or something needing a specialist), answer "unclear".\n'
            'Write output/audit.json: {"summary": "...", "findings": [{"criterion_id": "c1", "outcome": "meets|fails|unclear", "screen_ids": ["0"], "evidence": "what you saw, quoting the text or element"}], "limitations": ["..."]}. One finding per criterion.\n'
            'You are running non-interactively: do not ask questions and do not reply with only a summary; the task is complete only when output/audit.json exists. Do not modify package/ or docs/.\n'
            'Criteria: ' + json.dumps(criteria)
        ),
    )
    save('job', j)
    enqueue(j)
    return j


def finish_doc_review(j, out, runner_type):
    import json

    crit = {c['id']: c for c in j['criteria']}
    raw = {}
    if runner_type == 'cli':
        f = out / 'output' / 'audit.json'
        if not f.is_file():
            raise ValueError('The agent finished without writing output/audit.json. Open runner.log in the job history to see what it said.')
        try:
            raw = json.loads(f.read_text())
        except ValueError:
            raise ValueError('output/audit.json is not valid JSON')
        if not isinstance(raw, dict) or not isinstance(raw.get('findings'), list):
            raise ValueError('output/audit.json must be an object with a findings list')
    answered = {}
    for x in raw.get('findings', []):
        if isinstance(x, dict) and x.get('criterion_id') in crit and x['criterion_id'] not in answered:
            answered[x['criterion_id']] = x
    findings = []
    for cid, c in crit.items():
        x = answered.get(cid)
        if x:
            sids = [str(s) for s in (x.get('screen_ids') if isinstance(x.get('screen_ids'), list) else [])][:12]
            findings.append(dict(c, criterion_id=cid, outcome=DOC_OUTCOMES.get(x.get('outcome'), 'unclear'), screen_ids=sids, evidence=str(x.get('evidence', ''))[:800] or 'No evidence given.', label='agent_opinion'))
        else:
            ev = 'The fixture runner cannot read documents; run this with a local coding agent.' if runner_type != 'cli' else 'The agent did not address this criterion.'
            findings.append(dict(c, criterion_id=cid, outcome='unclear', screen_ids=[], evidence=ev, label='agent_opinion'))
    lim = raw.get('limitations')
    lim = [str(i)[:400] for i in lim][:10] if isinstance(lim, list) else ([str(lim)[:800]] if lim else [])
    with core.LOCK:
        v = get(j['target_variant_id'])
        v.setdefault('doc_reviews', []).append(
            dict(
                id=uid(),
                job_id=j['id'],
                runner_name=j.get('runner_name', ''),
                runner_type=runner_type,
                at=time.time(),
                docs_hash=j['docs_hash'],
                summary=str(raw.get('summary', ''))[:1000],
                limitations=lim,
                counts={k: sum(1 for f in findings if f['outcome'] == k) for k in ('meets', 'fails', 'unclear')},
                findings=findings,
                note='An agent’s opinion of your documents against the screens. Unverified: the studio did not check it and it is not a compliance sign-off.',
            )
        )
        v['doc_reviews'] = v['doc_reviews'][-10:]
        save('variant', v)
