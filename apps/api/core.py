"""Storage primitives shared by every module: the data directory, the SQLite entity table, logging and ids."""

import logging, sys, os, json, sqlite3, uuid, hashlib, threading, time
from pathlib import Path
from contextlib import contextmanager

ROOT = Path(__file__).resolve().parents[2]
STORE = Path(os.environ.get('STUDIO_STORAGE', ROOT / 'storage'))
STORE.mkdir(parents=True, exist_ok=True)
STORE = Path(os.environ.get('STUDIO_STORAGE', ROOT / 'storage'))
STORE.mkdir(parents=True, exist_ok=True)
LOCK = threading.RLock()
log = logging.getLogger('studio')


def setup_logging():
    # Operational log: stderr plus storage/studio.log (rotating). Never logs request bodies, prompts or agent output.
    from logging.handlers import RotatingFileHandler

    fmt = logging.Formatter('%(asctime)s %(levelname)s %(message)s')
    log.setLevel(os.environ.get('STUDIO_LOG_LEVEL', 'INFO').upper())
    if not log.handlers:
        for h in (
            logging.StreamHandler(sys.stderr),
            RotatingFileHandler(STORE / 'studio.log', maxBytes=2_000_000, backupCount=3),
        ):
            h.setFormatter(fmt)
            log.addHandler(h)


STARTED = time.time()
SHARE_PORT = int(os.environ.get('STUDIO_SHARE_PORT', '0') or 0)


def uid():
    return uuid.uuid4().hex[:16]


def canonical(x):
    return json.dumps(x, sort_keys=True, separators=(',', ':'))


def digest(x):
    return hashlib.sha256(canonical(x).encode()).hexdigest()


@contextmanager
def db():
    c = sqlite3.connect(STORE / 'studio.db', timeout=30)
    try:
        c.execute('PRAGMA busy_timeout=30000')
        if not getattr(db, 'wal', None) or db.wal != str(STORE):
            c.execute('PRAGMA journal_mode=WAL')
            db.wal = str(STORE)
        c.execute('CREATE TABLE IF NOT EXISTS entities (id TEXT PRIMARY KEY, type TEXT, data TEXT)')
        yield c
        c.commit()
    finally:
        c.close()


def save(kind, x):
    with LOCK, db() as c:
        c.execute('INSERT OR REPLACE INTO entities VALUES (?,?,?)', (x['id'], kind, json.dumps(x)))
    return x


def allof(kind):
    with db() as c:
        return [json.loads(r[0]) for r in c.execute('SELECT data FROM entities WHERE type=?', (kind,))]


def get(id):
    with db() as c:
        r = c.execute('SELECT data FROM entities WHERE id=?', (id,)).fetchone()
    if not r:
        raise ValueError('Record not found')
    return json.loads(r[0])


def safe_path(base, path):
    p = (base / path).resolve()
    if Path(path).is_absolute() or '..' in Path(path).parts or not p.is_relative_to(base.resolve()) or p.is_symlink():
        raise ValueError('Unsafe asset path')
    return p
