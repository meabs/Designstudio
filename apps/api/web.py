"""HTTP layer: studio API handler, share listener, health check and process entry point."""

import ipaddress, socket, signal, sys, os, json, hashlib, threading, time, re, zipfile, io, shutil
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler, BaseHTTPRequestHandler
from urllib.parse import urlparse
from local_agents import discover, configuration, bwrap_ok
from boards import blind_choice, conflict_preview, create_board, hidden_job_file, launch, mask_state, set_blind, spread_offset
from contexts import context, profile_create, profile_delete, profile_update, project, seed
from core import LOCK, ROOT, SHARE_PORT, STARTED, allof, db, get, log, safe_path, save, setup_logging, uid
from jobs import JOBQ, MAX_JOBS, job_progress, WORKERS, cancel_job, recover_jobs, retry_job, start_workers, stop_workers
from prototypes import approve, mix_variants, set_aside, set_review_state
from importer import parse_files, read_folder
from audit import apply_style, audit_review, audit_variant, extract_style, launch_doc_review, read_review_folder
from references import add_reference, delete_reference
from sharing import SHARE_JS, SHARE_PLAYER, share_create, share_find, share_revoke
import core


class ShareHandler(BaseHTTPRequestHandler):
    server_version = 'Share'
    sys_version = ''

    def log_message(self, *a):
        pass

    def reply(self, status, body, ctype='text/html; charset=utf-8', extra=None):
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(status)
        for k, v in {
            'Content-Type': ctype,
            'Content-Length': str(len(data)),
            'Cache-Control': 'no-store',
            'X-Content-Type-Options': 'nosniff',
            'Referrer-Policy': 'no-referrer',
            'X-Robots-Tag': 'noindex, nofollow',
            **(extra or {}),
        }.items():
            self.send_header(k, v)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        m = re.match(r'^/s/([A-Za-z0-9_-]{16,64})/(.*)$', urlparse(self.path).path)
        if not m:
            return self.reply(404, 'Not found')
        token, rest = m.groups()
        p, info = share_find(token)
        if not p:
            return self.reply(
                410 if info in ('expired', 'revoked') else 404,
                '<!doctype html><meta charset="utf-8"><title>Link unavailable</title><p style="font:16px system-ui;margin:3em auto;max-width:30em">This prototype link '
                + ('has expired or was revoked.' if info in ('expired', 'revoked') else 'is not valid.')
                + '</p>',
            )
        csp = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-src 'self'; form-action 'none'"
        try:
            if rest in ('', 'index.html'):
                return self.reply(
                    200,
                    SHARE_PLAYER,
                    extra={
                        'Content-Security-Policy': "default-src 'self'; script-src 'self'; style-src 'unsafe-inline'; frame-src 'self'; connect-src 'self'"
                    },
                )
            if rest == 'player.js':
                return self.reply(200, SHARE_JS, 'application/javascript')
            if rest == 'meta.json':
                return self.reply(
                    200,
                    json.dumps(
                        dict(
                            board_title=p['board_title'],
                            version=p['version'],
                            start=p['start_screen_id'],
                            screens=[dict(id=x['id'], title=x['title'], file=x['file']) for x in p['screens']],
                        )
                    ),
                    'application/json',
                )
            if rest.startswith('f/'):
                f = safe_path(core.STORE / 'prototypes' / p['id'], rest[2:])
                if not f.is_file():
                    return self.reply(404, 'Not found')
                import mimetypes

                return self.reply(
                    200,
                    f.read_bytes(),
                    mimetypes.guess_type(f)[0] or 'application/octet-stream',
                    {'Content-Security-Policy': csp},
                )
        except ValueError:
            return self.reply(404, 'Not found')
        return self.reply(404, 'Not found')


ALLOWED_HOSTS = {'localhost', '127.0.0.1', '[::1]'}


UI_DIST = ROOT / 'apps/ui/dist'
LOOPBACK_BINDS = {'127.0.0.1', 'localhost', '::1'}
# Actions that decide which programs the studio runs and how they are confined. In LAN mode only the machine
# running the studio may use them: anyone else on the network could otherwise register an arbitrary executable.
RUNNER_ADMIN = {'runner', 'local-runner', 'update-runner', 'delete-runner', 'test-runner', 'set-review-folder'}


