"""Boards, blind A/B, job launch, per-job context overrides and the conflict preview."""

import copy, random, time, re
from core import allof, canonical, digest, get, save, uid
from jobs import enqueue
from contexts import current_context, profiles_of
from references import resolve_references, snapshot_references
import core


def hidden_job_file(path):
    # While a board is blind, files that reveal the runner (envelope, runner log, raw agent output) are withheld; the task text and references are identical for every runner.
    m = re.match(r'/assets/jobs/([0-9a-f]+)/(.*)$', path)
    if not m:
        return False
    try:
        j = get(m.group(1))
        b = get(j['board_id']) if j.get('board_id') else None
    except ValueError:
        return False
    return bool(
        b
        and b.get('blind')
        and not b.get('revealed')
        and not (m.group(2) == 'TASK.md' or m.group(2).startswith('references/'))
    )


# ---- blind A/B comparison: identities are withheld by the server until the designer chooses or reveals ----
LETTERS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'


def assign_labels(board_id, count):
    used = {v.get('blind_label') for v in allof('variant') if v['board_id'] == board_id} | {
        j.get('blind_label') for j in allof('job') if j.get('board_id') == board_id
    }
    pool = [c for c in LETTERS if c not in used]
    random.SystemRandom().shuffle(pool)
    return pool[:count]


def label_lineage(board_id):
    vs = [v for v in allof('variant') if v['board_id'] == board_id]
    byid = {v['id']: v for v in vs}
    for v in sorted(
        [v for v in vs if not v.get('parent_id') and not v.get('blind_label') and v.get('kind') != 'mix'],
        key=lambda x: x['id'],
    ):
        v['blind_label'] = assign_labels(board_id, 1)[0]
        save('variant', v)
    for v in sorted(vs, key=lambda x: x['created_at']):
        if v.get('parent_id') and not v.get('blind_label'):
            root = v
            while root.get('parent_id') and root['parent_id'] in byid:
                root = byid[root['parent_id']]
            if root.get('blind_label'):
                v['blind_label'] = root['blind_label']
                save('variant', v)


def set_blind(board_id, on):
    b = get(board_id)
    if on and b.get('revealed'):
        raise ValueError('Identities were already revealed for this board')
    b['blind'] = bool(on)
    save('board', b)
    if on:
        label_lineage(board_id)
    return get(board_id)


def blind_choice(board_id, variant_id=None, reason=''):
    b = get(board_id)
    if not b.get('blind') or b.get('revealed'):
        raise ValueError('This board is not in blind mode')
    choice = None
    if variant_id:
        v = get(variant_id)
        if v['board_id'] != board_id:
            raise ValueError('Choose a variation from this board')
        choice = dict(
            variant_id=v['id'],
            label=v.get('blind_label'),
            runner_name=v['runner_name'],
            reason=str(reason)[:500],
            at=time.time(),
        )
    b['revealed'] = True
    b['blind_choice'] = choice
    return save('board', b)


def mask_state(state):
    hidden = {b['id'] for b in state['board'] if b.get('blind') and not b.get('revealed')}
    if not hidden:
        return state
    for v in state['variant']:
        if v['board_id'] in hidden:
            v['runner_name'] = 'Option ' + (v.get('blind_label') or '?') if v.get('kind') != 'mix' else v['runner_name']
            v['runner_id'] = None
            v.pop('style', None)
            v.pop('applied_tokens', None)
            v.pop('rule_breaks', None)
            for dr in v.get('doc_reviews', []):
                dr['runner_name'] = 'Hidden (blind)'
            for c in v.get('validation', []):
                if c['check'] == 'Fixture guidance support':
                    c.update(
                        check='Guidance support',
                        evidence='Some prose guidance may not be applied automatically; needs designer review.',
                    )
    for j in state['job']:
        if j.get('board_id') in hidden:
            j['runner_name'] = 'Hidden (blind)'
            j['runner_id'] = None
            j.pop('agent_report', None)
            j.pop('usage', None)
            j.pop('angle', None)
    for b in state['board']:
        if b['id'] in hidden:
            b.pop('decisions', None)
    for p in state['prototype']:
        if p.get('board_id') in hidden:
            p['runner_name'] = 'Hidden (blind)'
    return state


