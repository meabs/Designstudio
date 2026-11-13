"""HTTP layer: studio API handler, share listener, health check and process entry point."""

import signal, sys, os, json, hashlib, threading, time, re, zipfile, io, shutil
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler, BaseHTTPRequestHandler
from urllib.parse import urlparse
from local_agents import discover, configuration, bwrap_ok
from boards import blind_choice, conflict_preview, create_board, hidden_job_file, launch, mask_state, set_blind
from contexts import context, project, seed
from core import LOCK, ROOT, SHARE_PORT, STARTED, allof, db, get, log, safe_path, save, setup_logging, uid
from jobs import JOBQ, WORKERS, cancel_job, recover_jobs, retry_job, start_workers, stop_workers
from prototypes import approve, mix_variants, set_review_state
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


def host_ok(host):
    # DNS-rebinding guard: the studio can start local agents, so only loopback host names are served.
    h = (host or '').rsplit(':', 1)[0] if not (host or '').endswith(']') else host
    return h.lower() in ALLOWED_HOSTS or h.lower() in {
        x.strip().lower() for x in os.environ.get('STUDIO_ALLOWED_HOSTS', '').split(',') if x.strip()
    }


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
            if path == '/api/health':
                return self.send_json(health())
            if path == '/api/local-agents':
                return self.send_json(discover())
            if path == '/api/config':
                return self.send_json(dict(bwrap=bwrap_ok(), share_port=SHARE_PORT))
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
                f = (
                    safe_path(ROOT / 'apps/web', path.lstrip('/'))
                    if '.' in path.split('/')[-1]
                    else ROOT / 'apps/web/index.html'
                )
            if not f.is_file():
                return self.send_error(404)
            import mimetypes

            self.send_response(200)
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
            self.end_headers()
            self.wfile.write(f.read_bytes())
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
                    d['project_id'], d.get('brief', ''), d.get('overrides'), d.get('reference_ids')
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
                result = approve(d['id'])
            elif action == 'accept-revision':
                result = set_review_state(d['id'], 'accepted')
            elif action == 'revert-revision':
                result = set_review_state(d['id'], 'reverted')
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
                        r['args'] = configuration(r['agent'], r.get('model', ''), sandbox=bool(r['sandbox']))[
                            'args'
                        ]  # the agent's own sandbox flag must follow ours
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
                if d['type'] not in ['fixture', 'cli']:
                    raise ValueError('Unsupported runner')
                result = save('runner', dict(id=uid(), **d))
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
        server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
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
            print(f'Design Studio: cannot listen on 127.0.0.1:{port}: {error}', file=sys.stderr)
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