def lan_mode():
    return os.environ.get('STUDIO_HOST', '127.0.0.1').strip().lower() not in LOOPBACK_BINDS


def is_loopback_client(addr):
    try:
        return ipaddress.ip_address(addr.split('%')[0]).is_loopback
    except ValueError:
        return False


def _plain(addr):
    a = addr.split('%')[0]
    return a[7:] if a.lower().startswith('::ffff:') else a


def is_local_client(client, server):
    # Local = loopback, or the computer talking to its own network address (e.g. http://192.168.x.x:5173 opened on the host itself).
    # A remote device never has the host's own address as its source address.
    return is_loopback_client(client) or _plain(client) == _plain(server)


def lan_ips():
    ips = set()
    for target in ('10.255.255.255', '192.168.255.255', '172.16.255.255'):  # no packets are sent; this picks the outgoing interface
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as c:
                c.connect((target, 1))
                if not c.getsockname()[0].startswith('127.'):
                    ips.add(c.getsockname()[0])
        except OSError:
            pass
    return sorted(ips)


def host_ok(host):
    # DNS-rebinding guard: the studio can start local agents, so only loopback names are served.
    # In LAN mode IP literals (an attacker's DNS name cannot be one) and this machine's own host names are served too.
    host = (host or '').strip()
    h = host.lower() if host.endswith(']') else host.rsplit(':', 1)[0].lower()
    if h in ALLOWED_HOSTS or h in {x.strip().lower() for x in os.environ.get('STUDIO_ALLOWED_HOSTS', '').split(',') if x.strip()}:
        return True
    if not lan_mode():
        return False
    try:
        ipaddress.ip_address(h.strip('[]'))
        return True
    except ValueError:
        me = socket.gethostname().lower()
        return h in (me, me + '.local', me.split('.')[0] + '.local')


