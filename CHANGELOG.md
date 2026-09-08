# Changelog

## Unreleased

- Range bounds: `typer.Option(min=..., max=...)` params render as `INTEGER[1..]` / `INTEGER[1..365]` / `FLOAT[0.0..1.0]` in error blocks and SKILL.md; JSON payloads gain a `range` field on arguments and options (`null` when not a range).
- SKILL.md no longer collapses to a bare command list above 10 commands: every command keeps its arguments, options and example; only the help body is trimmed to its first line. `wording.SKILL_TOO_MANY` removed (no longer used).
- External `click` is no longer imported on Typer >= 0.26 unless something else already loaded it (saves ~5-9 ms per process). `compat.current()` picks up a late import.

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
