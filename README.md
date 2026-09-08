# typer-agentic

A [Typer](https://typer.tiangolo.com/) extension that makes CLIs friendly to coding agents.

When an LLM agent misspells a flag or omits an argument, Typer prints a Rich panel and exits 2. The agent then either burns turns re-reading `--help`, or, worse, gives up on the tool and starts editing files by hand. `typer-agentic` intercepts usage errors and, **only when an agent is driving**, replaces the panel with a compact block: what went wrong, the valid parameters with types and choices, exactly one corrected example, and calm instructions that keep the agent on the retry path. Humans keep Typer's stock output, byte for byte.

## Quickstart

```python
from typer_agentic import agent_errors

app = typer.Typer()
...
main = agent_errors(app)  # use `main` as your [project.scripts] entry point
```

Nothing else changes. `agent_errors(app)` returns a zero-argument callable, never mutates the app, and never monkeypatches Typer or Click.

## Before / after

`myapp sync --verbos`, Typer 0.27 (stock):

```
Usage: myapp sync [OPTIONS] {path}
Try 'myapp sync --help' for help.
╭─ Error ────────────────────────────────────────────────────────────╮
│ No such option: --verbos (Possible options: --verbose)             │
╰────────────────────────────────────────────────────────────────────╯
```

Same command with `CLAUDECODE=1` in the environment (Claude Code sets it for you):

```
✗ Usage error in `myapp sync`: No such option: --verbos

This is a recoverable input mistake, not a bug in the tool. Do not switch tools, edit files or state to work around it, or invent flags; apply the one change below and re-run the command.

Did you mean: --verbose

Fix and retry (one change): Replace '--verbos' with '--verbose'. Run the corrected example.

```
myapp sync ./PATH --verbose
```

Valid options:
  --verbose, -v  flag              Enable verbose output.
  --count        INTEGER           How many.
  --env          CHOICE[dev|prod]  Target environment.

Required arguments: PATH

Full reference: myapp sync --help
```

Honest note: Typer already prints a did-you-mean hint. What this adds is the typed inventory, the runnable example, and the de-escalation copy. If you only want the box-drawing gone, `TYPER_USE_RICH=0` does that with no dependency.

## Mode resolution

`mode="auto"` (the default) picks agent or human output per invocation. Highest precedence first:

| # | Signal | Result |
|---|---|---|
| 1 | `AgentErrorsConfig(mode="agent" \| "human")` | forced |
| 2 | `--agent-errors` / `--human-errors` on the command line | agent / human |
| 3 | `AGENT_ERRORS` env var (`1/true/yes/on` vs `0/false/no/off/empty`) | agent / human |
| 4 | Any of `CLAUDECODE`, `CLAUDE_CODE`, `CLAUDE_CODE_ENTRYPOINT`, `CODEX`, `CODEX_CLI`, `CURSOR`, `CURSOR_SESSION_ID`, `OPENCODE`, `AGENT` set and non-empty | agent |
| 5 | `tty_heuristic=True` and stderr is not a TTY | agent |
| 6 | default | human |

The sentinel flags are consumed by the wrapper before Typer parses anything, so they work even when the rest of the command line is broken. They do not appear in `--help`.

## Format

Markdown (default) is written for a model to read: stable first line `✗ Usage error in \`<command>\`: …`, fixed section order, no ANSI. JSON is for harnesses that parse stderr and retry automatically: select it with `AgentErrorsConfig(format="json")` or `AGENT_ERRORS_FORMAT=json`. The JSON document is the only thing written to the stream. See [SCHEMA.md](SCHEMA.md).

For agent-harness authors: grep the first line for `✗ Usage error`, or set `AGENT_ERRORS_FORMAT=json` and `json.loads(stderr)`.

## Configuration

```python
from typer_agentic import AgentErrorsConfig

main = agent_errors(
    app,
    config=AgentErrorsConfig(
        mode="auto",  # "agent" | "human" to force
        format="markdown",  # or "json"
        stream="stderr",  # or "stdout"
        env_var="AGENT_ERRORS",
        format_env_var="AGENT_ERRORS_FORMAT",
        flag="--agent-errors",  # None disables
        human_flag="--human-errors",  # None disables
        skill_flag="--agent-skill",  # None disables
        max_suggestions=3,
        include_hidden=False,  # list hidden params too
        tty_heuristic=False,
        agent_detect_env_vars=(...),  # see table above
        intercept_click_exceptions=False,
        repeat_detection=False,  # see below
        repeat_state_dir=None,  # defaults to $TMPDIR
    ),
)
```

## SKILL.md for your CLI

Errors are the reactive channel. `myapp --agent-skill` prints an [Agent Skill](https://docs.claude.com/en/docs/agents-and-tools/agent-skills) describing every visible command, argument, option and one example per command, so the agent has the inventory before it guesses:

```
myapp --agent-skill > .claude/skills/myapp/SKILL.md
```

`render_skill(app)` returns the same text as a string. The library never writes files itself. Every command keeps its arguments, options and example regardless of size; above 10 commands only the first line of each command's help is kept.

## Repeat-failure escalation (opt-in)

Each CLI run is a fresh process, so "the agent is looping" needs a little state. With `repeat_detection=True` the wrapper writes a small JSON record (`$TMPDIR/typer-agentic-<uid>/<prog>.json`, 10-minute TTL, atomic replace) and on the second identical failure adds: *stop retrying variations, read `--help`, rebuild from the example*. On the third it adds: *if that does not resolve it, report the exact error to the user instead of working around it*. Any I/O problem silently disables the feature.

## The copy

All agent-facing text lives in `typer_agentic/wording.py`. If you customise it, keep the rules the defaults follow: one sentence classifying the failure as a recoverable input mistake; one sentence forbidding the panic behaviours (switching tools, editing state around the CLI, inventing flags); exactly one next action; calm, imperative, no exclamation marks, no apologies, no "please"; identical wording across error types.

## Compatibility

- Python 3.11+, `typer>=0.24`, no other runtime dependency. External `click` is imported only when Typer does not vendor Click (< 0.26) or when something else in the process has already imported it; a vendored-Click app never pays for it.
- Typer 0.26+ bundles its own Click under `typer._click`; its exception classes are unrelated to `click.exceptions`. `typer_agentic.compat` resolves whichever hierarchies are present and catches all of them.
- If resolution fails on some future Typer, `agent_errors(app)` becomes a transparent passthrough and emits one `RuntimeWarning` per process (only in agent mode). Your CLI keeps working; only the feature degrades.
- Agent mode drives Click's `make_context` / `invoke` loop directly (not `main(standalone_mode=False)`, whose return value cannot distinguish `typer.Exit(n)` from a command returning `n`), so exit codes match stock Typer: `Exit(n)` → `n`, normal return → 0, `Abort` → 1, Ctrl-C → 130. Shell completion is delegated to Typer untouched.
- Not intercepted, by design: runtime exceptions inside command bodies (they propagate with Typer's pretty-exception hook applied), `NoArgsIsHelpError` (help is printed as usual), `--help` / `--version` / completion.
- The built-in `--help`, `--install-completion` and `--show-completion` options are omitted from the inventory.

The test suite runs against Typer 0.25 (external Click) and the current release: `uv run poe test-compat`.

## Development

```
uv sync
uv run poe setup      # install git hooks
uv run poe check      # lint, typecheck, dead code, deps, clones, tests
uv run poe fix        # auto-format + fix lint
uv run poe test       # tests with coverage
uv run poe test-compat
```

Golden files under `tests/golden/` are regenerated with `UPDATE_GOLDEN=1 uv run pytest`.

Release: `uv run poe release` (or `level=minor uv run poe release`) bumps the version, tags, and pushes. The tag triggers the PyPI publish workflow.

## License

MIT
