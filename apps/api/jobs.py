"""Durable job queue, workers, sandboxed runner execution, retries and agent self-report parsing."""

import os, json, signal, threading, time, re, subprocess, shutil, queue
from pathlib import Path
from local_agents import bwrap_ok
from core import LOCK, allof, get, log, safe_path, save, uid
from fixture import ALLOWED_OUTPUT, fixture_tokens, render_screen
from references import snapshot_references
from regions import diff_regions, region_revise, stamp_anchors
from research import sanitize_research
from validation import check_manifest, validate
import core


def event(j, status, message):
    j['status'] = status
    j['events'].append(dict(time=time.time(), message=message))
    save('job', j)


CANCEL = set()
MAX_JOBS = max(1, int(os.environ.get('STUDIO_MAX_JOBS', '3')))
CANCEL = set()
MAX_JOBS = max(1, int(os.environ.get('STUDIO_MAX_JOBS', '3')))


class Cancelled(Exception):
    pass


def check_cancel(j):
    if j['id'] in CANCEL:
        raise Cancelled()


def sandbox_command(runner, command, jobdir):
    # Filesystem sandbox (bubblewrap): everything read-only, home and the studio's storage hidden, only this job's folder writable.
    # Agent install/auth directories are re-bound explicitly (see runner.sandbox_ro / sandbox_rw); the network stays available for model calls.
    if not bwrap_ok():
        raise ValueError('Sandbox is enabled for this runner but bubblewrap is not usable on this machine')
    home = str(Path.home())
    job = str(Path(jobdir).resolve())
    store = str(core.STORE.resolve())
    args = [
        'bwrap',
        '--ro-bind',
        '/',
        '/',
        '--dev',
        '/dev',
        '--proc',
        '/proc',
        '--tmpfs',
        '/tmp',
        '--tmpfs',
        home,
        '--tmpfs',
        store,
    ]
    for p in runner.get('sandbox_ro', []):
        args += ['--ro-bind-try', os.path.expanduser(p), os.path.expanduser(p)]
    for p in runner.get('sandbox_rw', []):
        args += ['--bind-try', os.path.expanduser(p), os.path.expanduser(p)]
    exe = runner.get('executable')
    if exe and exe.startswith(home):
        # The executable lives under the hidden home: recreate its symlink (or bind the file) so the sandbox can start it.
        args += ['--symlink', os.readlink(exe), exe] if os.path.islink(exe) else ['--ro-bind-try', exe, exe]
    args += [
        '--bind',
        job,
        job,
        '--unshare-pid',
        '--unshare-ipc',
        '--unshare-uts',
        '--die-with-parent',
        '--new-session',
        '--chdir',
        job,
        '--',
    ]
    return args + command


DEFAULT_ENV_ALLOWLIST = ['PATH', 'HOME', 'USER', 'LANG', 'LC_ALL', 'TERM', 'TMPDIR', 'SHELL']


def runner_env(runner):
    return {k: os.environ[k] for k in runner.get('env_allowlist', DEFAULT_ENV_ALLOWLIST) if k in os.environ}


def run_cli(command, out, timeout, j, runner=None):
    # Streams to runner.log so a partial log survives a timeout or cancellation.
    with open(out / 'runner.log', 'w') as log:
        proc = subprocess.Popen(
            command,
            cwd=out,
            stdin=subprocess.DEVNULL,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
            env=runner_env(runner or {}),
        )
        start = time.time()
        while proc.poll() is None:
            if j['id'] in CANCEL:
                proc.terminate()
                proc.wait()
                raise Cancelled()
            if time.time() - start > timeout:
                proc.kill()
                proc.wait()
                raise subprocess.TimeoutExpired(command, timeout)
            time.sleep(0.2)
    return proc.returncode


