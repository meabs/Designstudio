# User guide

## Concepts
- **Context version** – the saved Markdown guidelines, flat tokens and rules. Jobs use the *saved* version; unsaved edits are marked and never used.
- **Variation** – one runner's complete board of screens. **Revisions** are child versions that you accept or revert.
- **Approval** – pins one version, locks it and builds a prototype bundle. Approving a different version moves the approval; earlier prototypes stay available.

## Workspace layout (Figma-style)
- **Left panel**: design context, pages (boards) and a **Layers** tree of variations and their screens. Click a layer to select that frame.
- **Canvas**: each variation is a labelled section of frames with prototype-flow arrows. Select a frame to see its handles and size; double-click for a live sandboxed preview. A floating bar zooms (also Ctrl+scroll) and fits.
- **Right inspector**: **Design** (frame, version, context, fill tokens, references, lineage), **Checks**, **Comments**. Revise and Approve are pinned at the bottom.
- **Tools and shortcuts**: `V` move, `C` comment, `+` / `-` zoom, `0` reset, `1` fit, `Esc` close a comment.

## Reference images
Open **References** in the left panel (or use the picker on Research and Generate) to upload images by choosing files, drag-and-drop, or pasting from the clipboard. Add a note telling the agent how to use each image. Selected images are copied into the job, listed in the task text and recorded in the envelope and input hash, so every runner in a comparison gets the same ones. Revisions reuse the board's references. Deleting a library image does not affect past jobs. The fixture runner records references but cannot interpret them; a variation with references gets a "needs designer review" item rather than a claim they were applied.

## Compare more rigorously
- **Blind compare** (Variants toolbar): hides runner names, ids and fixture hints, both in the UI and in the data the server sends. Options get random letters, inherited by their revisions. Choose **I prefer this** (with an optional reason) or **Reveal without choosing**. Approving a version also counts as your choice and reveals. The result is recorded and shown in History. Honest limit: the generated files and job folders on disk still contain runner details, and visibly different designs can give a runner away.
- **Mix screens**: pick the source version for each screen (thumbnail grid) to create a new version. It is a normal immutable version with provenance per screen, package checks, a "Mixed provenance" review item and its own prototype. Each source's shared assets are kept apart so styles never collide. Revising a mix asks which runner should apply the feedback.
- **Per-region revisions**: pins anchored to an element revise only that element (turn off with "Limit changes to pinned elements"). The studio compares parent and child per element and adds a pass/fail "Revision scope" check; changed regions are outlined on the review screen.

## Guidelines page
Edit guidelines with a live preview, edit tokens as JSON (invalid JSON is flagged and blocks saving), and manage rules in the table. Rule IDs are stable; saving a changed rule raises its version. Add instructions as plain lines (stored as human-review `GUIDANCE-nnn` rules). The effective-context panel shows which scope won for any ID, before you save. Version history lists what changed; **Load into editor** restores an old version as a new one.

## Research
Enter a question and optional sources (one URL or excerpt per line). Findings without a source are labelled unverified; fixture findings are labelled synthetic. Take findings to a new board (and generate) or attach them to an existing board.

## Boards
- **Variants** – cards for each variation, plus cards for runs that failed, timed out or were cancelled (Retry / Cancel). Double-click a screen for a live sandboxed preview.
- **Compare** – pick any two versions; the filmstrip switches screens; changed screens are flagged.
- **Review** – with the comment tool, click the screen to drop a bubble pin (click a pin to open its thread popover), tick pins to include, **Revise selection**. For a revision, toggle Before/After or open side by side. Use **Add comment** or press Enter on the screen for keyboard-only pin placement (position is editable).

## Experimenting against your own rules

Agents treat the rules as hard constraints and will usually follow a rule over your brief, without saying so up front. When you want an agent to break a convention on purpose:

