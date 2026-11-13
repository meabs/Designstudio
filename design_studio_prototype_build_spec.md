# Design Studio: Model-Neutral Prototype Build Specification

**Status:** Implementation specification, v1.0  
**Working name:** Design Studio  
**Audience:** Any coding agent or engineering team  
**Primary user:** Product, UX and service designers who want to direct AI coding agents without writing application code  
**Target:** Local-first, single-user, working prototype  
**Estimated scope:** One usable vertical slice; not a production design platform

---

## 0. Instructions to the implementing agent

Build the functioning prototype described below. Treat this document as the source of truth, including the acceptance tests and explicit exclusions.

- Do not assume or require any particular LLM, coding-agent brand, agent SDK or orchestration framework. Implement the specified interfaces and choose replaceable underlying libraries.
- Do not substitute a presentation, static mockup, chatbot or architecture diagram for the functioning prototype.
- Do not build a vector editor, pixel-level design manipulation tool or Figma clone. **Figma is a visual reference for the application's shell and professional feel, not its functionality.**
- The primary product capability is **persistent, versioned design guidance** that genuinely influences research, generation, revision and validation.
- **Click-through prototypes are the final output.** Do not build production application features, real account flows, payment processing, data persistence in generated apps or backend integrations for prototypes.
- Build the entire happy path using fixture agents first, then add a configurable real-agent adapter. The application must remain usable without an API key.
- Implement in vertical slices with tests; the first fully working path is more valuable than ten polished placeholders.
- When choosing an implementation detail not specified here, pick the smallest maintainable option and document the decision in `docs/DECISIONS.md`.
- Never claim a guideline has been verified if the system has only asked an LLM to assess it.

**Definition of done:** A designer can create a project, provide guidelines, run research, generate two independent screen-board variations, compare them, annotate a screen, run a revision, approve a variation and open a linked click-through prototype. A deterministic fixture performs this without external credentials; a configured agent can replace the fixture without changing the UI or domain model.

## 1. Product intent

### 1.1 One-sentence proposition

A designer-directed AI workbench that keeps design guidelines authoritative while independently configured coding agents produce, revise and connect screen designs into shareable click-through prototypes.

### 1.2 Core design principles

1. **Guidelines before generation.** The designer owns the rules. Agents must consume immutable versions of them.
2. **Research and generation are distinct jobs.** Research produces structured findings and traceable sources; generation consumes chosen research findings.
3. **Compare genuinely independent alternatives.** The same brief and context go to separate configured agents, each with its own output directory and history.
4. **Feedback is visual and contextual.** Pin comments to a screen and revise only the requested scope wherever practical.
5. **Everything is reversible.** Generation and revision create immutable versions; approval never overwrites history.
6. **Click-through, not production software.** Navigation, mocked interactions and states are enough.
7. **No provider lock-in.** Models and agent runners are replaceable infrastructure, not domain concepts.
8. **Evidence over assertion.** Show which rules were checked programmatically, which need a human, and which findings have genuine sources.

### 1.3 Intended use case

A designer creates a **Credit Card Application** project, imports a brand design guide and component tokens, adds an accessibility rule and a local rule such as “one primary action per screen”, then asks an agent to research application journey patterns. The designer selects findings and starts a three-screen board (“eligibility → details → review”) with Model A and Model B. The app displays both variants side by side. The designer comments “replace the modal with inline disclosure” on one screen, regenerates that board from the selected agent, approves it and launches an interactive, mocked journey in a clean preview.

## 2. Scope

### 2.1 Must ship in the MVP

| Area | Required behaviour |
|---|---|
| Projects | Create, rename, open and archive a project; each project has isolated guidance, jobs and assets |
| Design context | Edit Markdown guidelines; import JSON design tokens; set workspace, project and per-job rules; show effective context and precedence |
| Rules | Add a rule with ID, description, scope, severity, verification mode; version and snapshot rules for every job |
| Research | Create a research brief; start a job; review structured findings; retain source URL/title and verification status; select findings for generation |
| Screen boards | Define a board brief and 2–5 target screens; launch 2 or more configured agents using the identical brief and context snapshot |
| Variants | Display each agent's generated screen thumbnails and preview; compare boards side by side; preserve generated artifacts |
| Annotation | Add pin-based comments to a screen; support comments with coordinates and optional stable element IDs |
| Revision | Start a targeted revision using selected annotations; show new version beside predecessor and a change summary |
| Validation | Run deterministic checks on screen packages and present unknown/advisory checks separately |
| Approval | Mark a board variation approved and preserve the approved version immutably |
| Prototype | Open the approved board as a linked, mocked click-through journey; back/forward and common states must work |
| Agent integration | Fixture agent and at least one configurable real runner using a brand-neutral contract |
| History | View job state, agent identity, inputs hash, outputs, rule snapshot, changes and failures |

### 2.2 Explicit exclusions

