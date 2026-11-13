"""Package and manifest validation for generated prototypes."""

import re
from pathlib import Path
from core import safe_path

MAX_PACKAGE_FILES = 200
MAX_PACKAGE_BYTES = 20_000_000
MAX_PACKAGE_FILES = 200
MAX_PACKAGE_BYTES = 20_000_000
EXTERNAL_PATTERNS = [
    (r'(?:src|href|action|poster|data)\s*=\s*["\']?\s*(?:https?:)?//', 'external URL in an attribute'),
    (r'url\(\s*["\']?\s*(?:https?:)?//', 'external URL in CSS url()'),
    (r'@import\b', 'CSS @import'),
    (r'\b(?:fetch|XMLHttpRequest|WebSocket|EventSource)\s*\(', "network call"),
    (r'sendBeacon\s*\(', 'network call (sendBeacon)'),
    (r'\bimport\s*\(|\bimport\s+[^;]*\bfrom\s+["\']', "dynamic or module import"),
    (r'<\s*(?:iframe|object|embed)\b', 'embedded frame/object'),
    (r'http-equiv\s*=\s*["\']?refresh[^>]*url\s*=\s*\s*https?:', 'meta refresh to an external URL'),
    (r'(?:location\s*(?:\.href)?\s*=|window\.open\s*\()\s*["\']https?:', 'navigation to an external URL'),
]


def check_manifest(m):
    # Minimal structural check of variant-package/1.0 (stdlib only; mirrors contracts/schemas/variant-package.schema.json).
    if not isinstance(m, dict):
        raise ValueError('Manifest must be a JSON object')
    if m.get('schema_version') != '1.0' or m.get('kind') != 'clickthrough-static':
        raise ValueError('Invalid manifest contract: need schema_version "1.0" and kind "clickthrough-static"')
    screens = m.get('screens')
    if not isinstance(screens, list) or not screens:
        raise ValueError('Manifest needs a non-empty screens list')
    ids = []
    for sc in screens:
        if not isinstance(sc, dict) or not all(
            isinstance(sc.get(k), str) and sc.get(k) for k in ('id', 'title', 'file')
        ):
            raise ValueError('Every screen needs string id, title and file')
        if not isinstance(sc.get('states', []), list):
            raise ValueError('Screen states must be a list')
        ids.append(sc['id'])
    if len(ids) != len(set(ids)):
        raise ValueError('Duplicate screen IDs in manifest')
    if m.get('start_screen_id') not in ids:
        raise ValueError('start_screen_id must name a screen')
    if not isinstance(m.get('edges', []), list) or any(
        not isinstance(e, dict) or e.get('from') not in ids or e.get('to') not in ids for e in m.get('edges', [])
    ):
        raise ValueError('Invalid navigation edge')


def scan_package(folder):
    files = [f for f in folder.rglob('*') if f.is_file() or f.is_symlink()]
    if len(files) > MAX_PACKAGE_FILES:
        raise ValueError(f'Package has too many files (limit {MAX_PACKAGE_FILES})')
    if sum(f.stat().st_size for f in files if f.is_file() and not f.is_symlink()) > MAX_PACKAGE_BYTES:
        raise ValueError('Package is too large')
    for f in files:
        if f.is_symlink():
            raise ValueError('Symlinks are not allowed in packages')
        if f.suffix.lower() in ('.html', '.css', '.js'):
            text = f.read_text(errors='replace')
            for pattern, label in EXTERNAL_PATTERNS:
                if re.search(pattern, text, re.I):
                    raise ValueError(f'Not allowed in {f.relative_to(folder)}: {label}')


def token_refs(folder, tokens):
    # var(--x) with no fallback must be declared in the package or provided by the token set.
    declared = set('--' + k for k in (tokens or {}))
    used = {}
    for f in folder.rglob('*'):
        if f.is_file() and f.suffix.lower() in ('.html', '.css'):
            text = f.read_text(errors='replace')
            declared |= set(re.findall(r'(--[\w-]+)\s*:', text))
            for name in re.findall(r'var\(\s*(--[\w-]+)\s*\)', text):
                used.setdefault(name, f.name)
    return sorted(n for n in used if n not in declared)


def validate(folder, manifest, rules, tokens=None):
    results = []
    check_manifest(manifest)
    ids = {s['id'] for s in manifest['screens']}
    scan_package(folder)
    for s in manifest['screens']:
        f = safe_path(folder, s['file'])
        content = f.read_text()
        count = len(re.findall('data-role="primary-action"', content))
        results.append(
            dict(
                check='Primary action · ' + s['title'],
                outcome=(
                    'not_assessable'
                    if not count
                    else (
                        'pass'
                        if count
                        <= next(
                            (
                                r.get('parameters', {}).get('max', 1)
                                for r in rules
                                if r.get('check') == 'primary_action_count'
                            ),
                            1,
                        )
                        else 'fail'
                    )
                ),
                evidence=f'{count} instrumented primary actions',
                screen=s['id'],
            )
        )
        root = folder.resolve()
        for link in re.findall(r'(?:href|src)\s*=\s*["\']([^"\']+)["\']', content):
            if link.startswith(('#', 'data:', 'mailto:', 'tel:')):
                continue
            target = (f.parent / link.split('#')[0].split('?')[0]).resolve()
            if Path(link).is_absolute() or link.startswith('/') or not target.is_relative_to(root):
                raise ValueError(f'{s["file"]} links outside the package: {link}')
            if not target.is_file():
                raise ValueError(f'{s["file"]} links to a missing file: {link}')
        stable = re.findall('data-design-id="([^"]+)"', content)
        results.append(
            dict(
                check='Stable targets · ' + s['title'],
                outcome='pass' if stable and len(set(stable)) == len(stable) else 'not_assessable',
                evidence=f'{len(stable)} targets',
            )
        )
    results.append(
        dict(
            check='Package & local navigation',
            outcome='pass',
            evidence='Manifest valid; all screen files and declared destinations exist; local links resolved; no external assets, network calls or embedded frames',
        )
    )
    unresolved = token_refs(folder, tokens)
    results.append(
        dict(
            check='Token references',
            outcome='fail' if unresolved else 'pass',
            evidence=(
                ('Unresolved CSS variables without fallback: ' + ', '.join(unresolved))
                if unresolved
                else 'All CSS variables resolve to a declared token or custom property'
            ),
        )
    )
    for r in rules:
        if r.get('verification') != 'deterministic':
            results.append(
                dict(
                    check=r['description'],
                    outcome='review',
                    evidence='Needs designer review; no automated conformance claim',
                )
            )
    return results
