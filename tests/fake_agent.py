#!/usr/bin/env python3
"""Scripted stand-in for a coding agent, used only by the browser tests. Reads the task prompt (last argument), writes what that task expects."""
import json, sys
from pathlib import Path

task = sys.argv[-1]
out = Path('output'); out.mkdir(exist_ok=True)
if 'Task: guidelines_draft' in task:
    (out / 'draft.json').write_text(json.dumps(dict(markdown='# Relay Ops\n\nPrecise, technical, dark.', tokens={'ink': '#e8eef2', 'background': '#0b0f14', 'accent': '#4ade80'}, rules=[dict(id='CTA-001', description='One primary action per screen', severity='error'), dict(id='TRUST-001', description='State that a human can approve actions', severity='warning')], notes=['Assumed a dark theme'])))
elif 'Task: pin_ask' in task:
    (out / 'answer.json').write_text(json.dumps(dict(answer='The heading is 43px with a 1.12 line height.', suggested_change='Raise it to 52px.', confidence='high')))
# merge / revise tasks: output/ already holds a copy of the parent version, so leaving it untouched is a valid (no-op) revision.
