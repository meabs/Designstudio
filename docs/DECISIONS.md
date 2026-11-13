# Implementation decisions

- Use Python standard-library HTTP, SQLite and plain browser modules rather than React/FastAPI. This enables one-command startup without downloaded dependencies. The domain and runner contract remain independent of the UI.
- Store typed JSON entities in SQLite; immutable context versions, job envelopes and variant directories preserve history. Approval pins the exact variant; revisions create child directories.
- Run jobs in independent background threads and persist state/events. On restart interrupted jobs are marked failed rather than silently resumed. A durable worker queue and cancellation remain future work.
- Built-in fixture directions use actual standalone HTML and native relative navigation. Chrome captures screenshots; screenshot failures are reported as not assessable.
- Discover executables locally. Codex models come from its local cache, OpenCode models from its discovery command; other model IDs are manually entered. Do not invent a current model catalog or imply that cached models are accessible.
- Agent selectors configure safe argument arrays; no shell interpolation or permission-bypass flags. Existing local authentication belongs to the CLI, not the studio.
- Routes follow the design specification, while the initial HTTP mutation API uses concise action endpoints. The full specified REST API/OpenAPI is deferred.
- This implementation is intended for trusted local coding agents, not hostile artifact ingestion or multi-user hosting.

- Research now has in-page status, results and a direct board/generation handoff. Handoff pins finding content and provenance in the board; later global finding selection changes do not silently alter that board's generation/revision inputs.
- Fixture color guidance is deliberately restricted to explicit text/background/button directives. Applied values are recorded on the variation, the source context remains immutable, and a fixture-support warning stays in designer review.

- Research results previously shared an ID with their job, so the job's final save overwrote them. Research records now have their own ID and a `job_id`.
- Approval builds a separate immutable bundle under `storage/prototypes/<id>/` (copy of the variant plus a tiny `_player/nav.js` that only reports the current screen to the player and executes back/forward/state commands). The source variant is untouched. Prototypes belong to a variant; approving another variant moves the approval flag but keeps older bundles.
- Revisions start as `pending` and are accepted or reverted; reverted versions stay in history, hidden by default. Approving a pending revision accepts it. An approved version cannot be reverted.
- Revisions take `annotation_ids` and are validated server-side (open pins on the parent only); used pins become `applied` and cannot be edited or deleted.
- Pin element anchors are resolved in the browser from a hidden, script-disabled frame at screenshot size; if no `data-design-id` element is under the pin, only coordinates are stored.
- Cancel/timeout use `Popen` with the log streamed to `runner.log`, so partial logs survive. Concurrency is limited by `STUDIO_MAX_JOBS`. Retry creates a new job from the stored inputs and links both ways.
- Context saves are deduplicated by content; rule versions increment only when a rule's content changes.
- The client was split into `lib.js`, `store.js`, `views.js` and `app.js`. Polling redraws only when state changes, never while a field is focused or the player is open, and preserves scroll position.

- Reference images are stored under `storage/projects/<id>/references/` with a sniffed (not client-declared) type, 5 MB cap and 40 per project; SVG is rejected. Uploads use a base64 JSON action to keep the stdlib server dependency-free. At launch each job gets its own copy in `jobs/<id>/references/`, its metadata (name, note, SHA-256) is part of the shared input hash, and retries copy from the previous job, not the library. CLI agents receive them as relative file paths in the task text; there is no provider-specific image protocol.
- Generated variations with references always get a designer-review check: the studio cannot verify that an agent used an image.
- The UI follows Figma's structure (layers, frames on a canvas, tabbed inspector, comment tool, floating zoom bar) without copying its assets. Canvas zoom uses CSS zoom plus an auto-fit on entry; the review frame scales its width instead so pin coordinates stay exact.

- CLI runners receive only their `env_allowlist` (editable in Settings; defaults per agent include its auth variable). Nothing else from the studio's environment is inherited. stdin is closed so agents never wait for piped input.
- Package validation is now stricter: manifest structure, 200 files / 20 MB, no symlinks, no external URLs, `@import`, network calls, frames/objects, module imports or external navigation in HTML/CSS/JS, and relative links may use `..` only if they stay inside the package. CSS variables with no fallback and no declaration fail a "Token references" check.
- Failure messages name the cause (missing manifest, bad JSON, unsupported file with allowed types, link and file) instead of raw exceptions. `.md` notes are allowed in agent output.
- Real-agent findings that drove these changes: an agent returned a plan without writing files once (task text now forbids it); another wrote a README and used `../` links (both previously rejected with opaque errors).