- Real-time multiplayer, comments synced between users, SSO and roles.
- Vector drawing, freeform shape creation, bezier tools, pixel-level manual design edits, auto-layout or Figma-file editing.
- Production-ready front-end builds, production infrastructure, APIs or business databases in the generated prototype.
- Autonomous source discovery without provenance; agents must not invent or silently treat a source as verified.
- Automated claims of WCAG compliance, brand compliance or user-research validity.
- A complex agent marketplace, proprietary agent protocol, custom model training, fine-tuning or self-hosted model serving.
- Importing entire Figma projects. Exporting a runnable static click-through package is sufficient.

## 3. User experience and look & feel

### 3.1 Visual direction

**Reference:** The restrained, precise visual language of professional design tools such as Figma. This means compact chrome, neutral panels, thin borders, canvas-centred layouts, dense but readable information, understated icons and obvious selection states. **Do not copy trademarks, logos, proprietary imagery or component implementations.**

Prefer a light workspace with a slightly darker top bar. Use very limited saturated colour, primarily for active selection and job states.

| Token | Suggested value | Application |
|---|---|---|
| `--bg-app` | `#F5F5F6` | Canvas surround |
| `--bg-panel` | `#FFFFFF` | Side panels and cards |
| `--bg-toolbar` | `#242629` | Global navigation |
| `--text-primary` | `#202124` | Standard text |
| `--text-muted` | `#6B7280` | Metadata |
| `--border` | `#E5E7EB` | Hairline dividers |
| `--accent` | `#6366F1` | Selection, focus, active tabs |
| `--success` | `#14804A` | Validated / approved states |
| `--warning` | `#A56812` | Human review required |
| `--danger` | `#B42318` | Failed job / deterministic failure |
| `--radius-sm` | `6px` | Controls |
| `--radius-card` | `10px` | Cards |
| `--font-ui` | `Inter, system-ui, sans-serif` | UI typography |

Default text 13–14px; section headings 15–17px. Avoid oversized landing-page typography, gradients, cartoon illustrations and ornamental dashboard widgets. Use Lucide or equivalent neutral outline icons.

### 3.2 Desktop layout

Optimise for 1440 × 900 first; remain usable at 1280 × 720. On smaller screens, allow panel collapse and horizontal canvas scrolling rather than attempting a full mobile editing experience.

```text
┌──────────────────────────────────────────────────────────────────────────────────┐
│ Design Studio  /  Credit Card Application     [Guidelines] [Jobs]   Run ▾  Share  │  48px
├───────┬─────────────────────┬────────────────────────────────┬───────────────────┤
│       │ Project             │  Board: Application Flow        │ Inspector         │
│  P    │ ────────────────    │ [Research] [Variants] [Review]  │ ────────────────  │
│  R    │ Design Context      │                                │ Selected: Model B │
│  O    │ • Brand guide       │   ┌──────────┐ ┌──────────┐   │ Rule results      │
│  J    │ • Tokens            │   │ Screen 1 │ │ Screen 2 │   │ Annotations       │
│  E    │ • Local rules       │   │          │ │          │   │ Job details       │
│  C    │                     │   └──────────┘ └──────────┘   │                   │
│  T    │ Boards              │                                │ [+ Comment]       │
│  S    │ • Eligibility       │ [Model A] [Model B] [Compare]   │ [Revise]          │
│       │ • Application       │                                │ [Approve]         │
├───────┴─────────────────────┴────────────────────────────────┴───────────────────┤
│ Activity  • Job 104 completed  • 2 rules pass  • 1 needs review      [Open Log]   │  30px
└──────────────────────────────────────────────────────────────────────────────────┘
```

**Left 56px rail:** Projects, boards, research, guidelines, history, settings.  
**Project panel ~240px:** Context files, rule packs, board list and recent jobs.  
**Centre flexible canvas:** Board cards or previews; compare mode; zoom-to-fit for screen images only (not a vector editor).  
**Right inspector ~300px:** Selected board/screen metadata, effective rules, findings, annotations and actions.  
**Top toolbar 48px:** Breadcrumbs, selected project, job launch and prototype preview.  
**Bottom activity strip 30px:** Running, completed and failed jobs; expands to detailed event log.

### 3.3 Required routes

- `/projects` — project cards, create project action.
- `/projects/:id/context` — guidance editor, tokens, rules, effective-context preview and version history.
- `/projects/:id/research` — research jobs, finding list, sources and selection.
- `/projects/:id/boards/:boardId` — screen board and variations.
- `/projects/:id/boards/:boardId/compare` — two-up board comparison and screen selection.
- `/projects/:id/boards/:boardId/review/:variantId` — screen preview with annotation pins, rule results and revision action.
- `/projects/:id/prototypes/:prototypeId` — distraction-free click-through player.
- `/projects/:id/history` — jobs, inputs/outputs and version lineage.
- `/settings/agents` — configure runners, select default/parallel agents, connection tests and fixture mode.

## 4. Primary user journeys

### Journey A: Establish design context

