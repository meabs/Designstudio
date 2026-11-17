"""Sanitising research output produced by agents."""

import ipaddress, re, socket, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse
from core import uid


def sanitize_research(raw, supplied):
    # Agent output is untrusted: keep known fields only, never accept provenance labels the agent assigned, never pre-select findings.
    if not isinstance(raw, dict) or not isinstance(raw.get('findings'), list):
        raise ValueError('research.json must be an object with a findings list')
    supplied_ids = {x['id'] for x in supplied}
    sources = [dict(x) for x in supplied]
    for x in raw.get('sources') if isinstance(raw.get('sources'), list) else []:
        if not isinstance(x, dict) or str(x.get('id') or '') in supplied_ids:
            continue
        url = x.get('url') if isinstance(x.get('url'), str) and re.match(r'https?://', x['url']) else None
        sources.append(
            dict(
                id=str(x.get('id') or uid()),
                title=str(x.get('title') or url or 'Source reported by the agent')[:200],
                url=url,
                text=str(x.get('text', ''))[:1000] or None,
                verification='unverified_claim',
                note='Reported by the agent; the studio did not retrieve or check it',
            )
        )
    known = {x['id'] for x in sources}
    findings = []
    seen = set()
    for f in raw['findings']:
        if not isinstance(f, dict) or not str(f.get('title', '')).strip():
            continue
        ids = [i for i in (f.get('source_ids') if isinstance(f.get('source_ids'), list) else []) if i in known]
        fid = str(f.get('id') or uid())
        while fid in seen:
            fid += '-' + uid()[:4]
        seen.add(fid)
        findings.append(
            dict(
                id=fid,
                title=str(f['title'])[:200],
                detail=str(f.get('detail', ''))[:3000],
                confidence=f.get('confidence') if f.get('confidence') in ('low', 'medium', 'high') else None,
                source_ids=ids,
                selected=False,
                verification=(
                    'source_supplied_by_user' if ids and all(i in supplied_ids for i in ids) else 'unverified_claim'
                ),
            )
        )
    lim = raw.get('limitations')
    lim = [str(i)[:500] for i in lim] if isinstance(lim, list) else ([str(lim)[:1000]] if lim else [])
    return dict(summary=str(raw.get('summary', ''))[:1000], findings=findings, sources=sources, limitations=lim)


# ---------- are the pages an agent cited real? ----------
# The studio fetches nothing the designer supplied. For a web-enabled run it makes ONE plain request per page the agent cited, so a made-up or
# moved URL is visible. Agent output is untrusted, so private and local addresses are never contacted, and redirects are checked hop by hop.
MAX_CHECKS = 12


class Private(Exception):
    pass


def _public(url):
    u = urlparse(url)
    if u.scheme not in ('http', 'https') or not u.hostname:
        raise Private(url)
    try:
        infos = socket.getaddrinfo(u.hostname, u.port or (443 if u.scheme == 'https' else 80), type=socket.SOCK_STREAM)
    except OSError:
        return  # does not resolve: the request will report it
    for info in infos:
        if not ipaddress.ip_address(info[4][0]).is_global:
            raise Private(url)


class _Hop(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        _public(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_status(url, timeout=8):
    """-> 'reachable' | 'not_found' | 'blocked' | 'error' | 'unreachable' | 'skipped'."""
    try:
        _public(url)
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 (compatible; link-check)', 'Accept': 'text/html,*/*;q=0.5', 'Range': 'bytes=0-1023'})
        with urllib.request.build_opener(_Hop).open(req, timeout=timeout) as r:
            return 'reachable' if r.status < 400 else 'error'
    except Private:
        return 'skipped'
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            return 'not_found'
        if e.code in (401, 403, 429, 451):
            return 'blocked'
        return 'error'
    except Exception:
        return 'unreachable'


LABELS = {
    'reachable': 'Page responded',
    'not_found': 'Page not found (404): the agent may have invented or mistyped this link',
    'blocked': 'The site refused an automated check; the page may still exist',
    'error': 'The site returned an error',
    'unreachable': 'Could not reach the site',
    'skipped': 'Not checked (local or private address)',
}


def check_urls(sources, findings, fetch=fetch_status):
    """Annotate agent-reported sources with a reachability result, and flag findings that lean on a page that was not found."""
    todo = [s for s in sources if s.get('url') and s.get('verification') == 'unverified_claim'][:MAX_CHECKS]
    if not todo:
        return
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda s: fetch(s['url']), todo))
    now = time.time()
    for s, r in zip(todo, results):
        s.update(reachable=r, reachable_note=LABELS.get(r, r), checked_at=now)
    bad = {s['id'] for s in todo if s['reachable'] == 'not_found'}
    for f in findings:
        broken = [i for i in f.get('source_ids', []) if i in bad]
        if broken:
            f['broken_sources'] = broken
