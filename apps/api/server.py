"""Design Studio entry point: `python3 apps/api/server.py`.

The implementation lives in focused modules (core, contexts, fixture, regions, validation, jobs,
prototypes, references, research, boards, sharing, web). This file only starts the server and
re-exports their public names so tests and tools can keep using `import server as s`.
Assigning `s.STORE` redirects the data directory for every module (it lives in `core`).
"""

import sys, types
import core
from core import *
from contexts import *
from fixture import *
from regions import *
from validation import *
from jobs import *
from jobs import _execute
from prototypes import *
from references import *
from research import *
from boards import *
from sharing import *
from web import *
from regions import _masked
import subprocess, time, threading, json


class _Facade(types.ModuleType):
    def __setattr__(self, k, v):
        if k == 'STORE':
            core.STORE = v
        else:
            super().__setattr__(k, v)

    def __getattr__(self, k):
        if k == 'STORE':
            return core.STORE
        raise AttributeError(k)


sys.modules[__name__].__class__ = _Facade
sys.modules[__name__].__dict__.pop('STORE', None)

if __name__ == '__main__':
    raise SystemExit(main())
