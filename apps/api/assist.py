"""Two small agent jobs that never change a design: draft guidelines from a company brief, and answer a question about one element.

Both stage their inputs inside the job folder, ask the agent for one JSON file, and keep the answer clearly labelled as an unverified agent opinion.
"""

import json, re, shutil, time
import core
from contexts import current_context
from core import digest, get, save, uid
from importer import token_name, token_value

RULE_ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9_-]{1,39}')


def _runner(runner_id):
    runner = get(runner_id)
    if not runner.get('enabled', True):
        raise ValueError('Runner is disabled or no longer exists')
    if runner['type'] != 'cli':
        raise ValueError('This needs a coding agent (Claude Code or Codex); template runners cannot do it')
    return runner


def _queue(j):
    from jobs import enqueue

    save('job', j)
    enqueue(j)
    return j


def launch_guidelines_draft(project_id, runner_id, brief):
    brief = str(brief or '').strip()
    if len(brief) < 20:
        raise ValueError('Describe the company, audience and feel in a few sentences first')
    if len(brief) > 6000:
        raise ValueError('Keep the description under 6,000 characters')
    runner = _runner(runner_id)
    j = dict(
        id=uid(),
        project_id=project_id,
        type='guidelines_draft',
        runner_id=runner_id,
        runner_name=runner.get('name', ''),
        status='queued',
        events=[],
        created_at=time.time(),
        context=current_context(project_id),
        references=[],
        brief=brief,
        input_hash=digest([project_id, brief]),
        instruction=(
            'Task: guidelines_draft. Turn the designer\'s description into a first draft of design guidelines they will review and edit.\n'
            'Write output/draft.json: {"markdown": "...", "tokens": {...}, "rules": [{"id": "CTA-001", "description": "...", "severity": "error|warning"}], "notes": ["..."]}.\n'
            '- markdown: a DESIGN.md (audience, feel, layout, typography, imagery, tone of voice, what to avoid). Concrete and specific, no filler. Do not invent facts about the company; where the description is silent, say so in notes instead.\n'
            '- tokens: a FLAT object of scalar values (for example ink, background, surface, accent, muted, radius, font, font-mono, spacing). Real CSS values. Choose colours with at least 4.5:1 text contrast.\n'
            '- rules: 4 to 10 testable rules, each one sentence, with a unique ID like AREA-001. Prefer rules a reviewer could check by looking at the screen.\n'
            '- notes: assumptions you made and things the designer should confirm.\n'
            'You are running non-interactively: do not ask questions. The task is complete only when output/draft.json exists.\n'
            'Designer\'s description:\n' + brief
        ),
    )
    (core.STORE / 'jobs' / j['id']).mkdir(parents=True, exist_ok=True)
    return _queue(j)


def finish_guidelines_draft(j, out):
    f = out / 'output' / 'draft.json'
    if not f.is_file():
        raise ValueError('The agent finished without writing output/draft.json. Open runner.log in the job history to see what it said.')
    try:
        raw = json.loads(f.read_text())
    except ValueError:
        raise ValueError('output/draft.json is not valid JSON')
    if not isinstance(raw, dict) or not str(raw.get('markdown', '')).strip():
        raise ValueError('output/draft.json needs a markdown field')
    tokens = {}
    for k, v in (raw.get('tokens') if isinstance(raw.get('tokens'), dict) else {}).items():
        name, val = token_name(k), token_value(v)
        if name and val is not None and len(tokens) < 40:
            tokens[name] = val
    rules, seen = [], set()
    for r in (raw.get('rules') if isinstance(raw.get('rules'), list) else [])[:20]:
        if not isinstance(r, dict) or not str(r.get('description', '')).strip():
            continue
        rid = str(r.get('id') or '').strip()
        if not RULE_ID.fullmatch(rid) or rid in seen:
            rid = f'RULE-{len(rules) + 1:03d}'
        seen.add(rid)
        rules.append(dict(id=rid, description=str(r['description']).strip()[:400], severity='error' if r.get('severity') == 'error' else 'warning'))
    notes = raw.get('notes') if isinstance(raw.get('notes'), list) else []
    j['draft'] = dict(
        markdown=str(raw['markdown']).strip()[:20000],
        tokens=tokens,
        rules=rules,
        notes=[str(n)[:400] for n in notes][:10],
        label='agent_draft',
        note='An agent’s first draft from your description. Nothing is saved until you review it and save the guidelines.',
    )


def launch_pin_ask(variant_id, screen, element_id, question, runner_id):
    question = ' '.join(str(question or '').split())
    if not 3 <= len(question) <= 500:
        raise ValueError('Ask a question of 3 to 500 characters')
    v = get(variant_id)
    sid = str(screen)
    if sid not in {s['id'] for s in v['manifest']['screens']}:
        raise ValueError('Choose a valid screen')
    runner = _runner(runner_id)
    jid = uid()
    out = core.STORE / 'jobs' / jid
    shutil.copytree(core.STORE / 'variants' / v['id'], out / 'package', ignore=shutil.ignore_patterns('thumbnails', 'changes.json'))
    ctx = get(v['context_id'])
    where = f'the element with data-design-id="{element_id}"' if element_id else 'the screen as a whole'
    j = dict(
        id=jid,
        project_id=v['project_id'],
        board_id=v['board_id'],
        type='pin_ask',
        target_variant_id=v['id'],
        screen=sid,
        element_id=str(element_id or ''),
        question=question,
        runner_id=runner_id,
        runner_name=runner.get('name', ''),
        status='queued',
        events=[],
        created_at=time.time(),
        context=ctx,
        references=[],
        input_hash=digest([v['id'], sid, element_id, question]),
        instruction=(
            'Task: pin_ask. Answer a designer\'s question about a finished screen. Do NOT change any design files.\n'
            f'package/ holds the screens. The question is about {where} on screen {sid} (package/screens/{sid}.html). Read the HTML and CSS.\n'
            'Write output/answer.json: {"answer": "plain answer in 1 to 4 sentences, quoting the actual values or markup you relied on", "suggested_change": "one concrete change if one is warranted, otherwise empty", "confidence": "high|medium|low"}.\n'
            'Judge from the files only. If static HTML cannot answer it, say so. Do not invent measurements.\n'
            'You are running non-interactively: do not ask questions. The task is complete only when output/answer.json exists.\n'
            'Design guidelines for context:\n' + str(ctx.get('markdown', ''))[:4000] + '\nQuestion: ' + question
        ),
    )
    return _queue(j)


def finish_pin_ask(j, out):
    f = out / 'output' / 'answer.json'
    if not f.is_file():
        raise ValueError('The agent finished without writing output/answer.json. Open runner.log in the job history to see what it said.')
    try:
        raw = json.loads(f.read_text())
    except ValueError:
        raise ValueError('output/answer.json is not valid JSON')
    if not isinstance(raw, dict) or not str(raw.get('answer', '')).strip():
        raise ValueError('output/answer.json needs an answer field')
    j['answer'] = dict(
        answer=str(raw['answer']).strip()[:1500],
        suggested_change=str(raw.get('suggested_change', '')).strip()[:600],
        confidence=raw.get('confidence') if raw.get('confidence') in ('high', 'medium', 'low') else 'low',
        label='agent_opinion',
        note='An agent’s reading of the HTML and CSS. Unverified.',
    )
