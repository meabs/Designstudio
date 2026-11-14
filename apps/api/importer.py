"""Import existing guideline files (DESIGN.md, rules, tokens) so designers don't paste them into the UI.

Pure parsing: nothing here writes to a project. The UI shows what was found, the designer ticks what to adopt, and it lands in an
unsaved guideline draft that becomes a new version only when saved. Input is either a folder on this computer (read-only,
no symlinks, bounded) or files the browser uploads.
"""

import json, re
from pathlib import Path

MAX_FILES = 80
MAX_BYTES = 300_000
MAX_RULES = 200
MAX_TOKENS = 200
TEXT_EXT = {'.md', '.markdown', '.json', '.css'}

DESIGN_NAME = re.compile(r'(^|[^a-z])(design|guideline|guidelines|brand|style|styleguide|style-guide)([^a-z]|$)', re.I)
RULES_NAME = re.compile(r'rule|guardrail|principle|standard|checklist|do[-_ ]?and[-_ ]?dont', re.I)
RULES_HEAD = re.compile(r'\b(rules?|principles?|must|do\'?s|don\'?ts|dos and don|requirements?|guardrails?|standards?)\b', re.I)
TOKENS_NAME = re.compile(r'token|theme|palette|variables', re.I)
CHECKBOX = re.compile(r'^\s*[-*+]\s*\[[ xX]\]\s*(.+)$')
BULLET = re.compile(r'^\s*(?:[-*+]|\d+[.)])\s+(.+)$')
STRONG = re.compile(r'\b(must|must not|never|always|required|shall|do not|don\'t|avoid|should)\b', re.I)
ERRORISH = re.compile(r'\b(must|must not|never|required|shall)\b', re.I)
RULE_ID = re.compile(r'^\**\[?([A-Z][A-Z0-9]{1,7}-\d{1,4})\]?\**\s*[:\-–.)]?\s+(.+)$')
CSS_VAR = re.compile(r'--([A-Za-z][\w-]*)\s*:\s*([^;}\n]+?)\s*(?:;|\}|$)', re.M)


def clean_text(s):
    return re.sub(r'\*\*|__|`', '', s).strip()


def token_name(raw):
    n = re.sub(r'[^a-z0-9]+', '-', str(raw).lower()).strip('-')
    return n if re.fullmatch(r'[a-z][a-z0-9-]{0,40}', n or '') else ''


def token_value(v):
    if isinstance(v, bool) or v is None:
        return None
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, str):
        v = v.strip()
        if v and len(v) <= 200 and not any(c in v for c in '<>{}'):
            return v
    return None


def flatten(obj, prefix=''):
    # Flat {name: value}, or nested groups and W3C/Style-Dictionary leaves ({"value": ..} / {"$value": ..}).
    out = {}
    if not isinstance(obj, dict):
        return out
    for k, v in obj.items():
        if k in ('$type', '$description', 'description', 'type', 'comment') and prefix:
            continue
        name = f'{prefix}-{k}' if prefix else str(k)
        if isinstance(v, dict):
            leaf = v.get('$value', v.get('value')) if ('$value' in v or 'value' in v) else None
            if leaf is not None:
                out[name] = leaf
            else:
                out.update(flatten(v, name))
        else:
            out[name] = v
    return out


def tokens_from_json(text):
    try:
        data = json.loads(text)
    except ValueError:
        return {}, 'not valid JSON'
    found = {}
    for k, v in flatten(data).items():
        n, val = token_name(k), token_value(v)
        if n and val is not None:
            found.setdefault(n, val)
    return found, ''


def tokens_from_css(text):
    return {token_name(n): token_value(v) for n, v in CSS_VAR.findall(text) if token_name(n) and token_value(v)}


def rules_from_md(name, text, rule_file):
    out, in_rules, in_code = [], rule_file, False
    for n, line in enumerate(text.splitlines(), 1):
        if line.strip().startswith('```'):
            in_code = not in_code
            continue
        if in_code:
            continue
        if line.startswith('#'):
            in_rules = rule_file or bool(RULES_HEAD.search(line))
            continue
        m = CHECKBOX.match(line)
        body = m.group(1) if m else None
        if body is None:
            b = BULLET.match(line)
            if b and (in_rules or STRONG.search(b.group(1))) and (in_rules or ERRORISH.search(b.group(1))):
                body = b.group(1)
        if not body:
            continue
        body = clean_text(body)
        if len(body) < 6:
            continue
        rid, desc = None, body
        mid = RULE_ID.match(body)
        if mid:
            rid, desc = mid.group(1).upper(), mid.group(2).strip()
        out.append(dict(id=rid, description=desc[:400], severity='error' if ERRORISH.search(desc) else 'warning', source=f'{name}:{n}'))
        if len(out) >= MAX_RULES:
            break
    return out