MAX_SCREENS = 12
# Board targets: what the screens are designed for. Legacy boards (no target) keep the original 720x960 frame.
TARGETS = {
    'website': dict(label='Website', frames={'d': (1440, 900)}),
    'mobile': dict(label='Mobile app', frames={'d': (390, 844)}),
    'both': dict(label='Website and mobile app', frames={'d': (1440, 900), 'm': (390, 844)}),
}
TARGET_BRIEF = {
    'website': 'TARGET: a desktop website. Design for a 1440px-wide viewport, with sensible behaviour down to tablet width. Use real page structure (header, navigation, sections, footer where relevant).',
    'mobile': 'TARGET: a mobile app. Design for a 390px-wide phone viewport (390x844): include <meta name="viewport" content="width=device-width, initial-scale=1">, no horizontal scrolling, touch targets of at least 44px, thumb-reachable primary actions, no hover-only interactions, and app-style navigation (tab bar, back button, sheets) rather than a website header and footer.',
    'both': 'TARGET: one responsive design that must work as a desktop website (1440px wide) AND as a mobile app screen (390px wide). Use CSS media queries so each screen adapts: a full layout on desktop, and on phones a single column with touch targets of at least 44px, no horizontal scrolling and app-style navigation. Include <meta name="viewport" content="width=device-width, initial-scale=1">. The studio will check both widths.',
}


def frame_of(board, view='d'):
    t = (board or {}).get('target')
    if t not in TARGETS:
        return (720, 960)  # legacy boards
    return TARGETS[t]['frames'].get(view) or TARGETS[t]['frames']['d']


def create_board(data):
    project_id = data['project_id']
    get(project_id)
    screens = data.get('screens', [])
    if (
        not isinstance(screens, list)
        or not 2 <= len(screens) <= MAX_SCREENS
        or any(not isinstance(n, str) or not n.strip() for n in screens)
    ):
        raise ValueError(f'Choose 2–{MAX_SCREENS} named screens')
    target = data.get('target') or 'website'
    if target not in TARGETS:
        raise ValueError('Target must be website, mobile or both')
    board = dict(
        id=uid(),
        project_id=project_id,
        title=data.get('title', 'Untitled board'),
        brief=data.get('brief', ''),
        screens=screens,
        target=target,
    )
    if 'research_id' in data:
        research = get(data['research_id'])
        if research.get('project_id') != project_id or 'findings' not in research:
            raise ValueError('Research must belong to this project')
        ids = data.get('finding_ids', [])
        findings = [f for f in research['findings'] if f['id'] in ids]
        if not findings or set(ids) != {f['id'] for f in findings}:
            raise ValueError('Choose valid research findings')
        board.update(
            research_id=research['id'],
            research_brief=research['brief'],
            research_findings=findings,
            research_sources=research.get('sources', []),
        )
    return save('board', board)


def job_context(ctx, ov):
    # Per-run overrides: a copy of the saved context with extra/replacement/suspended rules and run-only prose. Never saved to the project.
    ov = ov if isinstance(ov, dict) else {}
    rules = [
        dict(
            id=str(r.get('id', '')).strip(),
            description=str(r.get('description', '')).strip(),
            scope='job',
            severity=r.get('severity', 'error'),
            verification=r.get('verification', 'advisory'),
            **{k: r[k] for k in ('check', 'parameters') if k in r},
            justification=str(r.get('justification', '')).strip() or 'Run-only override',
            enabled=True,
        )
        for r in ov.get('rules', [])
        if isinstance(r, dict) and str(r.get('id', '')).strip() and str(r.get('description', '')).strip()
    ]
    suspend = [str(i) for i in ov.get('suspend', []) if str(i).strip()]
    prose = str(ov.get('prose', '')).strip()
    free = ov.get('free') if ov.get('free') in ('rules', 'open') else ''
    if not (rules or suspend or prose or free):
        return ctx
    c = copy.deepcopy(ctx)
    eff = {r['id']: r for r in c['effective_rules']}
    free_log = []
    if free:
        # Free exploration: nothing is enforced or checked. 'rules' keeps DESIGN.md prose and tokens as inspiration; 'open' drops them too.
        for i in list(eff):
            free_log.append({'id': i, 'superseded': eff.pop(i), 'winner': None, 'justification': 'Free exploration run'})
        if free == 'open':
            c['markdown'] = '(Free exploration: the project guidelines are intentionally not applied to this run.)'
            c['tokens'] = {}
    extra = []
    for r in rules:
        if r['id'] in eff:
            extra.append({'id': r['id'], 'superseded': eff[r['id']], 'winner': r, 'justification': r['justification']})
        eff[r['id']] = r
    for i in suspend:
        if i in eff:
            extra.append(
                {'id': i, 'superseded': eff.pop(i), 'winner': None, 'justification': 'Suspended for this run only'}
            )
    c['effective_rules'] = list(eff.values())
    c['overrides'] = c.get('overrides', []) + free_log + extra
    c['run_overrides'] = dict(rules=rules, suspend=suspend, prose=prose, free=free)
    c['hash'] = digest(
        {
            'markdown': c['markdown'],
            'tokens': c['tokens'],
            'effective_rules': c['effective_rules'],
            'run_prose': prose,
            'free': free,
        }
    )
    return c


