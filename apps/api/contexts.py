"""Projects and versioned design context (DESIGN.md, tokens, rules) with scope precedence."""

import os, time
from core import LOCK, allof, digest, get, save, uid

RULES = [
    dict(
        id='CTA-001',
        description='One primary action per screen',
        scope='project',
        severity='error',
        verification='deterministic',
        check='primary_action_count',
        parameters={'max': 1},
        enabled=True,
    ),
    dict(
        id='COMPONENT-001',
        description='Use the supplied component tokens',
        scope='workspace',
        severity='warning',
        verification='human_review',
        enabled=True,
    ),
    dict(
        id='COPY-001',
        description='Explain why sensitive details are requested',
        scope='project',
        severity='warning',
        verification='human_review',
        enabled=True,
    ),
]
GUIDE = '# Design guidelines\n\nUse a neutral financial-services style.\nUse clear titles and short descriptive copy.\nExplain why sensitive details are requested.\nOne obvious primary action per screen.\n'
TOKENS = {
    'accent': '#52614c',
    'ink': '#202b24',
    'background': '#f7f8f5',
    'radius': '8px',
    'spacing': '24px',
    'font': 'system-ui, sans-serif',
}


# ---- guideline profiles: several named, independently versioned guideline sets per project ----
def profiles_of(p):
    # Legacy projects have one implicit profile. `context_id` always mirrors the default profile's current version.
    return p.get('profiles') or [dict(id='main', name='Main', context_id=p.get('context_id'), created_at=p.get('created_at', 0))]


def active_profile_id(p):
    ids = [x['id'] for x in profiles_of(p)]
    return p.get('profile_id') if p.get('profile_id') in ids else ids[0]


def find_profile(p, profile_id=None):
    pid = profile_id or active_profile_id(p)
    prof = next((x for x in profiles_of(p) if x['id'] == pid), None)
    if not prof:
        raise ValueError('Unknown guidelines profile')
    return prof


def current_context(project_id, profile_id=None):
    p = get(project_id)
    ctx = get(find_profile(p, profile_id)['context_id'])
    return dict(ctx, profile_id=ctx.get('profile_id', 'main'), profile_name=find_profile(p, profile_id)['name'])


def _profile_name(name, p, keep=None):
    name = ' '.join(str(name or '').split())
    if not 1 <= len(name) <= 40:
        raise ValueError('Give the profile a name of 1 to 40 characters')
    if any(x['name'].lower() == name.lower() and x['id'] != keep for x in profiles_of(p)):
        raise ValueError('A profile with that name already exists')
    return name


def profile_create(project_id, name, copy_from=None):
    # A new profile starts as a copy of another profile's current version (or the defaults), with its own version history.
    p = get(project_id)
    name = _profile_name(name, p)
    src = get(find_profile(p, copy_from)['context_id']) if copy_from != 'blank' else None
    pid = uid()[:8]
    with LOCK:
        p = get(project_id)
        profs = list(profiles_of(p)) + [dict(id=pid, name=name, context_id=None, created_at=time.time())]
        p['profiles'] = profs
        p.setdefault('profile_id', profs[0]['id'])
        save('project', p)
        data = dict(profile_id=pid)
        if src:
            data.update(
                markdown=src['markdown'], tokens=src['tokens'], rules=[{k: v for k, v in r.items() if k != 'version'} for r in src['rules']]
            )
        context(project_id, data)
    return get(project_id)


def profile_update(project_id, profile_id, name=None, make_default=False):
    with LOCK:
        p = get(project_id)
        profs = [dict(x) for x in profiles_of(p)]
        prof = next((x for x in profs if x['id'] == profile_id), None)
        if not prof:
            raise ValueError('Unknown guidelines profile')
        if name is not None:
            prof['name'] = _profile_name(name, p, keep=profile_id)
        p['profiles'] = profs
        if make_default:
            p['profile_id'] = profile_id
            p['context_id'] = prof['context_id']
        p.setdefault('profile_id', profs[0]['id'])
        return save('project', p)


def profile_delete(project_id, profile_id):
    # Only the profile entry goes; versions already used by jobs stay as history.
    with LOCK:
        p = get(project_id)
        profs = [x for x in profiles_of(p) if x['id'] != profile_id]
        if len(profs) == len(profiles_of(p)):
            raise ValueError('Unknown guidelines profile')
        if profile_id == active_profile_id(p):
            raise ValueError('This is the default profile. Make another profile the default first.')
        p['profiles'] = profs
        return save('project', p)