class Handler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def log_request(self, code='-', size='-'):
        if code != 200 or self.command != 'GET' or not self.path.startswith(('/api/state', '/assets/')):
            log.info('%s %s %s', self.command, self.path.split('?')[0][:120], code)

    def deny_host(self):
        if host_ok(self.headers.get('Host')):
            return False
        self.send_json(
            {
                'code': 'BAD_HOST',
                'message': 'Host not allowed; open the studio at http://localhost (set STUDIO_ALLOWED_HOSTS to add names)',
            },
            403,
        )
        return True

    def do_HEAD(self):
        self.send_error(405)

    def send_json(self, x, status=200):
        data = json.dumps(x).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urlparse(self.path).path
        if self.deny_host():
            return
        try:
            if path == '/favicon.ico':
                self.send_response(204)
                self.end_headers()
                return
            if path.startswith('/api/job-progress/'):
                return self.send_json(job_progress(path.rsplit('/', 1)[-1]))
            if path == '/api/health':
                return self.send_json(health())
            if path == '/api/local-agents':
                return self.send_json(discover())
            if path == '/api/config':
                return self.send_json(dict(bwrap=bwrap_ok(), share_port=SHARE_PORT, max_jobs=MAX_JOBS))
            if path == '/api/state':
                data = json.dumps(
                    mask_state(
                        {
                            k: allof(k)
                            for k in [
                                'project',
                                'context',
                                'board',
                                'variant',
                                'job',
                                'research',
                                'annotation',
                                'runner',
                                'prototype',
                                'reference',
                            ]
                        }
                    )
                ).encode()
                tag = '"' + hashlib.sha256(data).hexdigest()[:20] + '"'
                if self.headers.get('If-None-Match') == tag:
                    self.send_response(304)
                    self.send_header('ETag', tag)
                    self.end_headers()
                    return
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.send_header('ETag', tag)
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                return self.wfile.write(data)
            if path.startswith('/api/export/'):
                rec = get(path.split('/')[-1])
                proto = 'variant_id' in rec
                v = get(rec['variant_id']) if proto else rec
                folder = core.STORE / ('prototypes' if proto else 'variants') / rec['id']
                buf = io.BytesIO()
                with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
                    for f in folder.rglob('*'):
                        if f.is_file() and not f.is_symlink():
                            z.write(f, f.relative_to(folder))
                    if not proto:
                        z.writestr(
                            'index.html',
                            f'<meta http-equiv="refresh" content="0;url=screens/{v["manifest"]["start_screen_id"]}.html">',
                        )
                self.send_response(200)
                self.send_header('Content-Type', 'application/zip')
                self.send_header('Content-Disposition', 'attachment; filename="prototype.zip"')
                self.end_headers()
                return self.wfile.write(buf.getvalue())
            if path.startswith('/assets/'):
                if hidden_job_file(path):
                    return self.send_json({'message': 'Hidden while this comparison is blind'}, 403)
                f = safe_path(core.STORE, path[len('/assets/') :])
            else:
                if not (UI_DIST / 'index.html').is_file():
                    msg = b'The UI has not been built yet. Run:  make ui-build   (needs Node 20+), then reload.'
                    self.send_response(503)
                    self.send_header('Content-Type', 'text/plain; charset=utf-8')
                    self.send_header('Content-Length', str(len(msg)))
                    self.end_headers()
                    return self.wfile.write(msg)
                # Single-page app: real files (hashed /ui/ assets) are served as-is, every other path gets index.html.
                f = safe_path(UI_DIST, path.lstrip('/')) if '.' in path.split('/')[-1] else UI_DIST / 'index.html'
            if not f.is_file():
                return self.send_error(404)
            import mimetypes

            body = f.read_bytes()
            ui = not path.startswith('/assets/')
            hashed = path.startswith('/ui/')
            tag = '"' + hashlib.sha256(body).hexdigest()[:20] + '"'
            if ui and not hashed and self.headers.get('If-None-Match') == tag:
                self.send_response(304)
                self.send_header('ETag', tag)
                self.send_header('Cache-Control', 'no-cache')
                self.end_headers()
                return
            self.send_response(200)
            if hashed:  # content-hashed build output never changes under the same name
                self.send_header('Cache-Control', 'public, max-age=31536000, immutable')
            elif ui:  # index.html names the current build; browsers (iOS Safari especially) must revalidate it
                self.send_header('Cache-Control', 'no-cache')
                self.send_header('ETag', tag)
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header(
                'Content-Security-Policy',
                (
                    "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'none'; form-action 'none'"
                    if path.startswith('/assets/')
                    else "default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-src 'self'; script-src 'self'"
                ),
            )
            self.send_header('Content-Type', mimetypes.guess_type(f)[0] or 'application/octet-stream')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except Exception as e:
            self.send_json({'message': str(e)}, 400)

    def do_POST(self):
        if self.deny_host():
            return
        try:
            origin = self.headers.get('Origin')
            if origin and urlparse(origin).netloc != self.headers.get('Host'):
                raise ValueError('Cross-origin request rejected')
            n = int(self.headers.get('Content-Length', 0))
            if n > (8_000_000 if self.path.endswith('/reference-upload') else 1_000_000):
                raise ValueError('Request too large')
            if not self.headers.get('Content-Type', '').startswith('application/json'):
                raise ValueError('Content-Type must be application/json')
            try:
                d = json.loads(self.rfile.read(n) or '{}')
            except ValueError:
                raise ValueError('Request body is not valid JSON')
            if not isinstance(d, dict):
                raise ValueError('Request body must be a JSON object')
            action = self.path.split('/')[-1]
            if lan_mode() and action in RUNNER_ADMIN and not is_local_client(self.client_address[0], self.connection.getsockname()[0]):
                raise ValueError('Runner settings can only be changed from the computer running the studio')
            if action == 'local-runner':
                result = save('runner', dict(id=uid(), **configuration(d['agent'], d.get('model', ''))))
            elif action == 'project':
                result = project(d)
            elif action == 'update-project':
                p = get(d['id'])
                p.update({k: v for k, v in d.items() if k in ['name', 'archived', 'description']})
                result = save('project', p)
            elif action == 'context':
                result = context(d['project_id'], d)
            elif action == 'board':
                result = create_board(d)
            elif action == 'research-board':
                runner_ids = d.get('runner_ids', [])
                if len(set(runner_ids)) < 2:
                    raise ValueError('Choose at least two runner configurations')
                if any(r not in {r['id'] for r in allof('runner')} for r in runner_ids):
                    raise ValueError('Runner unavailable')
                key = d.get('idempotency_key')
                with LOCK:
                    previous = next(
                        (
                            b
                            for b in allof('board')
                            if key and b.get('handoff_key') == key and b['project_id'] == d['project_id']
                        ),
                        None,
                    )
                    board = previous or create_board(d)
                    board['handoff_key'] = key
                    save('board', board)
                    jobs = launch(dict(d, board_id=board['id']), 'generate_board', d['project_id'])
                result = {'board': board, 'jobs': jobs}
            elif action == 'generate' and (d.get('pair_free') or len(d.get('profile_ids') or []) > 1):
                # Same brief, runners, references and directions repeated per guidelines profile and, with a pair, once more with the rules off.
                b = get(d['board_id'])
                if d.get('pair_free') and b.get('blind'):
                    raise ValueError('Rules-vs-free pairs are not available while a board is blind; they would reveal which run is which')
                level = d['pair_free'] if d.get('pair_free') in ('rules', 'open') else 'open'
                pids = d.get('profile_ids') or [d.get('profile_id')]
                off = spread_offset(d['board_id'])
                key = d.get('idempotency_key')
                result = []
                for pid in pids:
                    kk = key if (key and len(pids) == 1) else ((key + ':' + str(pid)) if key else None)
                    base = dict(d, spread_offset=off, profile_id=pid, idempotency_key=kk)
                    result += launch(base, 'generate_board', d['project_id'])
                    if d.get('pair_free'):
                        free_ov = dict(d.get('overrides') or {}, free=level)
                        result += launch(dict(base, overrides=free_ov, idempotency_key=(kk + ':free') if kk else None), 'generate_board', d['project_id'])
            elif action == 'profile-create':
                result = profile_create(d['project_id'], d.get('name'), d.get('copy_from'))
            elif action == 'profile-update':
                result = profile_update(d['project_id'], d['profile_id'], d.get('name'), bool(d.get('make_default')))
            elif action == 'profile-delete':
                result = profile_delete(d['project_id'], d['profile_id'])
            elif action == 'revise' and d.get('states'):
                result = launch(dict(d, states=True), 'revise_board', d['project_id'])
            elif action in ['research', 'generate', 'revise']:
                result = launch(
                    d,
                    {'research': 'research', 'generate': 'generate_board', 'revise': 'revise_board'}[action],
                    d['project_id'],
                )
            elif action == 'finding':
                r = get(d['research_id'])
                for f in r['findings']:
                    if f['id'] == d['id']:
                        f['selected'] = d['selected']
                result = save('research', r)
            elif action == 'annotation':
                if not 0 <= d['x'] <= 1 or not 0 <= d['y'] <= 1 or not d['comment'].strip():
                    raise ValueError('Invalid annotation')
                get(d['variant_id'])
                result = save(
                    'annotation',
                    dict(
                        d,
                        id=uid(),
                        created_at=time.time(),
                        status='open',
                        selected=True,
                        element_id=d.get('element_id') or None,
                        view=d.get('view') if d.get('view') in ('d', 'm') else 'd',
                    ),
                )
            elif action == 'reference-upload':
                result = add_reference(d)
            elif action == 'reference-update':
                r = get(d['id'])
                r.update({k: str(d[k])[: 500 if k == 'note' else 80] for k in ['name', 'note'] if k in d})
                result = save('reference', r)
            elif action == 'reference-delete':
                result = delete_reference(d['id'])
            elif action == 'board-blind':
                result = set_blind(d['board_id'], d.get('blind', True))
            elif action == 'conflict-preview':
                result = conflict_preview(
                    d['project_id'], d.get('brief', ''), d.get('overrides'), d.get('reference_ids'), d.get('profile_id')
                )
            elif action == 'blind-choice':
                result = blind_choice(d['board_id'], d.get('variant_id'), d.get('reason', ''))
            elif action == 'mix':
                result = mix_variants(d['board_id'], d.get('picks'))
            elif action == 'share-create':
                result = share_create(d['prototype_id'], d.get('hours'))
            elif action == 'share-revoke':
                result = share_revoke(d['prototype_id'], d['token'])
            elif action == 'approve':
                result = approve(d['id'], d.get('note', ''))
            elif action == 'set-aside':
                result = set_aside(d['id'], d.get('note', ''))
            elif action == 'accept-revision':
                result = set_review_state(d['id'], 'accepted', d.get('note', ''))
            elif action == 'revert-revision':
                result = set_review_state(d['id'], 'reverted', d.get('note', ''))
            elif action == 'audit':
                result = audit_variant(d['variant_id'])
            elif action == 'scan-guidelines':
                if d.get('folder'):
                    # Reading an arbitrary folder is only for the computer running the studio; browsers elsewhere upload files instead.
                    if lan_mode() and not is_local_client(self.client_address[0], self.connection.getsockname()[0]):
                        raise ValueError('Folders can only be read from the computer running the studio; choose files instead')
                    result = read_folder(d['folder'])
                    if d.get('project_id') and d.get('remember', True):
                        p = get(d['project_id'])
                        p['guidelines_folder'] = result['folder']
                        save('project', p)
                else:
                    fl = d.get('files')
                    if not isinstance(fl, list) or not fl or not all(isinstance(x, dict) for x in fl):
                        raise ValueError('Choose a folder or at least one file')
                    result = parse_files(fl)
            elif action == 'audit-docs':
                result = launch_doc_review(d['variant_id'], d['runner_id'])
            elif action == 'audit-review':
                result = audit_review(d['variant_id'], d['audit_id'], d['index'], d['decision'], d.get('note', ''))
            elif action == 'set-review-folder':
                folder = str(d.get('folder', '')).strip()
                info = read_review_folder(folder)
                if folder and info['error']:
                    raise ValueError(info['error'])
                p = get(d['project_id'])
                p['review_folder'] = info['folder']
                save('project', p)
                result = dict(project=p, docs=[dict(file=x['file'], title=x['title'], criteria=len(x['criteria'])) for x in info['docs']], skipped=info['skipped'])
            elif action == 'review-docs':
                info = read_review_folder(get(d['project_id']).get('review_folder', ''))
                result = dict(folder=info['folder'], error=info['error'], skipped=info['skipped'], docs=[dict(file=x['file'], title=x['title'], criteria=len(x['criteria'])) for x in info['docs']])
            elif action == 'extract-style':
                result = extract_style(d['variant_id'])
            elif action == 'apply-style':
                result = apply_style(d['project_id'], d.get('tokens'), d.get('profile_id'))
            elif action == 'review-check':
                v = get(d['variant_id'])
                if d['decision'] not in ['accepted', 'needs_change', 'open']:
                    raise ValueError('Unknown decision')
                v.setdefault('reviews', {})[str(d['index'])] = dict(
                    decision=d['decision'], note=d.get('note', ''), time=time.time()
                )
                result = save('variant', v)
            elif action == 'annotation-update':
                a = get(d['id'])
                if a.get('status', 'open') != 'open':
                    raise ValueError('Applied feedback is part of history and cannot be edited')
                a.update({k: d[k] for k in ['comment', 'selected'] if k in d})
                if not str(a['comment']).strip():
                    raise ValueError('Comment cannot be empty')
                result = save('annotation', a)
            elif action == 'annotation-delete':
                a = get(d['id'])
                if a.get('status', 'open') != 'open':
                    raise ValueError('Applied feedback is part of history and cannot be deleted')
                with LOCK, db() as c:
                    c.execute('DELETE FROM entities WHERE id=?', (a['id'],))
                result = {'deleted': a['id']}
            elif action == 'cancel-job':
                cancel_job(d['id'])
                result = {'cancelling': d['id']}
            elif action == 'dismiss-job':
                j = get(d['id'])
                if j['status'] in ('queued', 'running'):
                    raise ValueError('Cancel a running job before dismissing it')
                j['dismissed'] = True
                result = save('job', j)
            elif action == 'retry-job':
                result = retry_job(d['id'])
            elif action == 'update-runner':
                r = get(d['id'])
                r.update({k: d[k] for k in ['name', 'enabled', 'timeout'] if k in d})
                if 'auto_retries' in d:
                    if not isinstance(d['auto_retries'], int) or not 0 <= d['auto_retries'] <= 3:
                        raise ValueError('Automatic retries must be 0 to 3')
                    r['auto_retries'] = d['auto_retries']
                if 'sandbox' in d:
                    if d['sandbox'] not in (None, 'bwrap', 'none'):
                        raise ValueError('Unknown sandbox')
                    if d['sandbox'] == 'bwrap' and not bwrap_ok():
                        raise ValueError('bubblewrap is not usable on this machine')
                    r['sandbox'] = 'bwrap' if d['sandbox'] == 'bwrap' else None
                    if r.get('agent'):
                        # The agent's own flags must follow ours, and runners created before the sandbox existed lack
                        # the bind lists it needs (install and auth folders), so refresh those too.
                        cfg = configuration(r['agent'], r.get('model', ''), sandbox=bool(r['sandbox']))
                        r['args'] = cfg['args']
                        r['sandbox_ro'], r['sandbox_rw'] = cfg['sandbox_ro'], cfg['sandbox_rw']
                if 'env_allowlist' in d:
                    names = [str(x).strip() for x in d['env_allowlist'] if str(x).strip()]
                    if any(not re.fullmatch(r'[A-Z_][A-Z0-9_]*', n) for n in names):
                        raise ValueError('Environment variable names must be UPPER_SNAKE_CASE')
                    r['env_allowlist'] = names
                if 'model' in d and r['type'] == 'cli':
                    if r.get('agent') and d['model'].strip() != r.get('model', ''):
                        r['args'] = configuration(r['agent'], d['model'].strip(), sandbox=bool(r.get('sandbox')))[
                            'args'
                        ]
                    r['model'] = d['model'].strip()
                if not str(r['name']).strip():
                    raise ValueError('Runner needs a name')
                result = save('runner', r)
            elif action == 'delete-runner':
                if len([r for r in allof('runner') if r['id'] != d['id'] and r.get('enabled', True)]) < 1:
                    raise ValueError('Keep at least one enabled runner')
                with LOCK, db() as c:
                    c.execute('DELETE FROM entities WHERE id=?', (d['id'],))
                result = {'deleted': d['id']}
            elif action == 'board-research':
                b = get(d['board_id'])
                r = get(d['research_id'])
                ids = d.get('finding_ids', [])
                f = [x for x in r['findings'] if x['id'] in ids]
                if b['project_id'] != r.get('project_id') or not f or len(f) != len(set(ids)):
                    raise ValueError('Choose valid findings from this project')
                b.update(
                    research_id=r['id'],
                    research_brief=r['brief'],
                    research_findings=f,
                    research_sources=r.get('sources', []),
                    research_updated_at=time.time(),
                )
                result = save('board', b)
            elif action == 'runner':
                # Never accept an executable from the API: coding agents come only from the installed-agent scan (local-runner).
                if d.get('type') == 'cli' and os.environ.get('STUDIO_UNSAFE_TEST_RUNNERS') == '1' and not lan_mode():
                    # Test-only escape hatch (off by default, ignored in LAN mode): lets the browser tests register scripted fake agents.
                    result = save('runner', dict(id=uid(), name=str(d.get('name', 'Test CLI'))[:60], type='cli', executable=str(d['executable']), args=[str(a) for a in d.get('args', [])], timeout=int(d.get('timeout', 60)), enabled=True, **{k: d[k] for k in ('auto_retries', 'sandbox') if k in d}))
                elif d.get('type') == 'fixture':
                    style = d.get('style') if d.get('style') in ('a', 'b') else 'a'
                    result = save('runner', dict(id=uid(), name=' '.join(str(d.get('name') or 'Template').split())[:60], type='fixture', style=style))
                else:
                    raise ValueError('Only template runners can be added here. Add coding agents from Settings → Agents (installed agents only).')
            elif action == 'test-runner':
                r = get(d['id'])
                result = {
                    'message': (
                        'Fixture ready'
                        if r['type'] == 'fixture'
                        else ('Executable found' if shutil.which(r.get('executable', '')) else 'Executable unavailable')
                    )
                }
            else:
                raise ValueError('Unknown action')
            self.send_json(result)
        except (ValueError, KeyError, TypeError, AttributeError) as e:
            msg = (
                ('Missing or invalid field: ' + str(e))
                if isinstance(e, (KeyError, TypeError, AttributeError))
                else str(e)
            )
            self.send_json({'code': 'INVALID_REQUEST', 'message': msg, 'request_id': uid()}, 400)
        except Exception:
            rid = uid()
            log.exception('unhandled error %s %s (request %s)', self.command, self.path, rid)
            self.send_json(
                {'code': 'INTERNAL_ERROR', 'message': 'Unexpected server error; see studio.log', 'request_id': rid}, 500
            )