1. Create a project with name, short purpose and optional source examples.
2. Edit `DESIGN.md` in a Markdown editor with preview. Provide helpful initial content; it must be user-editable.
3. Upload a `tokens.json` file. Validate JSON and show a token table and swatch preview.
4. Add rules at workspace, project or job level. Rules have immutable IDs and versions.
5. Show an **Effective Context** panel combining the layers in order: **workspace defaults → project overrides → job overrides**. If a lower-level rule overrides an ID, show the superseded rule and justification.
6. Save a version. Every job snapshots this exact merged context and its SHA-256 checksum.

### Journey B: Research

1. Designer enters a research question, e.g. “What patterns make financial application eligibility clearer?”
2. Designer optionally attaches URLs, snippets or PDFs (PDF upload can be deferred; URLs and pasted snippets are required).
3. Research job starts via selected agent adapter. Its input includes current effective design context and explicitly authorised source material.
4. Result contains concise findings, rationale, original URLs where available, confidence and flags for `verified_source`, `unverified_claim` or `source_supplied_by_user`.
5. Designer reviews/checks findings and chooses which ones belong in the subsequent board brief.
6. A research finding that lacks a traceable original URL or user-supplied source must visibly show **Unverified**, not a fabricated citation.

### Journey C: Generate competing screen boards

1. Designer defines a journey title, goal, persona, assumptions and screen list (2–5 in MVP).
2. Designer selects research findings and optionally adds a brief.
3. Designer chooses 2+ agents configured under Settings. They may be the same provider with different models/prompts; each is shown as a separate **runner configuration**.
4. System creates a single immutable `DesignJobSpec` with the exact same brief, research selection, guidelines snapshot, tokens and rules. Different runner IDs are tracked separately.
5. Each runner creates an independent `VariantPackage`. No runner may see another runner's output during this initial generation.
6. Centre canvas shows one card per variation with screen thumbnails, elapsed time, status and validation summary.
7. Designer switches between variants or compares the same screen side by side.

### Journey D: Annotate and revise

1. Open any generated screen in Review mode.
2. Click to place an annotation pin, attach text and optionally associate a specific element ID if the renderer exposes one.
3. Choose annotation(s) and click **Revise selection**.
4. Revision job receives selected parent variant, selected screen(s), comments, effective-context snapshot and the original brief. It does **not** silently alter unrelated screens or previous versions.
5. New output is a child variant version. Display old/new images side by side; highlight changed screens and show a plain-language change log.
6. Re-run deterministic rule checks, keeping advisory checks in a separate category.
7. Allow designer to accept revision or revert to previous version.

### Journey E: Approve and preview

1. Select one approved **board variant**. Per-screen mixing from different variants is a later enhancement, not an MVP requirement.
2. Inspect preview with the correct navigation and at least one state change per journey (e.g. error, help or disclosure).
3. Click **Approve & Build Prototype**.
4. Create an immutable `PrototypeBundle` from the approved static screen package. Launch in an isolated iframe player and expose an **Open in new tab** action.
5. Provide **Export ZIP** of the static HTML/CSS/JS assets plus manifest. The ZIP runs without network dependencies if assets are local.

## 5. Recommended implementation architecture

This stack is a practical default, not a dependency of the product contract. Equivalent implementations are acceptable if they meet the acceptance criteria.

| Component | Default | Notes |
|---|---|---|
| Front end | React + TypeScript + Vite | Router, TanStack Query or equivalent data fetching |
| Styling | CSS variables + Tailwind or plain CSS modules | UI values controlled by theme tokens; no brand-specific dependency |
| UI controls | Radix or equivalent accessible primitives | Use for dialogs, menus, tabs and tooltips |
| Backend | Python 3.12+ / FastAPI | Simple REST API, job coordination and asset metadata |
| Persistence | SQLite + SQLAlchemy or SQLModel | Single-user local-first; relational metadata |
| File storage | Project-scoped local filesystem | Immutable context snapshots and variant bundles |
| Jobs | Persistent SQLite queue + one local worker | Polling every ~2s; explicit retry and cancellation |
| Generated previews | Static HTML/CSS/JS | Served on separate local origin where feasible, sandboxed iframe |
| Screenshot capture | Playwright / Chromium | Board thumbnails and before/after comparisons |
| Test framework | pytest + Vitest + Playwright | Contracts, API, end-to-end workflows |
| Packaging | Docker Compose or one dev start script | One documented development command |

**No mandatory cloud services.** The prototype must run on a developer workstation. Do not bake credentials into the front end or persist secrets in job artifacts.

### 5.1 Logical components