1. Open **Generate variants**. As you type the brief, a *Heads-up* box lists active rules your brief, run-only prose or reference notes seem to contradict (for example "three equal actions" against CTA-001). It is keyword-based and advisory; it cannot read images.
2. Open **Experiment for this run only**. Write a run-only brief (it is placed above DESIGN.md and stated to take precedence), and for each rule choose Keep, Suspend or Replace, or add a new rule.
3. Generate. The overrides are stored on those jobs only, are part of the shared input hash so every runner gets identical input, and are **not** saved into the project guidelines. A revision of one of those variants inherits its overrides.

After a run, the variant inspector's Design tab shows the run-only overrides and an **Agent self-report (unverified)**: whether the agent says it viewed the reference images, and any line where it says it did not follow part of the brief or references. A designer-review check is added when it does. The studio has not verified any of it. While a board is blind the self-report is hidden.

## Checks
Deterministic checks show their evidence. They never claim accessibility, brand or visual conformance. “Needs designer review” items stay open until you mark them.

## Prototype player
Back/Forward, Restart, mock states (Default/Help/Error where the screen supports them), 1440/390 framing, Open in new tab, Export ZIP (extract and open `index.html`).

## Sharing a prototype
In the player, **Share** creates a read-only link (expires after 1 hour to 30 days, or never) and lists active links with **Copy** and **Revoke**. Start the studio with `STUDIO_SHARE_PORT=5180` to serve them; that port exposes only approved prototype bundles, never the studio. Links are plain HTTP and need no login, so treat them like unlisted URLs. On another device, replace `localhost` in the link with this computer's address.

## Settings → Agents
Add local coding-agent configurations (model optional), rename, enable/disable, test or delete them. Each local agent also has the environment it may see, an **Automatic retries** limit (0 to 3) and, on Linux with bubblewrap, a **Filesystem sandbox** (on by default) that hides your home directory and other projects from the agent and lets it write only its own job folder. Fixtures always work offline. `STUDIO_MAX_JOBS` (default 3) limits concurrent jobs.

## Many runs, many projects

- **Rounds.** Every Generate action is a *round*: the variants created together plus every revision descending from them. Boards show variants grouped by round, newest first, with the round number and time on each card (so three runs of the same agent are no longer all "Studio B · v1"). Once a board has more than six variants, older rounds fold away to a one-line summary; click a round to open it. The Layers list in the left panel is grouped the same way and only expands the screens of the variant you are looking at.
- **Failed attempts** appear as a compact row at the top of the board with **Retry with same inputs** and **Dismiss**. Dismiss hides the attempt from the board; it stays in Job history. A failure that has already been retried disappears by itself.
- **Projects** opens on a home page (no project sidebar) with each project's boards, variants, approvals, running jobs and failures, sorted by last activity. With more than five projects a filter box appears. Inside a project, the small chevron next to the project name in the top bar switches projects without going back.
- **Usage and time.** The board header shows runs, agent time and tokens when an agent reports them; running jobs show live progress (elapsed, files written, last activity, live output).


## Designer tools

**Free exploration.** In *Generate → Experiment for this run only*, choose *Loosen* (no rules or checks; the guidelines are inspiration only) or *Fully open* (no guidelines, tokens or rules; the brief leads). Nothing is saved to the project, and each variant records how it was made.

**Spread.** *Spread* is on by default whenever you generate with more than one agent, so each gets a different directed angle (calm, bold, dense, warm, editorial, playful) and the results actually differ. Untick it for a strict like-for-like comparison where every agent gets the identical input. Each new spread round rotates the angles.

**Rules vs free.** Tick *Rules vs free* to run every agent twice with the same brief and angle, once as configured and once with the rules off. Open either in the inspector and press *Compare rules vs free*. Not available on blind boards (it would reveal which is which).

**Rule-break log.** A free variant lists what the saved guidelines would have said (fail, review, pass). Press *Propose a guideline change* on a break you like to put it in your guideline draft.

**Pull style into guidelines.** *Explore from this version → Pull style* lists the colours, fonts and radii used on the screens; tick, name and save a new guideline version.