def health():
    # Cheap liveness/readiness: database reachable, workers alive, queue depth, disk space.
    with db() as c:
        c.execute('SELECT 1').fetchone()
    jobs = allof('job')
    counts = {}
    for j in jobs:
        counts[j['status']] = counts.get(j['status'], 0) + 1
    return dict(
        ok=True,
        uptime_s=int(time.time() - STARTED),
        workers=sum(t.is_alive() for t in WORKERS),
        queued=JOBQ.qsize(),
        jobs=counts,
        free_disk_mb=shutil.disk_usage(core.STORE).free // 1_000_000,
        bwrap=bwrap_ok(),
        storage=str(core.STORE),
    )


def main():
    import errno
    import sys

    try:
        port = int(os.environ.get('PORT', '5173'))
        if not 0 < port < 65536:
            raise ValueError()
    except ValueError:
        print('Design Studio: PORT must be an integer from 1 to 65535.', file=sys.stderr)
        return 1
    try:
        bind = os.environ.get('STUDIO_HOST', '127.0.0.1').strip() or '127.0.0.1'
        server = ThreadingHTTPServer((bind, port), Handler)
    except OSError as error:
        if error.errno == errno.EADDRINUSE:
            print(
                f'Design Studio: port {port} is already in use. Stop the existing server or choose another port:\n  PORT={port+1 if port<65535 else 5173} python3 apps/api/server.py',
                file=sys.stderr,
            )
        elif error.errno in (errno.EACCES, errno.EPERM):
            print(
                f'Design Studio: permission denied opening 127.0.0.1:{port}. Run in a terminal that permits local server sockets, or choose an unprivileged port with PORT=5174.',
                file=sys.stderr,
            )
        else:
            print(f'Design Studio: cannot listen on {bind}:{port}: {error}', file=sys.stderr)
        return 1
    share = None
    if SHARE_PORT:
        try:
            share = ThreadingHTTPServer((os.environ.get('STUDIO_SHARE_HOST', '127.0.0.1'), SHARE_PORT), ShareHandler)
            threading.Thread(target=share.serve_forever, daemon=True).start()
            print(
                f'Share links enabled on port {SHARE_PORT} (read-only prototype bundles only; the studio itself stays on 127.0.0.1)',
                flush=True,
            )
        except OSError as e:
            print(f'Share listener could not start on port {SHARE_PORT}: {e}', file=sys.stderr)
    with server:
        setup_logging()
        seed()
        resumed = recover_jobs()
        start_workers()
        signal.signal(signal.SIGTERM, lambda *_: (_ for _ in ()).throw(KeyboardInterrupt()))
        if resumed:
            print(f'Resumed {resumed} queued job(s) after restart', flush=True)
        print(f'Design Studio → http://localhost:{port}', flush=True)
        if os.environ.get('STUDIO_OPEN_BROWSER', '1' if getattr(sys, 'frozen', False) else '0') == '1':
            import webbrowser

            threading.Timer(0.8, lambda: webbrowser.open(f'http://localhost:{port}')).start()
        if lan_mode():
            urls = [f'http://{ip}:{port}' for ip in lan_ips()] or [f'http://<this-computer>:{port}']
            print('LAN mode: reachable from your network at ' + ', '.join(urls), flush=True)
            print('  No login: anyone on this network can use the studio and spend your agent credits. Runner settings stay local-only.', flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            log.info('shutting down')
        finally:
            stop_workers()
            if share:
                share.shutdown()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