```text
React Design Workspace
  ├─ Project / Context / Rule editors
  ├─ Research and Board job views
  ├─ Variant comparison and annotation overlay
  └─ Click-through prototype player
                  │ REST + polling
                  ▼
Python API + persistent job worker
  ├─ Project / rule / version service
  ├─ Research job orchestration
  ├─ Board & revision job orchestration
  ├─ Manifest and rule validation
  ├─ Screenshot service
  └─ Artifact / prototype registry
                  │
         AgentRunner interface
        ┌─────────┼──────────┐
        ▼         ▼          ▼
      Fixture   CLI Agent   HTTP-compatible
       runner    runner     generation adapter
        └─────────┼──────────┘
                  ▼
    Immutable job workspaces + static assets
```

### 5.2 Local structure

```text
design-studio/
  apps/
    web/                         # React UI
    api/                         # FastAPI API, worker and adapters
  contracts/
    schemas/                     # JSON Schemas for all job/result packages
    examples/                    # Valid research and variant fixtures
  fixtures/
    sample-project/              # Starter guide, tokens, rules, sample research
  storage/                       # Gitignored runtime files
    projects/{project_id}/
      context/{version_id}/
      research/{job_id}/
      variants/{variant_id}/
      prototypes/{prototype_id}/
  docs/
    DECISIONS.md
    RUNNER_CONTRACT.md
    USER_GUIDE.md
  tests/
    api/
    contracts/
    e2e/
  .env.example
  README.md
```

## 6. Model-neutral agent runner contract

### 6.1 Interface and responsibilities

The orchestration service knows only a `RunnerConfig` and a `JobEnvelope`. It does not branch on model names, require a particular provider SDK or put prompts into domain tables. Different models are configuration, not separate pipelines.

A runner supports these task types:

- `research` — structured research findings.
- `generate_board` — static multi-screen output and manifest.
- `revise_board` — a new static multi-screen output, derived from a parent variant and annotations.

Reference interface (pseudocode, not a mandated language):

```python
class AgentRunner(Protocol):
    async def execute(
        self,
        job: JobEnvelope,
        workspace: Path,
        progress: ProgressReporter,
    ) -> RunnerResult: ...

    async def health_check(self) -> RunnerHealth: ...
```

`RunnerResult` carries task status, raw logs (with secrets redacted), elapsed time, usage if known, and paths to validated output artifacts. `ProgressReporter` emits queued/started/progress/completed/failed events.

### 6.2 Required adapter implementations

1. **FixtureRunner (mandatory):** No credentials; deterministic research findings; two visibly different board variations based on runner ID; support deterministic revision based on comments. Use this for reliable demo and CI.
2. **CliRunner (mandatory):** Configurable executable, argument list, environment-variable allowlist, working directory and input delivery (`stdin` or file path). Never launch through a shell string. Each run gets its own scoped output directory. It must normalise artifacts to the contract below.
3. **OpenAICompatibleHttpRunner (optional for MVP):** A generic user-configured HTTP completion endpoint (base URL, model name, secret reference) which requests a structured JSON result and materialises its declared files. This adapter is a transport option, not a dependency on OpenAI's own services. Document endpoint compatibility limitations.

CLI and HTTP runners may generate different raw responses but must produce the same validated result schemas. No UI logic should depend on which runner produced them.

### 6.3 Runner settings schema (illustrative)

```yaml
runners:
  - id: fixture-a
    label: Exploration A
    adapter: fixture
    enabled: true
  - id: fixture-b
    label: Exploration B
    adapter: fixture
    enabled: true
  - id: local-cli-1
    label: Local Coding Agent
    adapter: cli
    executable: /absolute/path/to/installed-agent
    args: ["run", "{prompt_file}"]
    input_mode: prompt_file
    env_allowlist: ["HOME", "PATH", "MODEL_API_KEY"]
    timeout_seconds: 300
    enabled: false
```

The CLI example is deliberately generic: each actual coding-agent CLI needs its own documented `args` mapping. **Do not pretend one CLI command works for every agent.**

### 6.4 Job envelope

A JSON Schema under `contracts/schemas/job-envelope.schema.json` must validate:

```json
{
  "schema_version": "1.0",
  "job_id": "job_001",
  "project_id": "project_001",
  "task_type": "generate_board",
  "input": {
    "brief": "Create a three-screen credit card application journey",
    "screens": ["eligibility", "details", "review"],
    "selected_finding_ids": ["finding_01"],
    "source_material": [],
    "annotation_ids": [],
    "parent_variant_id": null
  },
  "context_snapshot": {
    "version_id": "ctx_007",
    "sha256": "<computed SHA-256>",
    "guidelines_path": "context/DESIGN.md",
    "tokens_path": "context/tokens.json",
    "effective_rules_path": "context/rules.json"
  },
  "output_contract": "variant-package/1.0"
}
```

The stored envelope is immutable. Validate all IDs and paths; snapshots use a canonical serialisation before hashing.

### 6.5 Research result schema

