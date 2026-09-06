# Changelog

## 0.1.0

Initial release.

- `agent_errors(app)` wrapper: structured, retry-oriented usage errors when an agent drives the CLI; Typer's own output for humans.
- Auto-detection via `CLAUDECODE` and friends, `AGENT_ERRORS` env toggle, `--agent-errors` / `--human-errors` sentinel flags.
- Markdown (default) and JSON renderers; `typer-agentic/v1` schema.
- Parameter inventory with normalised types and choices, ranked suggestions, one synthesised corrected example.
- De-escalation copy in `copy.py`.
- `compat.py`: works with vendored (`typer._click`, Typer >= 0.26) and external Click; transparent passthrough if neither resolves.
- Optional repeat-failure escalation (`repeat_detection=True`).
- `--agent-skill` / `render_skill()` SKILL.md emitter.
