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
- `uv run poe setup` — install the madoqua pre-commit hook (once per clone)

## Code Search (`tyf`)

This project has `tyf` (ty-find) — type-aware code search that gives LSP-quality results by symbol name. Agents must use `uv run tyf` instead of grep for Python symbol definitions and references. Reserve grep for string literals, config values, TODOs, non-Python files.

- `uv run tyf show <name>` — definition + signature + usages (flags: `-d` docs, `-r` refs, `-t` test refs, `--all`)
- `uv run tyf find <Symbol>` — locate definition
- `uv run tyf refs <name>` — find all usages
- `uv run tyf members <Class>` — view class API
- `uv run tyf calls <name>` — call tree (`--in` for callers)
- `uv run tyf list <file.py>` — file outline

All commands accept multiple symbols — batch to save tool calls.

## Clone Detection (`biston`)

Structural clone detector for Python — finds functions that are structurally similar even when names/literals/argument order differ. Run after producing multiple similar functions, or when refactoring, to spot extraction opportunities. It also runs in the commit hook (`--focus-args`, staged files only) — a clone pair blocks the commit that touches one of its files.

- `uv run biston scan --suggest .` — find clones with anti-unified template proposals
- `uv run biston scan --tests-only .` — test-duplication scan
- `uv run biston overview .` — condensed file-centric summary
- `uv run biston guide triage` — what to do with findings

## Toolbox (aesop)

Every tool teaches itself: run `uv run <tool> guide` first and follow its conventions (`madoqua`, `gerenuk`, `biston`, `zorilla`, `pycoati`, `tyf`). Refresh the pins with:

```
uv lock --refresh --upgrade-package madoqua --upgrade-package gerenuk --upgrade-package biston --upgrade-package zorilla --upgrade-package pycoati --upgrade-package ty-find && uv sync
```

**On commit** — `hooks/pre-commit` is a madoqua shim (`[tool.madoqua]` in pyproject.toml). It only runs when a `.py`/`.pyi` file is staged; otherwise it is a silent no-op. Fix phase: `ruff check --fix`, `ruff format` (re-staged). Check phase, in parallel on the staged files: `ruff check`, `ty check`, `biston scan --focus-args`, `zorilla check`, plus `gerenuk run -- -q` (impacted tests only, diffed against `origin/main`; whole suite when a non-Python file changed). Typical run ~1.5 s, gerenuk dominates; `uv run madoqua stats` shows the timings (`.git/hook-timings.jsonl`). Exit 1 = your code is blocked, 2 = madoqua could not run. `MADOQUA_SKIP="<step name>"` drops a check for one run; `--no-verify` still works but is not the fix.

Migration notes: the old hand-rolled hook ran `ty check` on the whole repo; madoqua checks staged files only, so repo-wide diagnostics do not block clean commits, but a file with existing diagnostics blocks the first commit that touches it (currently none: `uv run ty check` is clean). zorilla has a baseline of 17 findings (ZR004 assertion-roulette x13, ZR001 conditional-test-logic x4) in `tests/test_compat.py`, `test_e2e.py`, `test_introspect.py`, `test_render.py`, `test_repeat.py`, `test_skill.py`, `test_suggest.py`; the hook blocks the next commit that touches one of those files until its findings are fixed or suppressed with `# zorilla: ignore[ZRxxx] -- <reason>` on the same line.

**Fresh clone** — `uv sync` then `uv run madoqua install` (or `uv run poe setup`) once; `core.hooksPath=hooks` is local git config, not tracked.

**On demand** —
- `uv run gerenuk impacted-tests` — which tests the current diff reaches and why; `uv run gerenuk run -- -q` runs them; `uv run gerenuk audit <file.py>` lists symbols nothing references (report, do not delete).
- `uv run biston scan --suggest .` — repo-wide clone scan with extraction templates (`uv run poe clones` is the same scan).
- `uv run zorilla check .` — full-tree test-smell lint; `uv run zorilla stats .` / `overview .` for the breakdown.
- `uv run tyf find|refs|show <symbol>` — see Code Search above.

**Periodic audit, never in the hook or CI** — `uv run pycoati . --format pretty` scores every test for suspicion and prints a ranked list plus a remediation ladder; run it before a test cleanup session. It runs the suite with `--cov`, so pytest-cov must stay installed or coverage is silently null.

## Stack

uv, ruff (lint/format), ty (type check), tyf (code search), biston (clone detection), madoqua (commit hook), gerenuk (impacted tests), zorilla (test lint), pycoati (test audit), pytest (+xdist, randomly), poethepoet (task runner), hatchling (build)

## Development Workflow

- TDD: failing test first, then implementation. Bug fixes include a regression test.
- All public behavior must have tests in `tests/`.
- When a test fails, diagnose before changing it. Default assumption: the test is right. Never weaken an assertion just to make it pass.
- **IMPORTANT**: After completing any task, run the `/python-review` skill. Apply all 🔴 Must Fix and 🟡 Should Fix findings before marking work complete.

## Notes

- ty is in beta — may produce false positives. Prefer `# ty: ignore[rule]` over blanket suppression.
- Pre-commit hook (madoqua) auto-fixes and restages files. Blocks on unfixable lint, ty diagnostics, clone pairs, zorilla findings in staged files, or a failing impacted test.
- Keep `typer` the only runtime dependency unless a plan explicitly adds one.