```json
{
  "schema_version": "1.0",
  "summary": "Patterns and trade-offs relevant to the research brief",
  "findings": [
    {
      "id": "finding_01",
      "title": "Explain the purpose of eligibility questions",
      "detail": "Example design recommendation tied to the source material",
      "confidence": "medium",
      "source_ids": ["source_01"],
      "verification": "source_supplied_by_user"
    }
  ],
  "sources": [
    {
      "id": "source_01",
      "title": "Supplied source",
      "url": "https://example.org/reference",
      "retrieved_at": null,
      "verification": "source_supplied_by_user"
    }
  ]
}
```

`https://example.org/reference` is an illustrative schema value, not an actual asserted research source. Real runs must only retain URLs from the supplied or actually retrieved source material. With no source, record a finding as `unverified_claim` and show it clearly.

### 6.6 Generated VariantPackage

Every board variation must be packaged as:

```text
variant-package/
  manifest.json
  screens/
    eligibility.html
    details.html
    review.html
  assets/
    theme.css
    interactions.js
    ...optional local images or fonts...
  thumbnails/
    eligibility.png
    details.png
    review.png
  changes.json                  # Required for revisions only
```

`manifest.json` must contain version, stable screen IDs, names, relative HTML paths, start screen, directed navigation edges, available mock states, provenance and output type `clickthrough-static`.

```json
{
  "schema_version": "1.0",
  "kind": "clickthrough-static",
  "board_id": "board_001",
  "screens": [
    {"id": "eligibility", "title": "Eligibility", "file": "screens/eligibility.html", "states": ["default", "help"]},
    {"id": "details", "title": "Your details", "file": "screens/details.html", "states": ["default", "error"]},
    {"id": "review", "title": "Review", "file": "screens/review.html", "states": ["default"]}
  ],
  "start_screen_id": "eligibility",
  "edges": [
    {"from": "eligibility", "to": "details", "trigger": "continue"},
    {"from": "details", "to": "review", "trigger": "continue"},
    {"from": "review", "to": "details", "trigger": "edit"}
  ]
}
```

**Generated-artifact constraints:**

- Self-contained, static and deterministic. Only HTML/CSS/JS and local assets; no build step required to view the generated output.
- No remote CDN, analytics, network fetch, external scripts or generated API calls.
- No real customer data. Use obvious synthetic content.
- Native links/buttons for journeys; local navigation between `screens/*.html` using relative links or a tiny shared navigation script.
- UI elements relevant for annotations should expose stable `data-design-id` values.
- Primary CTA elements should expose `data-role="primary-action"` to enable deterministic checking.
- Respect provided CSS variables/tokens where specified and make token usage inspectable.
- Reject path traversal, absolute paths and symlinks in artifact packages. Limit total files, total bytes and image dimensions.
- Render in a sandboxed iframe without `allow-same-origin` when scripts are allowed. Serve assets from an isolated origin for defence in depth.

### 6.7 Task instruction assembly (vendor-neutral)

Before invoking a runner, the orchestration layer assembles a **plain-text task instruction** plus the JSON envelope and a read-only copy of the context snapshot. The adapter decides how that content reaches the model (`stdin`, prompt file or HTTP message); the meaning does not change by provider.

Each task instruction must include, in this order:

1. The declared task (`research`, `generate_board`, or `revise_board`) and its intended output contract.
2. The user-authored brief and named screens, preserving the designer's exact language.
3. The full effective `DESIGN.md`, effective token values and resolved design rules, with the context snapshot hash.
4. Selected research findings with their source/verification flags; unverified findings must be marked as such.
5. Relevant immutable parent artifacts and selected annotations for revision jobs only.
6. Output directory, required manifest/schema, static-only interaction constraints and a requirement to emit no external asset dependencies.
7. A final self-check request to enumerate generated files and identify any guideline that could not be confidently honoured. **This is a self-report, not validation.**

The runner must write machine-readable deliverables to the output directory. Any prose it writes to stdout is treated as a log, never a substitute for the required files. Save the assembled task instruction with the job for debugging and reproducibility; redact secrets before making it visible in the UI.

### 6.8 Fair parallel generation

Before any `generate_board` batch, calculate a **shared input checksum**. Each runner gets the same job envelope and context snapshot, except for its runner identity, output location and execution metadata. Record the shared checksum and runner-specific execution configuration separately. Do not allow agents to read peer outputs during initial generation.

## 7. Rule system and validation

### 7.1 Effective context

Context consists of three distinct resources:

- `DESIGN.md`: prose guidelines, brand voice, UI patterns, do/don't examples.
- `tokens.json`: colours, spacing, typography, radius and approved reusable styling tokens.
- `rules.json`: individually identifiable, versioned and scoped design policies.

Rules merge by stable `id`, with workspace < project < job specificity. Log overrides, including previous value and who/what introduced the override. Each job stores the effective resolved resources as immutable files.

### 7.2 Example rule

```json
{
  "id": "CTA-001",
  "description": "Only one primary action per screen",
  "scope": "project",
  "severity": "error",
  "verification": "deterministic",
  "check": "primary_action_count",
  "parameters": {"max": 1},
  "enabled": true
}
```

Supported verification types: `deterministic`, `advisory_model`, `human_review`.

