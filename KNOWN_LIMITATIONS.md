# Known limitations

## Implemented

Persistent projects, archive/rename/restore, context versions and checksums, token import, scoped rule merging, research selection and provenance labels, independent fixture/CLI configurations, variant screenshot boards, two-up comparison, coordinate pins, child revisions, approval, revision accept/revert, human-review sign-off, job cancel/retry, lineage history, runner management, click-through player (history, states, device framing) and ZIP export. Local agent discovery and model selection are implemented. Python domain/startup tests and JavaScript workflow tests cover core invariants.

## Remaining / unverified

- Share links: read-only and unguessable (128-bit token, optional expiry, revocable), served by a separate listener that exposes only prototype bundles. There is no TLS or user authentication, so anyone with a link can view it until it expires or is revoked; the listener binds `STUDIO_SHARE_HOST` (default all interfaces) and links are plain HTTP unless you put it behind your own HTTPS proxy.

- Reference images are sent as files. Claude Code read a test image correctly in the doctor check; other agents are untested, and the fixture runner cannot interpret images. Images are not scanned for content and EXIF data is kept as uploaded.

- Blind comparison hides identity in the UI, in API state and in job files (envelope, runner log and raw output return 403 until reveal). Visibly different designs, response timing and the studio's own on-disk database can still reveal the runner; it is a bias-reduction aid, not a security boundary.
- Mixed versions check structure, links and tokens, plus a heuristic cross-screen consistency check (primary font and dominant colours from CSS text). That check is always a review item: it is not a visual review. Mixing assumes screens keep the `N.html` naming the contract requires.
- Region scope relies on `data-design-id`. If an agent emits none, the studio adds `auto-<tag>-<n>` anchors and flags it for review. A change inside an identified element is attributed to that element, not to individual child nodes without ids; a pin on text outside any element can only revise the whole screen.
- Real-agent behaviour varies run to run. `apps/api/doctor.py` has passed its checks (baseline, guidance, references, region revision, mixing, sandbox) with Claude Code and Codex on this machine; other agents and models are untested. The browser workflow itself uses fixtures plus `/bin/sleep` and `/bin/false` stand-ins for cancel, timeout and failure handling.
- Agent confinement: environment allowlist plus, on Linux with a working bubblewrap, a filesystem sandbox (read-only system, home and studio storage hidden, only the job folder writable). The network stays open for model calls and the agent's own auth directory is writable, so a compromised agent could still misuse its own credentials. Codex's built-in sandbox cannot nest inside ours, so it is switched to full-access *only* while ours is on. No sandbox on macOS/Windows or when user namespaces are disabled; no container images. Retries are automatic only if you set a per-runner limit (0 by default).
- Validation checks manifest essentials, screen files, local links, primary-action instrumentation, unique targets and remote asset references. Full JSON Schema enforcement, CSS token-reference scanning, CSS/JS network analysis and hostile-artifact rejection remain incomplete. This is not a security sandbox for untrusted code.
- No OpenAPI; the action API differs from the full REST specification. Workspace and job rule scopes are stored inside a project's versioned context, not as shared workspace packs or separate per-job editors.
- Fixture research is synthetic. Fixture generation supports token values and a small vocabulary of explicit text/background/button colour directives; other prose needs a local coding agent. Fixture revisions reflect feedback but do not interpret arbitrary requests.
- Before/after highlights regions that changed (per identified element) but not pixel-level differences, and whole-screen changes made without anchors show only as a changed screen.
- The UI assumes zero-based screen IDs for custom runners. Flat token JSON only; no DTCG nesting. Some fixture copy is specific to the sample use case.
- Missing Chrome produces a screenshot warning and a text placeholder; there is no rendered fallback or thumbnail-retry control.
- Colour contrast was raised across muted text but has not been audited with an automated tool; keyboard navigation covers the main flows but has not had a screen-reader pass.

The full build specification acceptance checklist has not been formally certified. This repository is a working implementation to extend.
- Run-only overrides change what the agent is told, not what the studio checks beyond the rules you keep; a replaced rule is validated by its new wording only if it is deterministic. The agent self-report is parsed with regexes from free text, can miss or misread a line, and is unverified. The conflict preview is a keyword heuristic that cannot read reference images, so it has false positives and misses.
- POC scope: single user, single machine, no authentication on the studio port (protected only by loopback binding and the Host check). State polling still recomputes the full state on the server every 2 s (the ETag only saves transfer). The API is split into small modules (see README "Code layout"), but the entity store is still one generic SQLite table with no migrations, and the UI needs Node 20+ to build (running it does not). Backups are manual (`make backup`).


