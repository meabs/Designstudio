"""Storage primitives shared by every module: the data directory, the SQLite entity table, logging and ids."""

import logging, sys, os, json, sqlite3, uuid, hashlib, threading, time
from pathlib import Path
from contextlib import contextmanager

FROZEN = bool(getattr(sys, 'frozen', False))
# In the packaged executable the bundled files (the built UI) live in PyInstaller's extraction folder.
ROOT = Path(getattr(sys, '_MEIPASS', '')) if FROZEN else Path(__file__).resolve().parents[2]


def default_store():
    if not FROZEN:
        return ROOT / 'storage'
    # Packaged build: keep your data in a per-user folder, never next to the executable.
    if sys.platform == 'darwin':
        base = Path.home() / 'Library/Application Support'
    elif sys.platform.startswith('win'):
        base = Path(os.environ.get('APPDATA') or Path.home() / 'AppData/Roaming')
    else:
        base = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local/share')
    return base / 'designstudio'


STORE = Path(os.environ.get('STUDIO_STORAGE') or default_store())
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


def allowed_roots():
    # Folders the studio may read on request (guideline import, review documents). Default: your home folder only.
    raw = os.environ.get('STUDIO_FOLDER_ROOTS', '').strip()
    return [Path(p).expanduser().resolve() for p in raw.split(os.pathsep) if p.strip()] if raw else [Path.home().resolve()]


def check_folder(path):
    # Resolve symlinks first, then require the folder to sit inside an allowed root and not inside a hidden directory (.ssh, .config...).
    root = Path(str(path or '').strip()).expanduser()
    if not root.is_dir():
        raise ValueError('Folder not found. Enter the full path to a folder on this computer.')
    root = root.resolve()
    for base in allowed_roots():
        if root.is_relative_to(base):
            if any(part.startswith('.') for part in root.relative_to(base).parts):
                raise ValueError('Hidden folders cannot be read')
            return root
    raise ValueError('That folder is outside the places the studio may read (by default your home folder). Set STUDIO_FOLDER_ROOTS to allow more.')


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