### 7.3 Required first-pass checks

| Check | Method | Meaning |
|---|---|---|
| Manifest valid | JSON Schema + paths | Generated package is well formed |
| Screens present | Filesystem and manifest | All expected screen pages exist |
| Navigation integrity | Relative link/edge resolution | Every declared edge lands on a valid screen |
| Primary action count | Parse `data-role="primary-action"` per screen | Enforce `CTA-001` on annotated actions |
| Annotation target stability | Check `data-design-id` uniqueness | Pin-target references are resolvable |
| Token references | CSS token reference scan + known key set | Detect invalid or unresolved token references |
| Local-only assets | Parse URLs and scripts | Detect externally referenced resources |

Checks that rely on generator instrumentation must show **not assessable** if required metadata is absent, rather than incorrectly passing. Deterministic validation does not certify visual quality, accessibility or full conformance with prose guidance.

**Guideline review UI:** Three groups: `Passed deterministic checks`, `Failed deterministic checks`, `Needs designer review`. Optionally expose model-advisory findings with an explicit “AI opinion” label. Human review remains first-class.

## 8. Core domain data model

Persist metadata in SQLite and artifacts on disk. IDs are opaque UUID/ULID strings, not model-specific IDs.

| Entity | Key fields |
|---|---|
| `Project` | id, name, description, created_at, archived_at |
| `ContextVersion` | id, project_id, parent_id, markdown_path, tokens_path, rules_path, hash, created_at |
| `Rule` | id, scope, version, severity, verification, parameters, enabled |
| `ResearchJob` | id, project_id, brief, context_version_id, status, created_at, finished_at |
| `ResearchFinding` | id, job_id, title, body, confidence, verification, selected, source_ids |
| `ResearchSource` | id, job_id, title, url, verification, retrieved_at |
| `Board` | id, project_id, title, brief, screen_definitions, created_at |
| `Job` | id, type, project_id, runner_config_id, status, input_hash, envelope_path, log_path, error, created_at, finished_at |
| `Variant` | id, board_id, parent_variant_id, job_id, context_version_id, package_path, created_at, status |
| `Screen` | id, variant_id, screen_key, title, file_path, thumbnail_path |
| `Annotation` | id, variant_id, screen_key, x_norm, y_norm, element_id, comment, status, created_at |
| `ValidationResult` | id, variant_id, rule_id, check_name, outcome, evidence, validation_type |
| `Prototype` | id, board_id, approved_variant_id, bundle_path, created_at |
| `JobEvent` | id, job_id, event_type, message, timestamp |

Relationships must support full lineage: `context snapshot → research selection → board brief → generation job → variant → annotation → revision job → child variant → approval → prototype`.

## 9. API contract

Use JSON request/response bodies and consistent error payloads (`code`, `message`, `details`, `request_id`). Provide an OpenAPI schema from the backend.

| Method | Path | Purpose |
|---|---|---|
| GET/POST | `/api/projects` | List/create projects |
| GET/PATCH | `/api/projects/{id}` | Read/edit project |
| GET/PUT | `/api/projects/{id}/context` | Current guidance and save next context version |
| GET | `/api/projects/{id}/context/effective` | Merged guidance, conflict and override view |
| POST | `/api/projects/{id}/context/import-tokens` | Upload and validate design tokens |
| GET/POST | `/api/projects/{id}/research` | List/create research job |
| POST | `/api/research/{jobId}/run` | Enqueue research execution |
| PATCH | `/api/research/findings/{id}` | Select/deselect finding |
| GET/POST | `/api/projects/{id}/boards` | List/create boards |
| POST | `/api/boards/{boardId}/generate` | Enqueue independent runner jobs |
| GET | `/api/boards/{boardId}/variants` | Compare generations |
| GET | `/api/variants/{id}` | Screen/manifest and validation metadata |
| GET/POST | `/api/variants/{id}/annotations` | List/place feedback pins |
| POST | `/api/variants/{id}/revise` | Enqueue revision with selected comments |
| POST | `/api/variants/{id}/approve` | Approve one complete board variant |
| POST | `/api/variants/{id}/prototype` | Build approved click-through bundle |
| GET | `/api/prototypes/{id}` | Prototype metadata and player URL |
| GET | `/api/prototypes/{id}/export` | Download static ZIP |
| GET | `/api/jobs/{id}` | Status, errors, input checksum and run metadata |
| GET | `/api/jobs/{id}/events` | Ordered progress and logs |
| GET/POST/PATCH | `/api/runners` | List/create/update configured agent runners |
| POST | `/api/runners/{id}/test` | Runner health/configuration check |

Generate and revise endpoints must be idempotent under a caller-provided idempotency key or deduplicate accidental double submits. Report partial batch failures honestly, allowing a successful variant to remain usable.

## 10. Screen-board rendering and annotation rules