## Designer tools (audit, free runs, pairs)

- The audit is static: it parses the delivered HTML/CSS and never renders or runs it. Contrast is measured only from explicit colours in CSS (opacity, gradients, images and computed styles are not), and tap-target size only from declared px sizes. It is evidence for a reviewer, not WCAG or legal certification.
- Document criteria are literal: a quoted phrase must (or must not) appear in the visible text. Anything else is listed for human judgement. The optional agent reading of your documents is an unverified opinion from a coding agent that sees only static files; it can be wrong or overconfident and is never a sign-off.
- Rule-break logs use the project's current saved guidelines at generation time and the same deterministic checks as normal runs; most prose rules can only be listed for review.
- Rules-vs-free doubles agent runs and cost. Spread directions are keyed to runner order, so they are comparable between a pair but not between rounds.
- Style extraction lists hex colours, font stacks and px radii; it does not infer roles (accent vs background) or spacing scales.

- Guideline import is heuristic: it decides what is a rule from file names, headings and wording ("must", "never", checklists), so prose-only guidance is imported as text, not rules, and a stray "must" bullet may need unticking. It reads `.md`, `.json` and `.css` only (no Figma, no Word/PDF). Re-importing is manual; the studio does not watch the folder.

- Profiles are whole sets, not layers: a new profile is a copy, so later edits to Main don't flow into it. Running several profiles multiplies runs and cost by the number ticked. On a blind board the UI hides profile names, but the underlying API data still carries them.

- Template (fixture) runners produce generic sample screens: they show the brief as text but do not interpret it, so they prove the interface, not design quality. Judge the studio with a real coding agent on a real brief.
- Folder reads are limited to `STUDIO_FOLDER_ROOTS` (default: your home folder). Anything else must be supplied with the browser file chooser.

- Board targets shape the brief, the screenshot size and the checks; they do not make the output native. A mobile-app board is a phone-sized HTML mock-up: no native iOS or Android controls, gestures or real navigation stacks. A board is still a journey of up to 12 screens, not a whole site map or app.
- On a "both" board only the two named widths are screenshotted (no tablet). Changed regions come from an HTML diff that doesn't depend on width and are drawn in whichever view you are reviewing; mixed versions carry both screenshots across.

- Spread is now on by default for several agents, which means a default comparison is no longer like-for-like (each agent gets a different direction). Untick it when you need identical inputs.
- Merging a part of one design into another is an agent's rebuild, not a copy: expect the idea and content to carry over but not pixel-identical markup, and review the result. Drafted guidelines, pin answers and merges are agent output, never verified.
- A cut-off run is only kept when the manifest and every screen were written; the last polish may be missing.
- The developer hand-off is static HTML, CSS and JS. It does not generate a React or framework project.

- Direct editing covers text, inline-style overrides, resize handles, offsets (`position: relative` with left and top, never absolute or fixed), reordering, duplicate, delete, adding text, buttons and PNG/JPEG images, and copying an element from another screen, on elements that carry a `data-design-id` (the studio adds anchors when an agent emitted none). Only a fixed list of properties and a conservative value syntax are accepted; text can be edited only on elements with no child elements. There is no auto-layout authoring, no editing of stylesheet rules or classes, no SVG or other element kinds to add, and no shared components that update every use. An element copied from another screen keeps its inline styles but only gets stylesheet styling if the target screen has the same rules. Copies lose the primary-action role. Moves are among identified elements only. The preview frame runs without scripts, so script-driven screens may render differently while editing than in the live preview. Edits apply at every width. Undo is per screen. Drafts are kept in the browser and copied to the studio a moment after each change; if both have a draft, the newer one wins, and a draft is limited to about 6 MB (a few pictures).
- GitHub Copilot CLI support was checked against Copilot CLI 1.0.112 on Linux: one three-screen generation passed every validation check, and a sandboxed run could use the login from `gh`. It is not added automatically on first start (add it under Settings → Agents), it has no model list so the model ID is typed by hand, and only one real generation has been run, so expect run-to-run variation like any agent.
