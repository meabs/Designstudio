"""Sanitising research output produced by agents."""

import re
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
