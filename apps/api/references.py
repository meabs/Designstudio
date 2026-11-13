"""Reference images: upload, sniffing, per-job snapshots."""

import base64, hashlib, time, re, shutil
from core import LOCK, allof, db, get, save, uid
import core

# ---- reference images: designer-supplied visual context passed to agents as files ----
MAX_REF_BYTES = 5_000_000
MAX_REFS_PER_PROJECT = 40
# ---- reference images: designer-supplied visual context passed to agents as files ----
MAX_REF_BYTES = 5_000_000
MAX_REFS_PER_PROJECT = 40


def sniff_image(raw):
    if raw.startswith(b'\x89PNG\r\n\x1a\n'):
        return 'png', 'image/png'
    if raw.startswith(b'\xff\xd8\xff'):
        return 'jpg', 'image/jpeg'
    if raw[:4] == b'RIFF' and raw[8:12] == b'WEBP':
        return 'webp', 'image/webp'
    if raw[:4] == b'GIF8':
        return 'gif', 'image/gif'
    raise ValueError('Unsupported image type. Use PNG, JPEG, WebP or GIF.')


def add_reference(d):
    pid = d['project_id']
    get(pid)
    try:
        raw = base64.b64decode(d.get('data', ''), validate=True)
    except Exception:
        raise ValueError('Image data is not valid')
    if not raw:
        raise ValueError('Empty image')
    if len(raw) > MAX_REF_BYTES:
        raise ValueError('Image is larger than 5 MB')
    if len([r for r in allof('reference') if r['project_id'] == pid]) >= MAX_REFS_PER_PROJECT:
        raise ValueError('Reference limit reached for this project')
    ext, mime = sniff_image(raw)
    rid = uid()
    folder = core.STORE / 'projects' / pid / 'references'
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f'{rid}.{ext}').write_bytes(raw)
    name = re.sub(r'[^\w .,()\-]', '', str(d.get('name') or 'Reference'))[:80].strip() or 'Reference'
    return save(
        'reference',
        dict(
            id=rid,
            project_id=pid,
            name=name,
            note=str(d.get('note', ''))[:500],
            file=f'{rid}.{ext}',
            mime=mime,
            size=len(raw),
            sha256=hashlib.sha256(raw).hexdigest(),
            created_at=time.time(),
        ),
    )


def delete_reference(rid):
    r = get(rid)
    f = core.STORE / 'projects' / r['project_id'] / 'references' / r['file']
    if f.is_file():
        f.unlink()
    with LOCK, db() as c:
        c.execute('DELETE FROM entities WHERE id=?', (rid,))
    return {'deleted': rid}


def resolve_references(project_id, ids):
    out = []
    for i in dict.fromkeys(ids or []):
        r = get(i)
        if r.get('project_id') != project_id or 'sha256' not in r:
            raise ValueError('Reference images must belong to this project')
        out.append(
            dict(id=r['id'], name=r['name'], note=r.get('note', ''), file=r['file'], mime=r['mime'], sha256=r['sha256'])
        )
    return out


def snapshot_references(j, source_dir):
    # Copy into the job's own folder so retries and history keep working even if the library image is later deleted.
    if not j.get('references'):
        return
    dst = core.STORE / 'jobs' / j['id'] / 'references'
    dst.mkdir(parents=True, exist_ok=True)
    for r in j['references']:
        src = source_dir / r['file']
        if not src.is_file():
            raise ValueError('Reference image is no longer available: ' + r['name'])
        shutil.copyfile(src, dst / r['file'])
