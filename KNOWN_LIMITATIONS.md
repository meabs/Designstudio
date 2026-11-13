# Known limitations

## Implemented

Persistent projects, archive/rename/restore, context versions and checksums, token import, scoped rule merging, research selection and provenance labels, independent fixture/CLI configurations, variant screenshot boards, two-up comparison, coordinate pins, child revisions, approval, revision accept/revert, human-review sign-off, job cancel/retry, lineage history, runner management, click-through player (history, states, device framing) and ZIP export. Local agent discovery and model selection are implemented. Python domain/startup tests and JavaScript workflow tests cover core invariants.

## Remaining / unverified

- Reference images are sent as files. Claude Code read a test image correctly in the doctor check; other agents are untested, and the fixture runner cannot interpret images. Images are not scanned for content and EXIF data is kept as uploaded.

- Blind comparison hides identity in the UI and API state only; job folders and files on disk, and visibly different designs, can still reveal the runner.
- Mixed versions check structure, links and tokens but not visual or copy consistency across screens; that stays a designer-review item. Mixing assumes screens keep the `N.html` naming the contract requires.
- Region scope needs `data-design-id` on the target; pins without an anchor revise the whole screen. A change inside an identified element is attributed to that element's own markup, not to individual child nodes without ids.
- Real-agent behaviour varies run to run. `apps/api/doctor.py` has passed baseline, guidance-sensitivity and reference-image checks with Claude Code on this machine; other agents and models are untested. The browser workflow itself uses fixtures plus `/bin/sleep` and `/bin/false` stand-ins for cancel, timeout and failure handling.
- CLI isolation relies on each installed agent: only allowlisted environment variables are passed, but directories are not sandboxed against peer reads. No container isolation or automatic retry. Queued jobs survive a restart; jobs that were running when the server stopped are marked failed and can be retried.
- Validation checks manifest essentials, screen files, local links, primary-action instrumentation, unique targets and remote asset references. Full JSON Schema enforcement, CSS token-reference scanning, CSS/JS network analysis and hostile-artifact rejection remain incomplete. This is not a security sandbox for untrusted code.
- No OpenAPI; the action API differs from the full REST specification. Workspace and job rule scopes are stored inside a project's versioned context, not as shared workspace packs or separate per-job editors.
- Fixture research is synthetic. Fixture generation supports token values and a small vocabulary of explicit text/background/button colour directives; other prose needs a local coding agent. Fixture revisions reflect feedback but do not interpret arbitrary requests.
- Pin anchoring needs the generated HTML to expose `data-design-id`; otherwise only coordinates are kept. Before/after highlights whole changed screens (byte comparison), not regions.
- The UI assumes zero-based screen IDs for custom runners. Flat token JSON only; no DTCG nesting. Some fixture copy is specific to the sample use case.
- Missing Chrome produces a screenshot warning and a text placeholder; there is no rendered fallback or thumbnail-retry control.
- Colour contrast was raised across muted text but has not been audited with an automated tool; keyboard navigation covers the main flows but has not had a screen-reader pass.

The full build specification acceptance checklist has not been formally certified. This repository is a working implementation to extend.