- Board canvas shows **rendered screenshots** of generated screens. Do not assume agents produce a reusable JSON vector design model.
- Double-click/preview opens live sandboxed HTML, while overview uses captured PNGs for speed.
- Comparison synchronises selected screen across two variants; other screens remain accessible via filmstrip.
- Screen comments use normalised coordinates (`x_norm`, `y_norm` between 0 and 1) relative to the screenshot's native dimensions. Prefer `data-design-id` anchoring when available; coordinate fallback must be preserved.
- Clicking a pin opens editable comment and revision selection controls.
- Revision input includes both text and precise screen/pin context. If the runner supports image input, thumbnails are optional additional context; the baseline protocol must remain usable by text-only runners.
- A revision must create a child variant, not modify or delete the parent package. The worker copies unchanged screens forward if the agent intentionally changes only selected screens.
- Track and visualise which screens were modified. Use screenshot comparison as a helpful cue, not an authoritative semantic diff.

## 11. Prototype player

A prototype is a **static, navigable bundle** derived from the approved variant. It is not a generated production application.

Required player controls:

- Start/restart journey.
- Native screen navigation (buttons and links).
- Browser back/forward in a dedicated preview tab or equivalent navigation history within the player.
- At least one mocked state change (help disclosure, validation error or edit flow).
- Screen title, current screen and current variation/build version.
- Switch between device presets (desktop 1440px and mobile 390px) by changing viewport framing, not by regenerating screens.
- Open in a new tab; export ZIP.

Do not implement login, external payments, real customer information collection, persistent form submission or an application backend.

## 12. Error states and guardrails

- Runner unavailable: explain configuration issue and allow fixture mode immediately.
- Research returns no usable sources: show findings as unverified, allow human input, do not forge citations.
- Invalid artifact: retain logs, report schema/path errors, allow retry with same inputs.
- One variant fails: show failed card; successful variants remain reviewable.
- Rule conflict: show which layer won and which rule was overridden before job submission.
- Unsupported content: reject overlarge uploads, unsafe file paths, scripts pointing to external domains and invalid ZIP members.
- Runner timeout: store partial log and mark `timed_out`; no silent success.
- Key handling: config secrets from environment or local protected config, never in public API response or generated files.
- Agent isolation: execution in scoped directories and, where feasible, container/sandbox with network restrictions. Never run generated app code with backend privileges.
- Keep UX honest: if code changes exceed the requested screen scope, show that as a warning rather than hiding it.

## 13. Build sequence: working vertical slices

### Slice 1: Design system and project shell

- Build the professional three-pane layout, sidebar, project browser and context editor.
- Seed a sample Credit Card Application project.
- Implement workspace/project/job design guidance precedence and immutable versions.
- Validate token JSON and expose Effective Context.

**Acceptance:** A new project can be created, `DESIGN.md` edited, tokens imported, rules added and the resolved context inspected after reload.

### Slice 2: Research workflow with fixture runner

- Implement job queue, job events and runner interface.
- Add FixtureRunner with credible *clearly labelled synthetic* findings and source provenance states.
- Add research creation, results, source rendering and finding selection.

**Acceptance:** A research job progresses queued → running → succeeded, shows findings and allows selection without external credentials.

### Slice 3: Parallel boards and comparisons

- Board brief and screen list editor.
- Shared job envelope and independent fixture runner outputs.
- Package schema validation; render screenshots using Playwright.
- Variant cards and two-up comparison.

**Acceptance:** Two fixture runner configurations create visibly different, navigable three-screen board variants from the same effective context snapshot and research selection.

### Slice 4: Visual feedback and revision

- Annotation overlay, coordinate/element anchoring and revision selection.
- Child-version creation, before/after compare and change log.
- Rule check summary in inspector.

**Acceptance:** A pinned comment changes the targeted screen in a child variant; parent still exists and can be reopened; a rule failure is visible.

### Slice 5: Approval and click-through export

- Approve whole board variant; build package and player.
- Connected navigation, mocked state, viewport presets and ZIP export.

**Acceptance:** Designer clicks through the approved journey, navigates back, triggers a mocked state and opens the downloaded static ZIP locally.

### Slice 6: Real agent adapter

- Configurable CLI runner with safe argument array and scoped workspaces.
- Config and health-check screen; clear error handling and artifact validation.
- Demonstrate one actual connected agent generating a variant package using the same `JobEnvelope` schema. This demonstration requires the operator's own installed/configured agent; CI remains fully offline using FixtureRunner.

**Acceptance:** Changing runner configuration needs no application code changes and no migrations; existing research/board/review screens work unchanged.

## 14. Test plan and quality gate

### 14.1 Unit and contract tests

- Rule precedence and explicit override tracking, including conflict cases.
- Fixture-generated output demonstrably changes when an effective design rule or token changes; guidelines are not decorative metadata.
- Stable hashing of canonical effective context snapshots.
- JSON Schema validation for jobs, findings, manifests and runner packages.
- Reject `../` paths, absolute paths, symlinks, external asset URLs and missing screen files.
- Job lifecycle transitions, retry, timeout and partial parallel failure.
- Annotation normalisation and stable target ID handling.
- Revision immutability, lineage and approval version pinning.
- Deterministic rule checks, especially primary CTA count and missing instrumentation.