IGNORE_RE = re.compile(
    r"not followed|ignored|did not (?:follow|use|view|open|apply)|didn't (?:follow|use|view|open|apply)|never opened|skipped|omitted|left out|could not honou?r|conflicts? with|declined|did not include",
    re.I,
)
SOURCE_RE = re.compile(r"brief|reference|mood ?board|sketch|woodcut|note|image", re.I)
NOT_VIEWED_RE = re.compile(
    r"(?:did not|didn't|never|not|haven't|have not)\s+(?:\w+\s+){0,2}(?:view|viewed|open|opened|look(?:ed)? at|examine[d]?|inspect(?:ed)?|see|seen)[^.\n]{0,60}(?:reference|image|mood ?board|sketch)|(?:reference|image)s?[^.\n]{0,40}(?:not (?:viewed|opened|examined)|unviewed)",
    re.I,
)
VIEWED_RE = re.compile(
    r"\b(?:viewed|opened|looked at|examined|inspected|studied)\b[^.\n]{0,60}(?:reference|image|mood ?board|sketch)",
    re.I,
)


def parse_agent_report(log_text, has_refs):
    # The agent's closing message, parsed for what it says it did not follow. A self-report: unverified, never used for pass/fail.
    lines = [l for l in log_text.splitlines() if not re.match(r'\s*(SessionEnd hook|hook:|tokens used|[\d,]+\s*$)', l)]
    tail = '\n'.join(lines)[-2400:].strip()
    half = tail[len(tail) // 2 :] if tail.count('Created the static package') > 1 else tail
    ignored = [
        re.sub(r'^[\s\-*]+', '', l).strip() for l in half.splitlines() if IGNORE_RE.search(l) and SOURCE_RE.search(l)
    ][:8]
    viewed = None
    if has_refs:
        viewed = False if NOT_VIEWED_RE.search(half) else (True if VIEWED_RE.search(half) else None)
    return dict(text=half[-1800:], ignored=ignored, viewed_references=viewed)


def record_report(j):
    try:
        jd = get(j['id'])
        logp = core.STORE / 'jobs' / j['id'] / 'runner.log'
        if jd.get('runner_id') is None or not logp.is_file():
            return
        r = parse_agent_report(logp.read_text(errors='replace'), bool(jd.get('references')))
        if not r['text']:
            return
        jd['agent_report'] = r
        save('job', jd)
        if jd.get('variant_id') and (r['ignored'] or r['viewed_references'] is False):
            v = get(jd['variant_id'])
            ev = ' | '.join(r['ignored'][:4]) or 'Agent says it did not view the reference images'
            if r['viewed_references'] is False and 'did not view' not in ev:
                ev += ' | Agent says it did not view the reference images'
            v.setdefault('validation', []).append(
                dict(
                    check='Agent self-report: parts of the brief or references not followed (unverified)',
                    outcome='review',
                    evidence=ev[:700],
                )
            )
            save('variant', v)
    except Exception:
        log.exception('could not record agent report for job %s', j.get('id'))


TOKENS_RE = re.compile(r'tokens used\s*[:\n]\s*([\d,]+)', re.I)
ANSI_RE = re.compile(r'\x1b\[[0-9;?]*[A-Za-z]|[\x00-\x08\x0b\x0c\x0e-\x1f]')


def record_usage(j, started):
    # Wall-clock time per job, plus a token count only when the agent printed one (Codex does, Claude Code in --print mode does not).
    try:
        jd = get(j['id'])
        tokens = None
        logp = core.STORE / 'jobs' / j['id'] / 'runner.log'
        if logp.is_file():
            hits = TOKENS_RE.findall(logp.read_text(errors='replace')[-6000:])
            tokens = int(hits[-1].replace(',', '')) if hits else None
        jd['usage'] = dict(duration_s=round(time.time() - started, 1), tokens=tokens)
        save('job', jd)
    except Exception:
        log.exception('could not record usage for job %s', j.get('id'))


def execute(j):
    started = time.time()
    try:
        check_cancel(j)
        _execute(j)
    except Cancelled:
        event(j, 'cancelled', 'Cancelled by designer; no variation was saved')
    finally:
        record_report(j)
        record_usage(j, started)


def job_progress(jid):
    """What is happening in a job right now: elapsed time, files the agent has written, a tail of its log.
    The log tail and file names are withheld while the board is blind (they can name the runner)."""
    j = get(jid)
    now = time.time()
    done = j['status'] not in ('queued', 'running')
    started = next((e['time'] for e in j['events'] if e['message'].startswith('Runner started')), None)
    end = j['events'][-1]['time'] if done and j['events'] else now
    base = core.STORE / 'jobs' / jid
    out = base / 'output'
    files = []
    if out.is_dir():
        for f in sorted(out.rglob('*')):
            if f.is_file() and not f.is_symlink():
                files.append(dict(name=str(f.relative_to(out)), size=f.stat().st_size, mtime=f.stat().st_mtime))
    board = get(j['board_id']) if j.get('board_id') else None
    blind = bool(board and board.get('blind') and not board.get('revealed'))
    logp = base / 'runner.log'
    tail = ''
    if logp.is_file() and not blind:
        raw = logp.read_bytes()[-1600:].decode(errors='replace')
        tail = ANSI_RE.sub('', raw).strip()
    last = max([f['mtime'] for f in files] + ([logp.stat().st_mtime] if logp.is_file() else []) + [started or 0])
    position = None
    if j['status'] == 'queued':
        position = 1 + sum(1 for x in allof('job') if x['status'] == 'queued' and x['created_at'] < j['created_at'])
    return dict(
        status=j['status'],
        elapsed_s=round(end - started, 1) if started else 0,
        idle_s=round(now - last, 1) if started and not done else 0,
        queue_position=position,
        screens_written=sum(1 for f in files if re.fullmatch(r'screens/\d+\.html', f['name'])),
        screens_expected=len(board['screens']) if board and j['type'] in ('generate_board', 'revise_board') else None,
        files=[] if blind else [dict(name=f['name'], size=f['size']) for f in files[:40]],
        file_count=len(files),
        log_tail=tail,
        log_hidden=blind,
        timeout_s=(get(j['runner_id']).get('timeout') if j.get('runner_id') else None),
    )


JOBQ = queue.Queue()
WORKERS = []
JOBQ = queue.Queue()
WORKERS = []


def enqueue(j):
    JOBQ.put(j['id'])


def claim(jid):
    # Atomically move queued -> running so a cancel and a worker can never both win.
    with LOCK:
        j = get(jid)
        if j['status'] != 'queued':
            return None
        if jid in CANCEL:
            event(j, 'cancelled', 'Cancelled before it started')
            return None
        j['status'] = 'running'
        save('job', j)
        return j


def worker():
    while True:
        jid = JOBQ.get()
        if jid is None:
            JOBQ.task_done()
            return
        try:
            j = claim(jid)
            if j:
                execute(j)
                maybe_auto_retry(jid)
        except Exception:
            log.exception('worker error on job %s', jid)
        finally:
            JOBQ.task_done()


def start_workers(n=None):
    while len(WORKERS) < (n or MAX_JOBS):
        t = threading.Thread(target=worker, daemon=True)
        t.start()
        WORKERS.append(t)


def stop_workers():
    for _ in WORKERS:
        JOBQ.put(None)
    for t in WORKERS:
        t.join(10)
    WORKERS.clear()


def recover_jobs():
    # Queued jobs resume in their original order; jobs that were mid-run cannot be trusted, so they fail visibly and can be retried with the same inputs.
    resumed = 0
    for j in sorted(allof('job'), key=lambda x: x['created_at']):
        if j['status'] == 'running':
            event(j, 'failed', 'Interrupted by a server restart; use Retry to run it again with the same inputs')
        elif j['status'] == 'queued':
            j['events'].append(dict(time=time.time(), message='Resumed after server restart'))
            save('job', j)
            enqueue(j)
            resumed += 1
    return resumed


def cancel_job(jid):
    with LOCK:
        j = get(jid)
        if j['status'] not in ['queued', 'running']:
            raise ValueError('Only queued or running jobs can be cancelled')
        CANCEL.add(jid)
        if j['status'] == 'queued':
            event(j, 'cancelled', 'Cancelled before it started')


def _execute(j):
    folder = None
    try:
        event(j, 'running', 'Runner started with immutable context snapshot')
        ctx = j['context']
        runner = get(j['runner_id'])
        out = core.STORE / 'jobs' / j['id']
        out.mkdir(parents=True, exist_ok=True)
        (out / 'envelope.json').write_text(json.dumps(j, indent=2))
        (out / 'TASK.md').write_text(j['instruction'])
        if runner['type'] == 'cli':
            command = [runner['executable']] + [
                s.replace('{input}', str(out / 'envelope.json'))
                .replace('{output}', str(out / 'output'))
                .replace('{instruction}', str(out / 'TASK.md'))
                .replace(
                    '{prompt}',
                    j['instruction'] + '\nRead envelope.json for full inputs. Write all deliverables to output/.',
                )
                for s in runner.get('args', [])
            ]
            (out / 'output').mkdir(exist_ok=True)
            if j.get('parent_id'):
                # Revisions start from a copy of the parent version, so the agent edits in place and untouched files stay identical.
                shutil.copytree(
                    core.STORE / 'variants' / j['parent_id'],
                    out / 'output',
                    dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns('thumbnails', 'changes.json'),
                )
            if runner.get('sandbox') == 'bwrap':
                command = sandbox_command(runner, command, out)
            if run_cli(command, out, min(int(runner.get('timeout', 120)), 600), j, runner):
                raise ValueError('CLI runner failed; see runner.log in the job history')
        time.sleep(0.4)
        check_cancel(j)
        if j['type'] == 'research':
            result = {
                'findings': [
                    dict(id=uid(), title=t, detail=d, selected=False, verification='unverified_claim', source_ids=[])
                    for t, d in [
                        (
                            'Explain before you ask',
                            'Synthetic fixture: explain the purpose of eligibility questions before requesting information.',
                        ),
                        (
                            'Make progress visible',
                            'Synthetic fixture: a short, predictable journey can help users understand the next step.',
                        ),
                    ]
                ],
                'sources': j.get('sources', []),
            }
            if runner['type'] == 'cli':
                rf = out / 'output' / 'research.json'
                if not rf.is_file():
                    raise ValueError(
                        'The agent finished without writing output/research.json. Open runner.log in the job history to see what it said.'
                    )
                try:
                    result = sanitize_research(json.loads(rf.read_text()), j.get('sources', []))
                except ValueError as e:
                    raise ValueError('Invalid research output: ' + str(e))
            for finding in result['findings']:
                finding.setdefault('id', uid())
                finding.setdefault('selected', False)
                if not finding.get('source_ids'):
                    finding['verification'] = 'unverified_claim'
            # Own ID: entities share one primary key, so reusing the job's ID let the final job save overwrite this record.
            j['research_id'] = uid()
            save(
                'research',
                dict(
                    id=j['research_id'],
                    job_id=j['id'],
                    project_id=j['project_id'],
                    brief=j['brief'],
                    created_at=time.time(),
                    **result,
                ),
            )
        elif j['type'] == 'audit_review':
            from audit import finish_doc_review

            finish_doc_review(j, out, runner['type'])
        else:
            board = get(j['board_id'])
            parent = get(j['parent_id']) if j.get('parent_id') else None
            variant = dict(
                id=uid(),
                project_id=j['project_id'],
                board_id=board['id'],
                job_id=j['id'],
                runner_id=runner['id'],
                runner_name=runner['name'],
                style=runner.get('style', 'a'),
                parent_id=j.get('parent_id'),
                context_id=ctx['id'],
                profile_id=ctx.get('profile_id', 'main'),
                profile_name=ctx.get('profile_name', 'Main'),
                version=parent['version'] + 1 if parent else 1,
                approved=False,
                created_at=time.time(),
                changes=[],
            )
            folder = core.STORE / 'variants' / variant['id']
            (folder / 'screens').mkdir(parents=True)
            variant['blind_label'] = j.get('blind_label') or (parent or {}).get('blind_label')
            variant['review_state'] = 'pending' if parent else None
            variant['references'] = j.get('references', [])
            manifest = dict(
                schema_version='1.0',
                kind='clickthrough-static',
                board_id=board['id'],
                start_screen_id='0',
                screens=[],
                edges=[],
            )
            annotations = j.get('annotations', [])
            for i, title in enumerate(board['screens']):
                matching = [a for a in annotations if a['screen'] == str(i)]
                sc = (j.get('scope') or {}).get(str(i), {})
                parent_html = (
                    (core.STORE / 'variants' / parent['id'] / 'screens' / f'{i}.html').read_text() if parent else ''
                )
                content = render_screen(
                    title,
                    i,
                    board['screens'],
                    ctx,
                    variant['style'],
                    bool(matching),
                    ' '.join(a['comment'] for a in matching),
                    brief=j.get('brief', ''),
                )
                if parent and not matching:
                    content = parent_html
                elif parent and sc.get('mode') == 'region':
                    notes = {}
                    for a in matching:
                        notes.setdefault(a['element_id'], a['comment'])
                    content = region_revise(parent_html, notes) or content
                if runner['type'] == 'fixture':
                    (folder / 'screens' / f'{i}.html').write_text(content)
                manifest['screens'].append(
                    dict(
                        id=str(i),
                        title=title,
                        file=f'screens/{i}.html',
                        states=['default', 'help', 'error'] if i == 1 else ['default', 'help'],
                    )
                )
                if i < len(board['screens']) - 1:
                    manifest['edges'].append({'from': str(i), 'to': str(i + 1), 'trigger': 'continue'})
                if matching:
                    variant['changes'].append(f'{title}: ' + '; '.join(a['comment'] for a in matching))
            if runner['type'] == 'cli':
                source = out / 'output'
                for f in source.rglob('*'):
                    if f.is_symlink() or not f.resolve().is_relative_to(source.resolve()):
                        raise ValueError('Unsafe output symlink')
                    if f.is_file() and f.suffix.lower() not in ALLOWED_OUTPUT:
                        raise ValueError(
                            f'Unsupported output file output/{f.relative_to(source)}. Allowed types: '
                            + ', '.join(sorted(ALLOWED_OUTPUT))
                        )
                written = sorted(str(f.relative_to(source)) for f in source.rglob('*') if f.is_file())
                if not (source / 'manifest.json').is_file():
                    raise ValueError(
                        'The agent finished without writing output/manifest.json ('
                        + (
                            f'it wrote {len(written)} other file(s): ' + ', '.join(written[:6])
                            if written
                            else 'it wrote no files'
                        )
                        + '). Open runner.log in the job history to see what it said.'
                        + (
                            ' The log mentions a blocked or unapproved action: the agent probably could not run a command it needed. Check the runner\'s sandbox setting in Settings, then retry.'
                            if re.search(r'blocked|not allowed|approval|permission', (out / 'runner.log').read_text(errors='replace')[-3000:], re.I)
                            else ''
                        )
                    )
                try:
                    manifest_check = json.loads((source / 'manifest.json').read_text())
                except ValueError as e:
                    raise ValueError('output/manifest.json is not valid JSON: ' + str(e))
                shutil.copytree(source, folder, dirs_exist_ok=True)
                manifest = manifest_check
                variant['anchors_added'] = {}
                for sd in manifest.get('screens', []):
                    pf = folder / sd.get('file', '')
                    if pf.is_file() and not pf.is_symlink() and pf.suffix == '.html':
                        new, n = stamp_anchors(pf.read_text(errors='replace'))
                        if n:
                            pf.write_text(new)
                            variant['anchors_added'][sd['id']] = n
            (folder / 'manifest.json').write_text(json.dumps(manifest, indent=2))
            variant['manifest'] = manifest
            check_manifest(manifest)
            if {s['id'] for s in manifest['screens']} != {str(i) for i in range(len(board['screens']))}:
                raise ValueError('Screen IDs must be zero-based strings')
            if len(manifest['screens']) != len(board['screens']):
                raise ValueError('Missing requested screens')
            variant['validation'] = validate(folder, manifest, ctx['effective_rules'], ctx['tokens'])
            if ctx.get('run_overrides', {}).get('free'):
                # Free run: nothing was enforced, so record what the project's saved rules would have said (the rule-break log).
                from contexts import current_context

                saved = current_context(j['project_id'], ctx.get('profile_id'))
                variant['rule_breaks'] = dict(
                    context_id=saved['id'],
                    context_version=saved['version'],
                    results=validate(folder, manifest, saved['effective_rules'], saved['tokens']),
                )
            if variant.get('anchors_added'):
                variant['validation'].append(
                    dict(
                        check='Annotation anchors added by the studio',
                        outcome='review',
                        evidence='The agent emitted no data-design-id on '
                        + str(len(variant['anchors_added']))
                        + ' screen(s), so the studio added '
                        + str(sum(variant['anchors_added'].values()))
                        + ' anchors (auto-<tag>-<n>) to make pins and region revisions possible. Markup is otherwise unchanged.',
                    )
                )
            if variant['references']:
                variant['validation'].append(
                    dict(
                        check=f"Reference images ({len(variant['references'])})",
                        outcome='review',
                        evidence=(
                            'Recorded with the job, but the fixture runner cannot interpret images. Use a local coding agent to apply them.'
                            if runner['type'] == 'fixture'
                            else 'Passed to the agent as files. Whether they were applied needs your judgement; this is not verified.'
                        ),
                    )
                )
            if runner['type'] == 'fixture':
                variant['validation'].append(
                    dict(
                        check='Fixture guidance support',
                        outcome='review',
                        evidence='Template demo: supports tokens and explicit text/background/button color directives. Other prose rules need a local coding agent; no general rule conformance is claimed.',
                    )
                )
                variant['applied_tokens'] = fixture_tokens(ctx)
            if parent:
                scope = j.get('scope') or {}
                variant['changed_regions'] = {}
                variant['revision_scope'] = scope
                for screen_def in manifest['screens']:
                    before = safe_path(core.STORE / 'variants' / parent['id'], screen_def['file']).read_text(
                        errors='replace'
                    )
                    after = safe_path(folder, screen_def['file']).read_text(errors='replace')
                    sc = scope.get(screen_def['id'])
                    title = screen_def['title']
                    if before == after:
                        if sc:
                            variant['validation'].append(
                                dict(
                                    check='Revision scope · ' + title,
                                    outcome='review',
                                    evidence='The agent made no change to this targeted screen.',
                                )
                            )
                        continue
                    d = diff_regions(before, after)
                    variant['changed_regions'][screen_def['id']] = d
                    if not sc:
                        variant['validation'].append(
                            dict(
                                check='Revision scope · ' + title,
                                outcome='fail',
                                evidence='Changed although no feedback targeted this screen.',
                            )
                        )
                    elif sc['mode'] == 'region':
                        extra = [x for x in d['elements'] if x not in sc['elements']]
                        variant['validation'].append(
                            dict(
                                check='Revision scope · ' + title,
                                outcome='fail' if (extra or d['outside']) else 'pass',
                                evidence=(
                                    (
                                        'Changed outside the pinned element(s): '
                                        + ', '.join(extra + (['page content'] if d['outside'] else []))
                                    )
                                    if (extra or d['outside'])
                                    else 'Only the pinned element(s) changed: ' + ', '.join(d['elements'])
                                ),
                            )
                        )
                (folder / 'changes.json').write_text(json.dumps(variant['changes']))
            variant['changed_screens'] = [
                sd['id']
                for sd in manifest['screens']
                if parent
                and (folder / sd['file']).read_bytes()
                != safe_path(core.STORE / 'variants' / parent['id'], sd['file']).read_bytes()
            ]
            # Capture actual rendered screens using the locally installed browser.
            (folder / 'thumbnails').mkdir(exist_ok=True)
            for s in manifest['screens']:
                check_cancel(j)
                chrome_screenshot(j['id'], safe_path(folder, s['file']), folder / 'thumbnails' / f'{s["id"]}.png')
                if not (folder / 'thumbnails' / f'{s["id"]}.png').is_file():
                    variant['validation'].append(
                        dict(
                            check='Screenshot capture · ' + s['title'],
                            outcome='not_assessable',
                            evidence='Local Chrome capture unavailable',
                        )
                    )
            shutil.rmtree(f'/tmp/studio-chrome-{j["id"]}', ignore_errors=True)  # one throwaway Chrome profile per job
            check_cancel(j)
            save('variant', variant)
            j['variant_id'] = variant['id']
            folder = None
        event(j, 'succeeded', 'Artifacts saved and deterministic validation completed')
    except Cancelled:
        if folder:
            shutil.rmtree(folder, ignore_errors=True)
        raise
    except subprocess.TimeoutExpired:
        event(j, 'timed_out', 'Runner exceeded the configured timeout; partial log kept in job history')
    except Exception as e:
        event(j, 'failed', str(e))


def chrome_screenshot(job_id, page, png, timeout=20):
    # Headless Chrome spawns helper processes and can hang; run it in its own process group and kill the whole group on timeout,
    # then remove its throwaway profile so nothing is left behind.
    profile = f'/tmp/studio-chrome-{job_id}'
    cmd = ['google-chrome', '--headless', '--no-sandbox', '--disable-gpu', '--hide-scrollbars', '--no-pdf-header-footer', '--window-size=720,960', f'--user-data-dir={profile}', f'--screenshot={png}', page.as_uri()]
    try:
        p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
    except FileNotFoundError:
        return False
    try:
        p.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        pass
    finally:
        try:
            os.killpg(p.pid, signal.SIGKILL)  # also reaps helper processes Chrome leaves behind after a normal exit
        except (ProcessLookupError, PermissionError):
            pass
        try:
            p.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
    return Path(png).is_file()


def maybe_auto_retry(jid):
    try:
        j = get(jid)
        if (
            j['status'] not in ('failed', 'timed_out')
            or j.get('retried_by')
            or j['id'] in CANCEL
            or not j.get('runner_id')
        ):
            return
        runner = get(j['runner_id'])
        limit = int(runner.get('auto_retries', 0))
        attempt = int(j.get('attempt', 1))
        if attempt > limit:
            return
        new = retry_job(jid, auto=(attempt + 1, limit + 1), defer=2 * attempt)
    except Exception:
        return


def retry_job(job_id, auto=None, defer=0):
    old = get(job_id)
    if old['status'] not in ['failed', 'timed_out', 'cancelled']:
        raise ValueError('Only failed, timed-out or cancelled jobs can be retried')
    if old.get('retried_by'):
        raise ValueError('This job was already retried')
    fresh = {k: v for k, v in old.items() if k not in ['id', 'status', 'events', 'variant_id', 'key', 'retried_by']}
    j = dict(
        fresh,
        id=uid(),
        status='queued',
        events=[dict(time=time.time(), message=f'Automatic retry: attempt {auto[0]} of {auto[1]}')] if auto else [],
        created_at=time.time(),
        key=None,
        retry_of=old['id'],
        attempt=int(old.get('attempt', 1)) + 1,
        auto_retry=bool(auto),
    )
    snapshot_references(j, core.STORE / 'jobs' / old['id'] / 'references')
    old['retried_by'] = j['id']
    save('job', old)
    save('job', j)
    (threading.Timer(defer, enqueue, [j]).start() if defer else enqueue(j))
    return j