ANGLES = [
    'calm and reassuring: generous whitespace, quiet colour, minimal chrome, plain gentle language',
    'bold and confident: a strong type scale, high contrast, decisive colour, short punchy copy',
    'dense and efficient: information-rich, compact, scannable, built for someone who wants it done fast',
    'warm and human: friendly voice, rounded shapes, a little personality and illustration',
    'editorial and content-led: strong hierarchy, long-form clarity, the explanation is the design',
    'playful and surprising: an unexpected layout or interaction that still gets the job done',
]
def spread_offset(board_id):
    # Rotate the directions each round so a second spread run explores new angles.
    return sum(1 for j in allof('job') if j.get('board_id') == board_id and j.get('angle'))


STATES_NOTE = 'Add the missing realistic states to this screen: an empty state, a loading state, an error/validation state, and a long-content state (long names, long numbers, translated-length text). Keep the existing default design and make each state reachable from the screen (for example a visible state switcher or links) and listed in the manifest states array.'

CONFLICT_PATTERNS = [
    (
        'actions',
        re.compile(
            r"\b(?:two|three|four|five|[2-5])\b[^.\n]{0,40}\b(?:equal|same|co-?equal|competing)\b[^.\n]{0,30}\b(?:actions?|buttons?|ctas?|doors?|paths?|choices?|options?)\b|no (?:single )?primary (?:button|action)",
            re.I,
        ),
        re.compile(r"(?:one|single|1|max(?:imum)?)\b[^.\n]{0,25}primary|primary[^.\n]{0,20}(?:one|single|only)", re.I),
        'asks for several equal actions',
    ),
    (
        'imagery',
        re.compile(r"illustrat|woodcut|hand[- ]?drawn|mascot|cartoon|whimsical|decorative|texture|photograph", re.I),
        re.compile(r"illustrat|decorat|imagery|stock|photograph|ornament|visual", re.I),
        'asks for expressive imagery',
    ),
    (
        'voice',
        re.compile(
            r"in (?:its|their|a) own voice|playful|quirky|character voice|speaks as|first[- ]person|humou?r|jokes?|riddle",
            re.I,
        ),
        re.compile(r"tone|voice|neutral|professional|humou?r|whims", re.I),
        'asks for a distinctive voice',
    ),
    (
        'motion',
        re.compile(r"animat|parallax|motion|video|autoplay|carousel", re.I),
        re.compile(r"animat|motion|static|reduce|carousel", re.I),
        'asks for motion',
    ),
    (
        'urgency',
        re.compile(r"countdown|urgen|scarcity|limited time|only \d+ left|hurry", re.I),
        re.compile(r"urgen|pressure|dark pattern|manipulat|transparen|trust", re.I),
        'asks for urgency',
    ),
]


QUESTION_RE = re.compile(r"^\s*(what|how|why|who|which|when|where|will|can|should|could|is|are|does|do)\b", re.I)


