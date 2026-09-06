# typer-agentic

See the [README](../README.md) for usage, [SCHEMA.md](../SCHEMA.md) for the JSON contract, and [docs/plans/](plans/) for the design spec.

Module map (`src/typer_agentic/`):

| module | role |
|---|---|
| `intercept.py` | invocation loop: resolve mode, run app, structure usage errors |
| `compat.py` | resolves Click exception classes from `typer._click` or `click`; passthrough on failure |
| `config.py` | `AgentErrorsConfig`, `resolve_mode`, `resolve_format`, `scan_argv` |
| `builder.py` | usage error → `ErrorPayload` |
| `introspect.py` | Click command → argument/option/subcommand inventory |
| `suggest.py` | candidate ranking |
| `example.py` | corrected example synthesis |
| `payload.py` | the typed, format-agnostic model |
| `render/` | markdown and JSON views |
| `wording.py` | every agent-facing string |
| `repeat.py` | optional repeat-failure escalation |
| `skill.py` | SKILL.md emitter |