def parse_files(files):
    """files: [{name, text}] -> candidates for guidelines markdown, rules and tokens."""
    docs, rules, tokens, skipped = [], [], {}, []
    token_sources = {}
    for f in files[:MAX_FILES]:
        name, text = str(f.get('name', '')), str(f.get('text', ''))
        ext = Path(name).suffix.lower()
        if ext not in TEXT_EXT:
            skipped.append(f'{name} (not .md, .json or .css)')
            continue
        if len(text) > MAX_BYTES:
            skipped.append(f'{name} (over {MAX_BYTES // 1000} KB)')
            continue
        base = Path(name).name
        if ext == '.json':
            found, err = tokens_from_json(text)
            if err:
                skipped.append(f'{name} ({err})')
            elif not found:
                skipped.append(f'{name} (no flat or nested token values found)')
            for k, v in found.items():
                if k not in tokens and len(tokens) < MAX_TOKENS:
                    tokens[k] = v
                    token_sources[k] = name
            continue
        if ext == '.css':
            for k, v in tokens_from_css(text).items():
                if k not in tokens and len(tokens) < MAX_TOKENS:
                    tokens[k] = v
                    token_sources[k] = name
            continue
        title = next((l.lstrip('# ').strip() for l in text.splitlines() if l.startswith('# ')), Path(base).stem)
        rule_file = bool(RULES_NAME.search(base)) and not DESIGN_NAME.search(base)
        found_rules = rules_from_md(name, text, rule_file)
        for k, v in CSS_VAR.findall(text):
            tk, tv = token_name(k), token_value(v)
            if tk and tv and tk not in tokens and len(tokens) < MAX_TOKENS:
                tokens[tk] = tv
                token_sources[tk] = name
        docs.append(
            dict(
                file=name,
                title=title,
                chars=len(text),
                text=text,
                kind='design' if DESIGN_NAME.search(base) else ('rules' if rule_file else 'other'),
                rule_count=len(found_rules),
            )
        )
        rules += found_rules
    # Decide which markdown files are guidelines prose: the DESIGN/brand/style files; rules-only files stay out of the prose.
    primary = [d['file'] for d in docs if d['kind'] == 'design'] or [d['file'] for d in docs if d['kind'] == 'other'][:1]
    for d in docs:
        d['use'] = d['file'] in primary
    seen, uniq = set(), []
    for r in rules:
        k = r['description'].lower()
        if k not in seen:
            seen.add(k)
            uniq.append(r)
    for n, r in enumerate(uniq, 1):
        r['n'] = n
    return dict(
        docs=docs,
        rules=uniq[:MAX_RULES],
        tokens=[dict(name=k, value=v, source=token_sources[k]) for k, v in tokens.items()],
        skipped=skipped,
    )


def read_folder(path):
    path = str(path or '').strip()
    if not path:
        raise ValueError('Enter the path to a folder')
    root = Path(path).expanduser()
    if not root.is_dir():
        raise ValueError('Folder not found. Enter the full path to a folder on this computer.')
    root = root.resolve()
    files, skipped = [], []
    for f in sorted(root.rglob('*')):
        if not f.is_file() or f.suffix.lower() not in TEXT_EXT:
            continue
        rel = str(f.relative_to(root))
        if any(part in ('node_modules', '.git') or part.startswith('.') for part in f.relative_to(root).parts):
            continue
        if len(files) >= MAX_FILES:
            skipped.append(f'{rel} (over the {MAX_FILES}-file limit)')
            continue
        if f.is_symlink() or not f.resolve().is_relative_to(root):
            skipped.append(f'{rel} (symlink or outside the folder)')
            continue
        if f.stat().st_size > MAX_BYTES:
            skipped.append(f'{rel} (over {MAX_BYTES // 1000} KB)')
            continue
        files.append(dict(name=rel, text=f.read_text(errors='replace')))
    out = parse_files(files)
    out['skipped'] = skipped + out['skipped']
    out['folder'] = str(root)
    return out
