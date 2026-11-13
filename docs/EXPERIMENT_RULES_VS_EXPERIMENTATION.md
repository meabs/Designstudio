# Do the rules stop experimentation? A real-agent experiment

**Scenario (deliberately outlandish):** *Baba Yaga Estates*, a mortgage application for a hut that walks on chicken legs. Applicants are folk-tale characters, the hut relocates without notice, and the first step must offer three equal-weight paths ("Fixed foundation", "Roaming rate", "Ask the hut") in a theatrical, illustrated voice.
The seeded guidelines say the opposite: calm and neutral, no humour or illustration, one primary action per screen (`CTA-001`, deterministic), plus `TONE-001` and `VISUAL-001` as designer-review rules.

Same brief, same two real agents (Claude Code, Codex, both inside the sandbox), same reference images, three rule regimes. Reproduce with `tests/scenario_hut.py` against a running server.

| Condition | Guidance in force |
|---|---|
| **S** strict | Original prose and rules |
| **O** overrides only | Job-scope overrides of `CTA-001` (max 3), `TONE-001`, `VISUAL-001`; DESIGN.md prose unchanged |
| **E** full experiment | Overrides, plus prose rewritten as an experiment brief and experimental tokens |

## Results

| Cond | Agent | Primary actions per screen | Three doors | Illustration elements | Look |
|---|---|---|---|---|---|
| S | Claude | 1 / 1 / 1 | as radio list | 0 | neutral form, no hut |
| S | Codex | 1 / 1 / 1 | as radio list | 3 | neutral form, no hut |
| O | Claude | 3 / 1 / 1 | three equal cards | 3 | neutral palette, plain tone (prose won) |
| O | Codex | 3 / 1 / 1 | three equal cards | 12 | warmer, playful copy (override won) |
| E | Claude | 3 / 1 / 1 | three equal doors | 15 | full folk-tale, hut illustration |
| E | Codex | 3 / 1 / 1 | three equal doors | 11 | full folk-tale, ornate, hut illustration |

Screenshots: `docs/screenshots/exp-1-eligibility-by-condition.png`, `exp-2-form-by-condition.png`, `exp-3-clickthrough.png`.

## Verdict: yes, rules suppress experimentation, in four ways

1. **Agents treat rules as hard constraints over the brief.** Under S both agents discarded the core creative ask. Claude's own report: *"I ignored the woodcut mood, the 'hut speaks in its own voice' note and the three-equal-doors note. They conflict with the tone, visual and primary-action rules"* and *"Reference images: I did not view them."* Codex "omitted" the conflicting reference directions. Their domain problem-solving stayed good (both added last-known-location and move-notification questions); what vanished was personality and visual risk.
2. **The studio does not surface that trade-off.** Those statements live only in `runner.log`. The deterministic checks said all green, because a design that obeys the rules *and abandons the brief* passes. There is no brief-fidelity signal.
3. **Overriding rules is not enough.** Prose in DESIGN.md is not layered. In O the three-doors override took effect for both agents, but tone and visuals were decided by the prose, and the two agents resolved the prose/rule conflict in opposite ways. Real experimentation needed rewriting the authoritative prose (E).
4. **There is no per-job override.** "Job" scope is just a label inside the single project-wide context. Running an experiment means editing guidance that governs every future job in the project.

Nothing in the tool *blocks* an experiment: rules never gate generation, and a violation only shows as a failed deterministic check. The suppression happens because agents obey the guidance the studio sends them, which is working as designed and exactly why an experiment mode is needed.

## Recommended changes
- **Per-job experiment overrides** in the Generate dialog: extra or replacement rules plus a short "for this run only" prose block, layered above DESIGN.md, recorded in that job's snapshot hash and never saved into the project guidance.
- **Surface the agent's own deviations** ("what I did not follow and why") on the variant as a clearly labelled self-report, with a designer-review item when it names a brief or reference it ignored.
- **Conflict preview before generation:** warn when the brief or selected references mention things the active rules forbid (three equal actions vs one-primary-action, illustration vs no-illustration).
- **Make reference images explicit:** record whether the agent says it viewed them (Claude did not under S).

## Other findings from running it for real
- Research output from a real agent crashed the studio (extra top-level keys), pre-selected findings and labelled sources it invented as "supplied by user". Fixed: agent output is sanitized and the studio assigns provenance itself; "verified" is never accepted.
- The player's iframe sandbox lacked `allow-forms`, so agent-built forms (JS `submit` handler) could not advance. Fixed, with a regression test; the bundle CSP still forbids real form posts.
- One Codex run timed out at the 300 s default; an automatic retry setting would have recovered it unattended.
