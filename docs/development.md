# Development

## Setup

```
uv sync
uv run poe setup   # installs the pre-commit hook from scripts/pre-commit.sh
```

## Checks

| Task | What it runs |
|---|---|
| `poe check` | ruff, ty, vulture, deptry, biston, pysentry in parallel, then fail-fast tests |
| `poe check-fast` | ruff + ty |
| `poe check-all` | everything sequentially, reports all failures |
| `poe test` | pytest with coverage, parallel, random order |
| `poe fix` | ruff format + ruff check --fix |

CI (`.github/workflows/ci.yml`) runs the same checks as separate jobs on every push to `main` and every PR.

## Release

```
uv run poe release              # patch
level=minor uv run poe release  # minor
```

Bumps `version` in `pyproject.toml`, refreshes the lockfile, commits, tags `vX.Y.Z`, pushes. The tag triggers `.github/workflows/release.yml`, which builds with `uv build` and publishes to PyPI via trusted publishing (GitHub environment `pypi`, no token stored).