**Realistic states.** *Add realistic states* asks the agent for empty, loading, error and long-content states on every screen, as a new revision.

**Decision log.** Approve and *Set aside…* ask for a one-line reason. *History → Decision log* shows the trail and copies it as Markdown for a stakeholder review.

**Review documents and audit.** In *Settings → Agents & models → Review documents* point the project at a folder of Markdown files. Checklist lines such as `- [ ] Must include "Representative APR"` or `- [ ] Never say "guaranteed approval"` are checked against the screen text; every other checklist line or "must/never/always" bullet becomes a review item with its file and line. Headings choose the area (accessibility, legal, content, design review). Open the **Audit** tab on a version and press *Run audit*; it never runs by itself. It always includes built-in accessibility checks (language, title, viewport, headings, alt text, labels, names, contrast, small text, tap targets, fixed widths). Mark findings *OK / accept as exception / needs change*.

**Responsive preview.** The live preview has Phone / Tablet / Desktop width buttons.

**Agent reading of your documents.** For checklist items that can't be matched literally, the Audit tab has *Agent reading of your documents*: pick an agent and press *Read*. It reads your Markdown and the version's screens and answers *meets / fails / could not tell* per item, with the evidence it saw. It is manual, costs one agent run, and is always labelled an unverified opinion. The template (fixture) runners can't read documents and say so.


## Importing existing guidelines

Already have a `DESIGN.md`, rules files or design tokens? On **Guidelines → Import from your files** enter the folder path (on the computer running the studio), or use *Choose files…* / *Choose folder…* in your browser (this also works from a phone). The studio finds:

- **Guidelines text:** files named like design / brand / style / guidelines (else the first Markdown file). Rules-only files stay out of the prose.
- **Rules:** checklist lines, bullets under headings like "Rules" or "Principles", and "must / never / always" bullets elsewhere. An ID written in the file (`CTA-001: …`) is kept; others get `IMPORT-nnn`. Each keeps its source file and line.
- **Tokens:** flat or nested JSON (including `value` / `$value` style files) and CSS custom properties (`--accent: #0f766e`) from `.css` files or code blocks in Markdown.

Tick what you want and press *Load into my draft*. Nothing is saved until you review the draft and press *Save new version*, so you can edit first. Items already in your draft come in unticked. The folder is remembered, so *Re-scan* picks up edits to the files. Reading a folder is only allowed from the computer running the studio.

This is separate from **Review documents** (Settings), which feeds the audit rather than the guidelines.


## Guidelines profiles (testing different rules)

A **profile** is a complete, separately versioned set of guidelines: text, rules and tokens. Every project starts with one, **Main**. On **Guidelines** use the profile bar to:

