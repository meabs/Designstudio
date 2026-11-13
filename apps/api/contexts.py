"""Projects and versioned design context (DESIGN.md, tokens, rules) with scope precedence."""

import time
from core import allof, digest, get, save, uid

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


def context(project, data):
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
    history = sorted([c for c in allof('context') if c['project_id'] == project], key=lambda c: c['created_at'])
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
        and get(project).get('context_id') == previous['id']
    ):
        return previous
    save('context', x)
    p = get(project)
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
        for label, style in [('Studio A', 'a'), ('Studio B', 'b')]:
            save('runner', dict(id=uid(), name=label, type='fixture', style=style))
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
