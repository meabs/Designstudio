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