def question_shaped(brief):
    b = (brief or '').strip()
    return bool(b) and (b.endswith('?') or bool(QUESTION_RE.match(b))) and not re.search(r'\b(design|create|build|make|draft|prototype)\b', b, re.I)


def conflict_preview(project_id, brief, overrides=None, reference_ids=None, profile_id=None):
    # Advisory only: keyword heuristics comparing the brief, run-only prose and selected reference notes with the active rules. It cannot read images.
    ctx = job_context(current_context(project_id, profile_id), overrides)
    refs = resolve_references(
        project_id, [i for i in (reference_ids or []) if any(r['id'] == i for r in allof('reference'))]
    )
    sources = [('your brief', brief or '')] + [
        ('reference ' + r['name'], r.get('note', '') + ' ' + r['name']) for r in refs
    ]
    if ctx.get('run_overrides', {}).get('prose'):
        sources.append(('run-only prose (applies, but check it)', ctx['run_overrides']['prose']))
    out = []
    if question_shaped(brief):
        out.append(
            dict(
                id='BRIEF',
                rule='A brief should say what to design',
                severity='warning',
                overridden=False,
                topic='brief',
                message='Your brief reads like a question, not an instruction (\u201c' + (brief or '').strip()[:60] + '\u201d).',
                action='Agents may answer it with a written summary instead of designing screens. Rewrite it as what to design, e.g. \u201cDesign a 3-step application journey that ...\u201d.',
            )
        )
    run_ids = {x['id'] for x in ctx.get('run_overrides', {}).get('rules', [])}
    for key, ask, rule_re, label in CONFLICT_PATTERNS:
        hits = [(w, m[0]) for w, t in sources if (m := ask.search(t))]
        if not hits:
            continue
        for r in ctx['effective_rules']:
            if rule_re.search(r['id'] + ' ' + r['description']) and not any(o['id'] == r['id'] for o in out):
                out.append(
                    dict(
                        id=r['id'],
                        rule=r['description'],
                        severity=r.get('severity', 'error'),
                        overridden=r['id'] in run_ids,
                        topic=key,
                        message=f"{' and '.join(sorted({w for w,_ in hits}))} {label} (\u201c{hits[0][1][:60]}\u201d), but {r['id']} says \u201c{r['description'][:90]}\u201d.",
                        action=(
                            'Already overridden for this run'
                            if r['id'] in run_ids
                            else 'Agents treat rules as hard constraints and usually follow the rule, not the brief. Override it for this run, or accept the trade-off.'
                        ),
                    )
                )
    return out