### 14.2 Required browser end-to-end scenario

1. Start with a clean local database and no API keys.
2. Create project **Credit Card Application**.
3. Add `DESIGN.md`, import `tokens.json` and create `CTA-001`.
4. Confirm the effective guidance includes the project rule; run fixture research and select two findings.
5. Create board **Application Journey** with three named screens.
6. Generate two parallel variants with different fixture runners.
7. Compare eligibility screens and place a visual pin on Variant B.
8. Run a revision with the feedback “Move the explanatory text below the heading.”
9. Confirm revised screen changed and parent did not.
10. Check deterministic validation and visible human-review status.
11. Approve the revised board and open the click-through prototype.
12. Navigate eligibility → details → review → edit details.
13. Trigger a mocked validation state, switch viewport preset and export ZIP.
14. Reload the app; confirm project, context, job history, annotations, variants and approval persist.

### 14.3 Non-functional targets for fixture mode

- Full demo workflow without credentials or external network calls.
- App shell interactive within ~2 seconds on a typical development laptop (guidance, not a benchmark claim).
- Fixture board generation and thumbnail capture complete within ~20 seconds on a typical development laptop (guidance, not a guaranteed SLA).
- Job failures and validation failures never corrupt previously approved assets.
- No browser console exceptions in the end-to-end workflow; keyboard-accessible navigation and visible focus for application controls.

## 15. Required starter content

Ship a sample project that proves guidance is being passed into the generation process, not merely displayed next to it:

```text
Credit Card Application
  DESIGN.md
    - Neutral financial-services visual style
    - Clear titles, short descriptive copy
    - Explain why sensitive details are requested
    - One obvious primary action per screen
  tokens.json
    - Neutral ink/background colours
    - One accessible accent colour
    - Spacing, typography and radius definitions
  rules.json
    - CTA-001: at most one primary action per screen
    - COMPONENT-001: reuse provided button and field styling tokens
    - COPY-001: explain requests for sensitive information (human review)
  Research fixture
    - Two clearly synthetic findings, explicitly labelled as fixture data
  Board fixture
    - Eligibility, Details, Review
    - Two visibly distinct layout approaches
```

In fixture mode, make at least one deliberate but visible rule violation in one variant so the rule inspector demonstrates a real failure, not a permanent row of green ticks.

## 16. Delivery artifacts

The implementing agent must deliver:

1. A running repository with source code for front end, backend, fixtures and tests.
2. `README.md` with requirements, quick start, test command and example workflow.
3. `.env.example` with **no credentials** and clearly documented configuration.
4. `docs/RUNNER_CONTRACT.md` with practical instructions to add a new CLI/HTTP runner without domain changes.
5. `docs/DECISIONS.md` recording material design choices and deviations from the spec.
6. JSON Schemas and example valid/invalid packages under `contracts/`.
7. A sample project and two independent fixture variants.
8. Automated unit/contract tests and the complete browser end-to-end happy path.
9. A downloadable static prototype ZIP created by the working UI.
10. A short `KNOWN_LIMITATIONS.md`, explicitly separating finished functionality from future work.

## 17. Final acceptance checklist

- [ ] Figma-inspired professional shell; **not** a Figma clone.
- [ ] Create and maintain project-specific design guidance and rules.
- [ ] Guidance uses proper workspace → project → job precedence and is versioned.
- [ ] Every agent job receives the exact resolved context snapshot.
- [ ] Research results have real provenance states and selectable findings.
- [ ] Two independent agent configurations generate competing boards in parallel.
- [ ] Every variant produces real screens and screenshot previews, not placeholders.
- [ ] Designer can compare, annotate, revise, inspect lineage and revert.
- [ ] Validation distinguishes deterministic evidence from advisory/human review.
- [ ] Approval locks a variant; exported result is a working click-through prototype.
- [ ] Fixture demo works offline and without an API key.
- [ ] A real CLI coding agent can be configured without changing domain logic.
- [ ] Tests and documentation enable any competent coding agent to continue the build.

---

## 18. Deferred roadmap, not part of v1

1. Multi-select individual screens from different model variants and reconcile a coherent flow.
2. Convert repeated designer feedback into candidate project rules, subject to designer approval.
3. MCP/API adapters for external design systems, asset libraries, Figma/Penpot source material and verified research search engines.
4. Blind A/B evaluation where model identity is hidden until designer decision.
5. Automated visual regression checks between parent and child variants.
6. Multiple designers, approval workflows and comments.
7. Visual rule assertions using screenshots, with calibrated uncertainty.
8. Publish read-only prototype links with optional access expiry.

**Do not implement the deferred roadmap until the v1 acceptance checklist passes.**
