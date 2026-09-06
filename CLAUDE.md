# typer-agentic

Typer extension that makes CLIs friendly to coding agents. Package: `src/typer_agentic/`, published to PyPI as `typer-agentic`.

Design and build prompts live in `docs/plans/`. Read the current plan before starting non-trivial work.

## Commands

- `uv run poe check` — lint, typecheck, dead code, unused deps, clones, then fail-fast tests
- `uv run poe check-fast` — lint + typecheck only
- `uv run poe fix` — auto-format and fix lint issues
- `uv run poe test` — tests with coverage (parallel)
- `uv run poe check-all` — every check, report all failures
- `uv run poe release` — bump patch version, tag, push (`level=minor|major` to override)

## Code Search (`tyf`)

This project has `tyf` (ty-find) — type-aware code search that gives LSP-quality results by symbol name. Prefer it over grep for Python symbols. Reserve grep for string literals, config values, TODOs, non-Python files.

- `uv run tyf show <name>` — definition + signature + usages (flags: `-d` docs, `-r` refs, `-t` test refs, `--all`)
- `uv run tyf find <Symbol>` — locate definition
- `uv run tyf refs <name>` — find all usages
- `uv run tyf members <Class>` — view class API
- `uv run tyf calls <name>` — call tree (`--in` for callers)
- `uv run tyf list <file.py>` — file outline

All commands accept multiple symbols — batch to save tool calls.

## Clone Detection (`biston`)

Structural clone detector for Python — finds functions that are structurally similar even when names/literals/argument order differ. Run after producing multiple similar functions, or when refactoring, to spot extraction opportunities.

- `uv run biston scan --suggest .` — find clones with anti-unified template proposals
- `uv run biston scan --tests-only .` — test-duplication scan
- `uv run biston overview .` — condensed file-centric summary
- `uv run biston guide triage` — what to do with findings

## Stack

uv, ruff (lint/format), ty (type check), tyf (code search), biston (clone detection), pytest (+xdist, randomly), poethepoet (task runner), hatchling (build)

## Development Workflow

- TDD: failing test first, then implementation. Bug fixes include a regression test.
- All public behavior must have tests in `tests/`.
- When a test fails, diagnose before changing it. Default assumption: the test is right. Never weaken an assertion just to make it pass.
- **IMPORTANT**: After completing any task, run the `/python-review` skill. Apply all 🔴 Must Fix and 🟡 Should Fix findings before marking work complete.

## Notes

- ty is in beta — may produce false positives. Prefer `# ty: ignore[rule]` over blanket suppression.
- Pre-commit hook auto-fixes and restages files. Only blocks on unfixable issues.
- Keep `typer` the only runtime dependency unless a plan explicitly adds one.