def context(project, data):
    p0 = get(project)
    profile_id = find_profile(p0, data.get('profile_id'))['id']
    tokens = data.get('tokens', TOKENS)
    if not isinstance(tokens, dict) or any(not isinstance(v, (str, int, float)) for v in tokens.values()):
        raise ValueError('Tokens must be a flat JSON object of scalar values')
    all_rules = data.get('rules', RULES)
    if not isinstance(all_rules, list) or any(
        not isinstance(r, dict) or not str(r.get('id', '')).strip() or not str(r.get('description', '')).strip()
        for r in all_rules
    ):
        raise ValueError('Every rule needs an ID and a description')
    if r_ids := [r['id'] for r in all_rules if r.get('scope', 'project') == 'project']:
        if len(r_ids) != len(set(r_ids)):
            raise ValueError('Duplicate rule IDs within the project scope')
    history = sorted(
        [c for c in allof('context') if c['project_id'] == project and c.get('profile_id', 'main') == profile_id],
        key=lambda c: c['created_at'],
    )
    previous = history[-1] if history else None
    prior = {r['id']: r for r in (previous or {}).get('rules', [])}
    versioned = []
    for r in all_rules:
        r = dict(r)
        old = prior.get(r['id'])
        core = lambda q: {k: v for k, v in q.items() if k != 'version'}
        r['version'] = 1 if not old else (old.get('version', 1) if core(old) == core(r) else old.get('version', 1) + 1)
        versioned.append(r)
    rules = {}
    overrides = []
    for scope in ['workspace', 'project', 'job']:
        for r in versioned:
            if r.get('scope', 'project') == scope and r.get('enabled', True):
                if r['id'] in rules:
                    overrides.append(
                        {
                            'id': r['id'],
                            'superseded': rules[r['id']],
                            'winner': r,
                            'justification': r.get('justification', 'More specific scope'),
                        }
                    )
                rules[r['id']] = r
    x = dict(
        id=uid(),
        project_id=project,
        profile_id=profile_id,
        version=len(history) + 1,
        parent_id=previous['id'] if previous else None,
        markdown=data.get('markdown', GUIDE),
        tokens=tokens,
        rules=versioned,
        effective_rules=list(rules.values()),
        overrides=overrides,
        created_at=time.time(),
    )
    x['hash'] = digest({k: x[k] for k in ['markdown', 'tokens', 'effective_rules']})
    x['content_key'] = digest(
        {
            'markdown': x['markdown'],
            'tokens': tokens,
            'rules': [{k: v for k, v in r.items() if k != 'version'} for r in versioned],
        }
    )
    if (
        previous
        and previous.get('content_key') == x['content_key']
        and find_profile(get(project), profile_id)['context_id'] == previous['id']
    ):
        return previous
    save('context', x)
    p = get(project)
    profs = [dict(q) for q in profiles_of(p)]
    next(q for q in profs if q['id'] == profile_id)['context_id'] = x['id']
    p['profiles'] = profs
    p.setdefault('profile_id', profs[0]['id'])
    if profile_id == active_profile_id(p):
        p['context_id'] = x['id']
    save('project', p)
    return x


def project(data):
    p = save(
        'project',
        dict(
            id=uid(),
            name=data.get('name', 'Untitled project'),
            description=data.get('description', ''),
            created_at=time.time(),
            archived=False,
        ),
    )
    context(p['id'], {})
    return get(p['id'])


def seed():
    if not allof('runner'):
        if os.environ.get('STUDIO_SEED_FIXTURES') == '1':
            # Tests and offline demos only: deterministic template runners. A normal install starts with your installed coding agents.
            for label, style in [('Studio A', 'a'), ('Studio B', 'b')]:
                save('runner', dict(id=uid(), name=label, type='fixture', style=style))
        else:
            from local_agents import configuration, discover

            for a in discover():
                if a['id'] in ('claude', 'codex', 'copilot') and a['supported']:
                    save('runner', dict(id=uid(), enabled=True, **configuration(a['id'], '')))
    if not allof('project'):
        p = project({'name': 'Credit Card Application', 'description': 'A clearer path to your next everyday card.'})
        save(
            'board',
            dict(
                id=uid(),
                project_id=p['id'],
                title='Application Journey',
                brief='Create a calm, transparent credit card application. Explain eligibility before asking for personal information.',
                screens=['Eligibility', 'Your details', 'Review'],
            ),
        )
