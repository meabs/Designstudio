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