def launch(data, kind, project_id):
    if kind == 'research' and not str(data.get('brief', '')).strip():
        raise ValueError('Enter a research question first')
    p = get(project_id)
    # Guidelines profile: a revision keeps the profile its parent used; otherwise the requested one, else the project's default.
    parent_ctx = get(get(data['parent_id'])['context_id']) if data.get('parent_id') else None
    asked = data.get('profile_id') or (data.get('profile_ids') or [None])[0]
    inherited = (parent_ctx or {}).get('profile_id', 'main') if parent_ctx else None
    if not asked and inherited and not any(x['id'] == inherited for x in profiles_of(p)):
        inherited = None  # the parent's profile was deleted: revise under the default profile
    ctx = current_context(project_id, asked or inherited)
    key = data.get('idempotency_key')
    parent_job = (
        next((j for j in allof('job') if j.get('variant_id') == data.get('parent_id')), None)
        if data.get('parent_id')
        else None
    )
    ov = data['overrides'] if 'overrides' in data else ((parent_job or {}).get('context', {}).get('run_overrides'))
    ctx = job_context(ctx, ov)
    if key:
        existing = [j for j in allof('job') if j.get('key') == key and j['project_id'] == project_id]
        if existing:
            return existing

    if (
        kind == 'revise_board'
        and data.get('parent_id')
        and not data.get('runner_ids')
        and not get(data['parent_id']).get('runner_id')
    ):
        raise ValueError('Choose a runner to revise a mixed version')
    runners = data.get('runner_ids') or (
        [get(data['parent_id'])['runner_id']]
        if kind == 'revise_board' and data.get('parent_id')
        else [next(r['id'] for r in allof('runner') if r.get('enabled', True))]
    )
    jobs = []
    enabled = {r['id'] for r in allof('runner') if r.get('enabled', True)}
    if any(r not in enabled for r in runners):
        raise ValueError('Runner is disabled or no longer exists')
    annotations = data.get('annotations', [])
    if kind == 'revise_board' and data.get('states'):
        # Add realistic states to every screen: virtual feedback, not stored as pins.
        pv = get(data['parent_id'])
        annotations = [
            dict(id='states-' + str(s['id']), variant_id=pv['id'], screen=str(s['id']), comment=STATES_NOTE, virtual=True)
            for s in pv['manifest']['screens']
        ]
    elif kind == 'revise_board':
        ids = data.get('annotation_ids', [])
        annotations = [get(i) for i in ids]
        if not annotations or any(
            a['variant_id'] != data.get('parent_id') or a.get('status', 'open') != 'open' for a in annotations
        ):
            raise ValueError('Select open feedback pins on the version being revised')
    board_for_refs = get(data['board_id']) if data.get('board_id') else None
    ref_ids = data['reference_ids'] if 'reference_ids' in data else (board_for_refs or {}).get('reference_ids', [])
    references = resolve_references(project_id, [i for i in ref_ids if any(r['id'] == i for r in allof('reference'))])
    scope = {}
    if kind == 'revise_board':
        by_screen = {}
        for a in annotations:
            e = by_screen.setdefault(str(a['screen']), {'elements': [], 'anchored': True})
            if a.get('element_id'):
                e['elements'].append(a['element_id'])
            else:
                e['anchored'] = False
        region = data.get('scope_mode', 'region') == 'region'
        scope = {
            sid: (
                {'mode': 'region', 'elements': sorted(set(e['elements']))}
                if region and e['anchored'] and e['elements']
                else {'mode': 'screen'}
            )
            for sid, e in by_screen.items()
        }
    supplied = [dict(x, id=x.get('id') or f'user_source_{n+1}') for n, x in enumerate(data.get('sources', []))]
    common = dict(
        scope=scope,
        references=references,
        brief=data.get('brief', ''),
        board_id=data.get('board_id'),
        parent_id=data.get('parent_id'),
        annotations=annotations,
        sources=supplied,
        findings=[
            f for r in allof('research') if r['project_id'] == project_id for f in r['findings'] if f.get('selected')
        ],
        context=ctx,
    )
    if common['board_id']:
        common['board'] = get(common['board_id'])
        if common['board']['project_id'] != project_id:
            raise ValueError('Board must belong to this project')
        if 'research_findings' in common['board']:
            common['findings'] = common['board']['research_findings']
            common['sources'] = common['board'].get('research_sources', [])
    if common['parent_id']:
        common['parent_package'] = str(core.STORE / 'variants' / common['parent_id'])
    shared = digest(common)
    for runner_id in runners:
        blind_labels = (
            assign_labels(common['board_id'], 1)
            if kind == 'generate_board' and board_for_refs and board_for_refs.get('blind')
            else []
        )
        angle = ''
        if data.get('spread') and kind == 'generate_board':
            off = data['spread_offset'] if 'spread_offset' in data else spread_offset(data.get('board_id'))
            angle = ANGLES[(runners.index(runner_id) + off) % len(ANGLES)]
        j = dict(
            id=uid(),
            project_id=project_id,
            type=kind,
            runner_id=runner_id,
            runner_name=get(runner_id).get('name', ''),
            status='queued',
            events=[],
            created_at=time.time(),
            input_hash=digest([shared, angle]) if angle else shared,
            angle=angle,
            key=key,
            **common,
        )
        scope_text = (
            (
                '\nRevision scope (strict): '
                + '; '.join(
                    (
                        f'screen {sid}: change ONLY the element(s) with data-design-id in {sc["elements"]} and their descendants, keep every other byte of that file identical'
                        if sc['mode'] == 'region'
                        else f'screen {sid}: you may change the whole screen'
                    )
                    for sid, sc in scope.items()
                )
                + '; all other screens must be copied unchanged.'
            )
            if scope
            else ''
        )
        refs_text = (
            (
                '\nReference images (designer-supplied visual context; files in references/). Treat them as inspiration or constraints, not verified brand rules; the guidelines above take precedence unless a note says otherwise:\n'
                + '\n'.join(
                    f'- references/{r["file"]} · {r["name"]}' + (f' · note: {r["note"]}' if r['note'] else '')
                    for r in references
                )
            )
            if references
            else ''
        )
        run_text = (
            (
                '\nRUN-ONLY EXPERIMENT BRIEF FROM THE DESIGNER (this run only; where it conflicts with DESIGN.md prose or the rules below, THIS TAKES PRECEDENCE, and rules listed here already replace or suspend the saved ones):\n'
                + ctx['run_overrides']['prose']
            )
            if ctx.get('run_overrides', {}).get('prose')
            else ''
        )
        if j.get('angle'):
            run_text += '\nDIRECTION FOR THIS VARIANT (the designer wants the runners to diverge; commit to this angle and make it clearly different from a conventional take): ' + j['angle']
        free_mode = ctx.get('run_overrides', {}).get('free')
        if free_mode:
            run_text += (
                '\nFREE EXPLORATION RUN: the designer has deliberately switched the rules off. Do not try to satisfy any design rules or checks; explore boldly and let the brief lead.'
                + (' The saved guidelines and tokens are inspiration only.' if free_mode == 'rules' else ' No project guidelines or tokens apply at all.')
            )
        if blind_labels:
            j['blind_label'] = blind_labels[0]
        target_text = ('\n' + TARGET_BRIEF[common['board']['target']]) if common.get('board', {}).get('target') in TARGET_BRIEF else ''
        j['instruction'] = (
            f'Task: {kind}. Output contract: static variant-package/1.0 or research.json.\nBrief: {common["brief"]}\nScreens: {common.get("board",{}).get("screens",[])}{target_text}\nDESIGN.md:\n{ctx["markdown"]}{run_text}\nTokens: {canonical(ctx["tokens"])}\nRules: {canonical(ctx["effective_rules"])}\nSnapshot SHA256: {ctx["hash"]}\nFindings (unverified unless explicitly sourced): {canonical(common["findings"])}\nSupplied sources (preserve provenance): {canonical(common["sources"])}\nAnnotations: {canonical(common["annotations"])}{refs_text}{scope_text}\nYou are running non-interactively: do not ask questions, do not reply with only a plan or summary, and do not wait for confirmation. The task is only complete when the files exist. Only create these file types: .html .css .js .json .png .jpg .svg .woff .woff2 (plus optional .md/.txt notes). Write files to output/. Research output: research.json with a findings array (id,title,detail,confidence,source_ids) and an optional limitations array. Cite supplied sources only by their id; do not invent sources or URLs and do not label anything verified (the studio assigns provenance labels itself). State plainly what you could not check. Variant output (a generate or revise task): the screens must be a working product interface for the audience in the brief (headings, navigation, forms, inputs, buttons, states). Never write an article, report or summary of research findings as a screen; findings are inputs that shape what the screens contain. If the brief reads like a question, treat it as the topic to design an interface for. Variant output: manifest.json with schema_version=1.0, kind=clickthrough-static, board_id, start_screen_id=0 (string), screens array with id as zero-based string, title, file=screens/<id>.html, states array; edges with from,to,trigger. All requested screens must exist. Use data-role=primary-action on primary controls and data-design-id on annotation targets. For a revision, output/ ALREADY CONTAINS a full copy of the parent version: edit those files in place and leave everything not covered by the revision scope untouched. No external dependencies. Enumerate files and any guidelines you could not honor; self-report is not validation.'
        )
        save('job', j)
        jobs.append(j)
        snapshot_references(j, core.STORE / 'projects' / project_id / 'references')
        enqueue(j)
    if kind == 'generate_board' and board_for_refs is not None and 'reference_ids' in data:
        board_for_refs['reference_ids'] = [r['id'] for r in references]
        save('board', board_for_refs)
    for a in annotations:
        if kind == 'revise_board' and not a.get('virtual'):
            a = get(a['id'])
            a.update(status='applied', job_ids=[j['id'] for j in jobs])
            save('annotation', a)
    return jobs
