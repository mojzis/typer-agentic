# typer-agentic

A [Typer](https://typer.tiangolo.com/) extension that makes CLIs friendly to coding agents.

> Early stage — the design lives in [`docs/plans/`](docs/plans/).

## Install

```
uv add typer-agentic
```

## Development

```
uv sync
uv run poe setup      # install git hooks
uv run poe check      # lint, typecheck, dead code, deps, clones, tests
uv run poe fix        # auto-format + fix lint
uv run poe test       # tests with coverage
```

Release: `uv run poe release` (or `level=minor uv run poe release`) bumps the version, tags, and pushes. The tag triggers the PyPI publish workflow.

## License

MIT
