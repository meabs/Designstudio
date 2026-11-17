# Local coding-agent runners

The server discovers Codex, Claude Code, OpenCode, Gemini CLI, GitHub Copilot and Aider on PATH. Built-in invocation adapters currently support Codex, Claude Code, OpenCode and GitHub Copilot CLI. Other installed tools are displayed but disabled until an adapter is added. Existing CLI authentication is reused; no API credentials are requested by the UI.

Settings → Agents lets you choose an installed executable, choose a cached/discovered model or enter a model ID, and create independent configurations. Empty model means the CLI's configured default. Two configurations may use the same coding agent with different models.

`apps/api/local_agents.py` owns discovery and argument mappings. Codex uses `exec --sandbox workspace-write --model MODEL`; Claude uses print mode with `acceptEdits`; OpenCode uses `run --model MODEL`; GitHub Copilot CLI uses `--prompt` with `--silent --no-ask-user --no-auto-update` (plus `--allow-all-tools --allow-all-paths` only inside the studio's filesystem sandbox, otherwise just `--allow-tool=write`; never `--allow-all-urls` or `--yolo`) and `--model MODEL`. Copilot reuses `copilot login` (token in the system credential store, or `~/.copilot`); `COPILOT_GITHUB_TOKEN`, `GH_TOKEN` and `GITHUB_TOKEN` are passed through if set. Copilot has no non-interactive model list, so enter the model ID by hand. Verified with Copilot CLI 1.0.112: a full board generation passed validation, including inside the bubblewrap sandbox. No shell command string is evaluated. Availability tests check executable presence, not authentication or model entitlement. CLI versions can vary; verify your installed version's flags.

Web search is per research job (`web: true`, research only). `local_agents.web_args` adds `--search` before `exec` for Codex, `WebSearch,WebFetch` to Claude's allowed tools, and `--allow-all-urls` for Copilot. Without the switch no agent receives any web permission.

Each job gets its own `storage/jobs/ID/` directory containing:

- `envelope.json`: immutable full inputs, resolved context and shared input hash.
- `TASK.md`: assembled task instruction.
- `output/`: required generated artifacts.
- `runner.log`: CLI stdout/stderr, retained locally (not exposed by the web server).

The prompt includes the task, brief, named screens, guidance, tokens, resolved rules, context hash, selected findings and revision comments. Revision envelopes contain a parent-package path. Agents write `output/manifest.json` with static screens or `output/research.json`. See schemas and examples in `contracts/`. Screen IDs must be string indices (`0`, `1`, `2`), with HTML in `screens/0.html`, etc. Every link and asset must be local; instrument primary actions using `data-role="primary-action"` and comment targets with `data-design-id`.

A nonzero exit, timeout, missing file or invalid package fails the job; there is no silent fallback to fixture output. CLI runners do not yet have container isolation, and agent permission prompts can cause timeout. Do not disable the agent's security controls to work around this.