- **New profile:** copy Main (or any profile's current version, or blank defaults) under a new name, e.g. "Looser tone" or "Strict compliance". Edit it and save versions as usual; Main is untouched.
- **Switch** the profile you are editing (save or discard first), **Rename**, **Make default**, or **Delete** a non-default profile.

The **default** profile is what new runs, research, the conflict preview and the sidebar counts use. In **Generate**, tick one or more profiles; each ticked profile runs every agent with the same brief, references and (if Spread is on) directions, so the results are comparable. It can be combined with *Rules vs free*. Variants, the inspector, Compare and History show which profile each came from. A revision keeps its parent's profile (falling back to the default if that profile was deleted), "Pull style" saves into the variant's profile, and a free run's rule-break log checks against its own profile. Deleting a profile never touches variants already made; they keep their snapshot.


## Websites, mobile apps, or both

When you create a board (or turn research into one) choose **what you are designing**:

- **Website:** screens are designed and screenshotted at 1440×900.
- **Mobile app:** screens are designed for a 390×844 phone (viewport meta, 44px touch targets, no horizontal scroll, app-style navigation), screenshotted at that size, and the prototype player opens in the phone view. The audit treats a fixed width over 390px as a failure instead of a note.
- **Both:** one responsive design checked at both widths. Each screen is screenshotted twice; board cards show the desktop screen with a phone inset, and **Review** has a **Desktop | Phone** switch. Pins belong to the view they were placed in, so a phone pin never shows on the desktop layout.

The chosen target is passed to every agent in the task text. Boards can have **2 to 12 screens**. Boards created before this feature keep the original 720×960 frame.

## Working faster with the winner

**Starter-guidelines warning.** A new project starts with sample guidelines (“neutral financial-services”, a grey-green palette). While they are unchanged the Guidelines page shows a warning, because every agent is told the same thing and designs converge.

**Draft guidelines from a description.** On the Guidelines page, describe the company, audience and feel in a few sentences and pick an agent (Claude Code or Codex). It returns a draft DESIGN.md, tokens and rules, plus the assumptions it made. Nothing is saved: *Replace my draft with this* loads it into your unsaved draft, and it becomes a version only when you press Save new version.

**Bring a part from another design.** In the inspector's *Explore* block, *Bring a part from another design…* asks an agent to rebuild one part (for example "the hero" or "the audit log") from a different design on the same board into the one you are looking at, using this design's own styling. It becomes a new revision of the design you started from; the donor is only read. Not available on a blind board, because it would reveal which design is which.

**Ask about a spot instead of changing it.** When you add a pin, choose *Ask the agent a question*. The agent reads the HTML and CSS and answers under **Comments → Questions**, labelled as an unverified agent opinion. Nothing is changed.

**Cut-off runs are kept.** If an agent runs out of time after writing every screen and the manifest, the work is kept and marked **Cut off** instead of being thrown away. Review it and use Revise to finish any polish. If the screens or manifest are missing, the run still counts as timed out.

**Developer hand-off.** In the player, *Developer hand-off* downloads a clean zip: `site/` (static HTML, CSS and JS, open `index.html`), `design/` (the guidelines, `tokens.json`, `tokens.css` and `rules.json` it was built to) and a README. It does not name the agent, and it states that the automated checks are structural, not a compliance certification. (*Export ZIP* is still there for the raw prototype folder.)

## Editing a screen directly

Pick the **Edit** tool (pencil, or press **E**) in Review. The screen becomes live: hover to outline an element, click to select it, shift-click to select several. Changes show immediately and stay a draft until you save. The draft is kept in this browser and in the studio, so it follows you to another browser.

- **Style and text.** In the Design tab change text (on elements without children), text colour, background, font size, weight, alignment, width, height, radius, padding, opacity and visibility. Project colour tokens appear as swatches. With several elements selected, a style change applies to all.
- **Layout.** Drag an element to reorder it: a green line shows where it will land (hold **Alt** to drop it inside the target). **Alt+↑/↓** moves it among its siblings, **Ctrl+D** duplicates, **Delete** removes, and **Text** / **Button** add a new block after the selection.
- **Resize and free move.** A selected element has handles on its right, bottom and corner: drag one to set its width and height. Turn on **Free move** (or hold **Ctrl** while dragging) to offset an element from its normal place instead of reordering it. The flow around it does not change.
- **Images.** **Image** adds a PNG or JPEG after the selection (large pictures are scaled down first). On a selected image you can edit its alt text and **Replace…** the picture.
- **From another screen.** Open **Insert from another screen**, pick a screen and an element, and insert a copy after the selection. The studio copies it from the saved version. A copy is never the screen's primary action, so duplicating or inserting a primary button leaves the one-primary-action check as it was.
- **Undo.** **Ctrl+Z** undoes and **Ctrl+Shift+Z** redoes, per screen. **Discard** drops the whole draft.

Press **Save as new version** to create a child version with a Manual edit check. It is pending like any revision: accept or revert it, compare it with its parent, or keep revising by pin. No agent runs and the original is never modified. Limits are listed in KNOWN_LIMITATIONS.md.
