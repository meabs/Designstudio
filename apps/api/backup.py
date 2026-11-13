"""Consistent backup of the studio's storage: SQLite online backup + copy of generated files.
Usage: python3 apps/api/backup.py [dest_dir]   (safe while the server runs)
Restore: stop the server, replace the storage directory (STUDIO_STORAGE) with the backup folder."""

import os, shutil, sqlite3, sys, time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def backup(store, dest):
    store = Path(store)
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    if not (store / 'studio.db').is_file():
        raise SystemExit(f'No studio.db in {store}')
    src = sqlite3.connect(store / 'studio.db', timeout=30)
    dst = sqlite3.connect(dest / 'studio.db')
    with dst:
        src.backup(dst)
    src.close()
    dst.close()
    for name in ('jobs', 'variants', 'prototypes', 'projects'):
        if (store / name).is_dir():
            shutil.copytree(store / name, dest / name, dirs_exist_ok=True, symlinks=True)
    return dest


if __name__ == '__main__':
    store = os.environ.get('STUDIO_STORAGE', ROOT / 'storage')
    dest = sys.argv[1] if len(sys.argv) > 1 else ROOT / 'backups' / time.strftime('%Y%m%d-%H%M%S')
    print('Backup written to', backup(store, dest))
