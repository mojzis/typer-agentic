# Spec: `typer-agent-errors` — structured, retry-oriented usage errors for Typer CLIs

**Rev 3 (2026-09).** Changes from rev 2, all driven by verifying the ecosystem against Typer 0.27.2:

- **(a) Vendored Click.** Typer ≥ 0.26 bundles its own copy of Click under `typer._click`; its `UsageError` is *not* a subclass of `click.exceptions.UsageError`. All interception now goes through a new `compat.py` (§4.1) that resolves the exception classes at import time and degrades to plain passthrough if it cannot. Nothing in the library imports the top-level `click` package unconditionally.
- **(b) Baseline moved.** Typer already prints `Possible options: …` / `Did you mean …?` on typos. Did-you-mean is no longer a differentiator; §8 keeps it only because we need the ranked candidate for the single corrected example. The pitch (§1, §11) is reframed around *inventory-with-types + one corrected example + de-escalation copy + agent auto-detection*.
- **(c) Environment reality.** Python `>=3.10` (Typer dropped 3.9 in 0.24). `rich` is always installed with Typer since 0.22 — the "rich optional" matrix is gone, replaced by a `TYPER_USE_RICH=0/1` matrix.
- **(d) Broader agent detection** default env-var list (§5).
- **(e) `NoArgsIsHelpError`** is a `UsageError` subclass that must be passed through untouched (§4).
- **(f) New optional milestone M7:** a SKILL.md emitter (§12) so agents can learn the option inventory *before* failing — Typer itself now ships an Agent Skill inside its wheel, establishing the convention.

**Audience:** Claude Code (implementer).
**Author role:** Senior CLI architect. This document is the contract; where it says MUST/SHOULD, treat it as such. Where it says "decide", the implementer has latitude but must document the choice in the README.

---

## 1. Problem statement

When an LLM agent drives a Typer CLI and misspells a flag or omits a required argument, Typer emits human-oriented output (Rich panels with box-drawing, usage line, prose) and exits 2. Since 0.20 it does include a did-you-mean hint, which is necessary but not sufficient. Two failure modes follow: (1) the agent wastes turns re-reading `--help` or guessing at the *shape* of the fix; (2) worse, after one or two failed attempts the agent **panics and abandons the tool entirely** — editing config files by hand, reimplementing the operation in Python, piping through `sed`, or inventing flags. The second mode is more expensive than the first.

This library intercepts Typer's usage errors (`UsageError` and subclasses: `BadParameter`, `MissingParameter`, `NoSuchOption`, `BadOptionUsage`, `BadArgumentUsage`) and emits a compact, corrective error block containing: what went wrong, the valid parameters **with types and choices**, **exactly one corrected example invocation**, and **explicitly de-escalating instructions** that keep the agent on the retry path. Optionally (§12) it also emits a SKILL.md describing the whole CLI so the agent has the inventory up front.

Human users are unaffected by default and can opt in to preview the agent view.

**What we deliberately do not do:** replace Typer's parser (cf. `agentyper`), add output routing / `--schema` / profiles / safety rails to command bodies (cf. `murli`), or touch runtime exceptions. Scope is the parse-error seam only.

## 2. Package identity & constraints

- Distribution: `typer-agent-errors`; import: `typer_agent_errors`.
- Runtime deps: `typer>=0.24` only. **No upper pin** — compatibility with future Typer internals is handled by §4.1's graceful degradation, not by a version ceiling. `click` is never a declared dependency; it is imported only inside `compat.py`, only as a fallback, only in a `try`.
- Python `>=3.10`. `src/` layout, `pyproject.toml`, `py.typed`, full type hints, MIT license.

```
src/typer_agent_errors/
  __init__.py      # public API re-exports
  compat.py        # resolves UsageError & friends from typer._click or click; NEW in rev 3
  config.py        # AgentErrorsConfig, resolve_mode(), resolve_format()
  intercept.py     # wrapper / invocation logic
  introspect.py    # ctx/command -> param inventory
  suggest.py       # best-candidate ranking (for the example), difflib + Typer's own possibilities
  payload.py       # typed dataclasses: the format-agnostic error model
  render/
    markdown.py    # default renderer
    json.py        # opt-in renderer
  copy.py          # all agent-facing strings (de-escalation copy) in one place
  skill.py         # SKILL.md emitter (M7, optional)
```

## 3. Public API

```python
from typer_agent_errors import agent_errors, AgentErrorsConfig

app = typer.Typer()
...
main = agent_errors(app)  # entry-point callable
main = agent_errors(app, config=AgentErrorsConfig(...))  # configured
```

`agent_errors(app)` MUST return a zero-arg callable suitable for `[project.scripts]`. It must not mutate the app's registered commands and must not monkeypatch Typer or Click globals — all interception is at invocation time. Rejected designs: patching `UsageError.show`; injecting a custom `TyperGroup` cls into user apps (Typer no longer supports Click-level customisation of user apps anyway).

`AgentErrorsConfig` (dataclass, all defaulted):

| field | type | default | meaning |
|---|---|---|---|
| `mode` | `Literal["auto","agent","human"]` | `"auto"` | force or auto-resolve (§5) |
| `format` | `Literal["markdown","json"]` | `"markdown"` | agent-mode wire format (§6) |
| `stream` | `Literal["stderr","stdout"]` | `"stderr"` | where the block goes |
| `env_var` | `str` | `"AGENT_ERRORS"` | mode toggle env var |
| `format_env_var` | `str` | `"AGENT_ERRORS_FORMAT"` | `markdown`/`json` override |
| `flag` | `str \| None` | `"--agent-errors"` | sentinel flag; `None` disables |
| `skill_flag` | `str \| None` | `"--agent-skill"` | prints SKILL.md and exits 0 (§12); `None` disables |
| `max_suggestions` | `int` | `3` | cap on `suggestions` list |
| `include_hidden` | `bool` | `False` | list hidden params |
| `tty_heuristic` | `bool` | `False` | `not isatty(stderr)` ⇒ agent |
| `agent_detect_env_vars` | `tuple[str, ...]` | see §5 | presence ⇒ agent in auto |
| `intercept_click_exceptions` | `bool` | `False` | also structure non-usage `ClickException`s |
| `repeat_detection` | `bool` | `False` | escalating copy on repeated identical failure (§7.3) |

## 4. Interception mechanics

### 4.1 `compat.py` — the only place that knows where Click lives

Typer ≥ 0.26 vendors Click as `typer._click`; the exception classes raised by a Typer app are `typer._click.exceptions.UsageError` etc., which are **unrelated by inheritance** to `click.exceptions.UsageError` even when the external `click` package is also installed. Typer < 0.26 raises the external Click classes. The library MUST work against both.

`compat.py` exposes:

```python
(
    UsageError,
    BadParameter,
    MissingParameter,
    NoSuchOption,
)
(
    BadOptionUsage,
    BadArgumentUsage,
    NoArgsIsHelpError,
    ClickException,
)
Exit, Abort, get_command, CompatStatus
```

Resolution order:

1. `from typer._click import exceptions as _exc` (Typer ≥ 0.26). `Exit`/`Abort` come from `typer.exceptions` in all versions; `get_command` from `typer.main`.
2. Else `import click.exceptions as _exc` (Typer < 0.26).
3. Else, or if any required name is missing, `CompatStatus.ok = False` with a reason string.

Behaviour when `CompatStatus.ok` is `False`: `agent_errors(app)` returns a callable that simply invokes `app()` — a transparent passthrough — and emits **one** `warnings.warn(..., RuntimeWarning)` per process, only when resolved mode is `agent`. It MUST NOT raise at import or wrap time. This is the crash-proofing principle from rev 2 applied to the dependency boundary: an unsupported Typer version degrades the *feature*, never the user's CLI.

Because a process may conceivably have both hierarchies present (older Typer + plugins), `intercept.py` catches a *tuple* of every resolvable `UsageError` class, not one. Provide a helper `is_usage_error(exc) -> bool`.

Tests MUST run against a pinned pre-vendoring Typer (0.25.x, external Click 8.2/8.3) and the latest 0.27.x, plus a simulated "resolution failed" case (monkeypatch `compat` to raise on import) asserting passthrough.

### 4.2 Invocation loop

**Resolve mode BEFORE invoking** (§5). Then:

- **Human mode:** call `app()` untouched — zero interference, byte-identical Rich behaviour by construction. We never re-implement Typer's human rendering.
- **Agent mode:** invoke `get_command(app).main(argv, prog_name=..., standalone_mode=False)`:
  - `NoArgsIsHelpError` (a `UsageError` subclass raised by `no_args_is_help=True`) → `exc.show()` (prints help), `sys.exit(exc.exit_code)`. **Never** render an error block for it — the user asked for help. Check this class *before* the generic `UsageError` branch.
  - Any other `UsageError` → build payload (§6.1), render (§6.2/6.3), write to stream, `sys.exit(exc.exit_code)` (Click uses 2; preserve it).
  - `Exit` → `sys.exit(e.exit_code)`; help/version/completion output stays untouched.
  - `Abort` → `Aborted.` to stderr, exit 1 (mirror standalone behaviour).
  - Non-usage `ClickException`: default replicate standalone (`e.show()`, exit `e.exit_code`); if `intercept_click_exceptions`, emit reduced payload (`error.type: "click_exception"`, no inventory).
  - Anything else propagates unchanged. Runtime errors inside command bodies are an explicit non-goal for v1. Note that calling `get_command(app).main` bypasses `Typer.__call__`'s pretty-exception hook; decide whether to re-apply it (set `sys.excepthook` as `Typer.__call__` does) — recommended yes, for parity with human mode.

**Sentinel flags = argv pre-scan, not Typer options.** The parse we're guarding may abort (unknown option earlier in argv) before a registered flag is ever reached. So: before invocation, scan `sys.argv[1:]` for exact tokens `--agent-errors` / `--human-errors` / `--agent-skill` (or configured), record, and **strip them from the argv passed to the app**. Document that these flags are consumed by the wrapper and won't appear in `--help`.

**`exc.ctx` may be `None`.** Fallback chain: `exc.ctx.command` → resolve from `get_command(app)` down the argv chain as far as possible without re-triggering errors → minimal payload with null inventory and a hint to run `<prog> --help`. **Crash-proofing rule:** the entire payload/render path is wrapped in try/except; a bug in our formatter must never mask the user's real error — on internal failure, fall back to `exc.show()` semantics and the original exit code.

## 5. Mode resolution (`auto`)

Precedence, highest first — implemented as a pure function `resolve_mode(config, argv, environ)` in `config.py`, unit-testable without invoking any app:

1. Explicit `config.mode` = `"agent"` or `"human"`.
2. Sentinel flags (`--agent-errors` forces agent; `--human-errors` forces human — the human preview/suppress override).
3. Env `AGENT_ERRORS`: truthy ⇒ agent, falsy ⇒ human.
4. Detection: any of `agent_detect_env_vars` present and non-empty ⇒ agent. Default tuple:
   `("CLAUDECODE", "CLAUDE_CODE", "CLAUDE_CODE_ENTRYPOINT", "CODEX", "CODEX_CLI", "CURSOR", "CURSOR_SESSION_ID", "OPENCODE", "AGENT")`.
   Claude Code sets `CLAUDECODE=1` and `CLAUDE_CODE_ENTRYPOINT`; the others follow the detection list used by `agent-kit` for Codex/Cursor/OpenCode. Zero-config in the target scenario. Keep this list in one constant; expect to extend it.
5. TTY heuristic, only if enabled (false-positives on ordinary pipes/CI, hence off by default).
6. Default: human.

`resolve_format(config, environ)`: `config.format` unless `AGENT_ERRORS_FORMAT` overrides; unknown values fall back to markdown with no error.

**Interaction with `TYPER_USE_RICH`:** none. Human mode is Typer's own rendering, so `TYPER_USE_RICH=0` still yields Typer's plain-text errors; agent mode never consults it. Document `TYPER_USE_RICH=0` in the README as the zero-dependency baseline for people who only want the box-drawing gone.

## 6. Payload and renderers

### 6.1 Format-agnostic payload (`payload.py`)

All introspection produces one typed dataclass tree — the renderers are dumb views over it. Fields (this is the v1 data contract; additive-only after release):

- `schema: str` — `"typer-agent-errors/v1"`.
- `error`: `type` (stable enum: `no_such_option`, `bad_parameter`, `missing_parameter`, `bad_option_usage`, `bad_argument_usage`, `no_such_command` — best-effort detection from group-resolution `UsageError`s, else `usage_error` — plus `click_exception`), `message`, `offending` (bad token/value or null; from `NoSuchOption.option_name`, `BadParameter` value/`param_hint`), `param` (canonical name or null).
- `command_path`: `ctx.command_path` or best-effort `prog_name`.
- `suggestions: list[str]` (§8), best first.
- `valid_arguments`: `{name, metavar, type, required, nargs, help}` per visible argument.
- `valid_options`: `{names, type, required, default, multiple, is_flag, choices, help}` per visible option. Skip hidden (unless configured) and the built-in `--help`. `type` = `param.type.name.upper()`; `choices` populated for Choice types (including `typing.Literal` params, which Typer maps to Choice). Boolean flags list both `opts` and `secondary_opts` (`--verbose, --no-verbose`). `default` sanitised to be serialisable (repr fallback; omit for required/callables/`...`).
- `subcommands`: `{name, help}` list for group-level errors, else null.
- `example: str | None` (§9).
- `recovery: RecoveryCopy` (§7).
- `exit_code: int`.

### 6.2 Markdown renderer (default)

Rationale: in the target scenario stderr is not parsed by code — it is pasted into a model's context, and **the model is the parser**. Markdown is ~30–40% cheaper in tokens than the equivalent JSON, is read more reliably by models than nested brackets, and degrades gracefully under tool-output truncation (a clipped markdown block loses its tail; a clipped JSON block loses validity).

Requirements:

- **Stable first line** (machine-greppable sentinel; some harnesses surface only line 1): `✗ Usage error in \`{command_path}\`: {short message}`.
- Deterministic section order: header → recovery framing line → `Did you mean:` → `Fix and retry (one change):` fenced example → `Valid options:` aligned block → `Required arguments:` → footer line pointing at `--help`. Omit empty sections entirely.
- Aligned plaintext columns for options (name(s) / type / help), e.g. `--env  CHOICE[dev|prod]  Target environment.` No box-drawing, no ANSI, no Rich.
- The corrected example sits in a fenced code block so agents copy it verbatim.
- Total budget: target ≤ 30 lines for a command with ≤ 15 options; if the option list exceeds 20 entries, truncate to the 20 most relevant (suggested ones first, then required, then alphabetical) and add `…and N more — run '{command_path} --help'`.
- Golden-file tested (§10).

Illustrative target output (normative for structure, not for exact wording — wording lives in `copy.py`, §7):

```
✗ Usage error in `myapp sync`: no such option: --verbos

This is a recoverable input mistake, not a bug in the tool. Do not switch
tools or edit files to work around it — fix the flag below and re-run.

Did you mean: --verbose

Fix and retry (one change):

    myapp sync ./PATH --verbose

Valid options:
  --verbose, --no-verbose   flag               Enable verbose output.
  --count                   INTEGER
  --env                     CHOICE[dev|prod]   Target environment.

Required arguments: PATH

Full reference: myapp sync --help
```

### 6.3 JSON renderer (opt-in)

For deterministic middleware (harnesses that `json.loads(stderr)` and drive automatic retries). Selected via `format="json"` or `AGENT_ERRORS_FORMAT=json`. One JSON object, `indent=2`, UTF-8, newline-terminated, the **only** thing emitted on the stream — no fences, no prose. Field names mirror §6.1 exactly (`recovery` serialised as an object with the copy strings). Ship `SCHEMA.md`; export the dataclasses/TypedDicts from `payload.py` for downstream typing. Additive-only after v1.

## 7. De-escalation copy (`copy.py`) — keeping the agent from running away

Observed agent pathology: fail once, fail twice, then give up on the CLI and take a harder, riskier path (hand-edit state, reimplement, shell out around the tool). The error block is our only channel to interrupt that spiral, so its language is a first-class deliverable, not decoration. All agent-facing strings live in `copy.py` as named constants/templates so they can be tuned without touching logic.

### 7.1 Tone and content rules (normative)

Every rendered error MUST include, in this order of prominence:

1. **Classification** — one sentence framing the failure as a *recoverable input mistake*, explicitly not a bug, not a missing capability, not a broken environment.
2. **Anti-abandonment directive** — one sentence explicitly naming and forbidding the panic behaviours: do not switch tools, do not edit files/state directly to work around the CLI, do not invent flags. Negative instructions here are deliberate; this is the one place where "do not X" earns its keep because X is the precise observed failure.
3. **Exactly one next action** — the corrected example (or `--help` when introspection failed). Never present two competing remedies; a panicking agent given options picks badly. "One change" phrasing anchors minimal-diff retries instead of wholesale command rewrites.

Style constraints: calm, imperative, concrete; no exclamation marks, no apologies, no anthropomorphising, no "please". ≤ 2 sentences of framing before the actionable content. Wording must be identical across error types wherever possible (stable phrasing is easier for models to key on across turns).

### 7.2 Per-error-type action lines

`copy.py` maps `error.type` → one action template: `no_such_option` → "Replace '{offending}' with '{best}'."; `missing_parameter` → "Add the required {kind} '{param}'."; `bad_parameter` with choices → "Use one of: {choices}."; `no_such_command` → "Use the subcommand '{best}'."; introspection-failed fallback → "Run '{command_path} --help' and retry with a flag from its output." Every template ends by pointing at the single example invocation.

### 7.3 Repeat-failure escalation (optional, `repeat_detection=True`, default off)

Each CLI invocation is a fresh process, so detecting "the agent is looping" requires state. When enabled: write a tiny record (hash of `argv` + error type, timestamp) to `$TMPDIR/typer-agent-errors/{prog}.json` with a 10-minute TTL; on a failure whose hash matches the previous record, escalate the copy: "Second identical failure. Stop retrying variations. Run `{command_path} --help`, read the option list, then construct the command fresh from the example below." On a *third* match, additionally say the honest thing: "If `--help` does not resolve this, report the exact error above to the user instead of working around it." — sanctioned surrender beats improvised workarounds. Implementation constraints: best-effort only (any I/O error ⇒ behave as if disabled), no locking beyond atomic write-replace, never crash, document the state-file location. This ships as milestone M6 and must be independently removable.

## 8. Candidate ranking (`suggest.py`)

Typer/Click already computes candidates (`NoSuchOption.possibilities`; "Did you mean" for subcommands). We still need a **single best** candidate to build the one corrected example, and Typer's list is unranked and includes secondary opts (`--no-verbose` for a `--verbos` typo). So:

- Candidates: union of Typer's `possibilities` (when present) and `difflib.get_close_matches(offending, candidates, n=max_suggestions, cutoff=0.6)` over all `opts + secondary_opts` of visible params; case-sensitive pass, then lowercased pass if empty.
- Rank by difflib ratio, descending; tie-break: primary `opts` before `secondary_opts`, then shorter. Dedup, cap at `max_suggestions`. `suggestions[0]` is `best` for §7.2/§9.
- Unknown subcommand: visible subcommand names.
- `BadParameter` on a Choice: the choice values (turns `--env prd` into `suggestions: ["prod"]`).
- No matches ⇒ empty list; action line falls back to the `--help` template.

## 9. Example-invocation synthesis

`example` = `command_path` + all **required** args/options with type-derived placeholders, plus the corrected form of the offending param. Placeholders: `INTEGER`→`1`, `FLOAT`→`1.0`, `TEXT`→`VALUE`, `PATH`/`FILE`/`DIRECTORY`→`./PATH`, `CHOICE`→first choice, flag→bare primary flag, UUID/datetime→valid literal; `nargs>1`/`multiple` shown twice. One line; correct *shape* over plausible values. Null when introspection failed.

## 10. Testing (pytest)

Do **not** use `CliRunner` for interception tests — it manages `standalone_mode` itself and tests the wrong seam. Invoke the wrapped callable with patched `sys.argv`, catch `SystemExit` via `pytest.raises`, capture streams via `capsys`.

Fixture app: a group; two subcommands; required arg `PATH`; options `--verbose/-v` flag, `--count INTEGER`, `--env` Choice[dev,prod]; one hidden option; one command with `no_args_is_help=True`.

1. `--verbos` → markdown block: sentinel first line, `Did you mean: --verbose` (not `--no-verbose`), fenced example present, exit 2. Golden-file compare.
2. Unknown subcommand `synk` → suggestion `sync`.
3. Missing required arg → `missing_parameter` action line names `path`; example includes `./PATH`.
4. `--count abc` → bad_parameter; `INTEGER` visible in options block.
5. `--env prd` → suggestion `prod`, choices rendered as `CHOICE[dev|prod]`.
6. Extra-args / bad_argument_usage path.
7. `--help` in agent mode → normal help, exit 0, no error block.
8. Forced human mode → output identical to unwrapped `app()` (no sentinel line, same exit code), under both `TYPER_USE_RICH=0` and `=1`.
9. `resolve_mode` precedence matrix incl. `--human-errors` beating `AGENT_ERRORS=1`, and each default detect env var; `resolve_format` fallback on garbage values. Pure-function tests.
10. Sentinel flags stripped from argv (behaviour identical apart from mode).
11. `UsageError(msg, ctx=None)` → minimal block, no crash, `--help` fallback action.
12. Payload/render crash safety: monkeypatch introspection to raise → original error still surfaced, original exit code.
13. Hidden option excluded by default; included with `include_hidden=True`.
14. JSON format: `AGENT_ERRORS_FORMAT=json` → `json.loads(stderr)` succeeds; fields per §6.1; parseability is itself an assertion.
15. De-escalation invariants, asserted structurally on every agent-mode golden file: classification sentence present, anti-abandonment sentence present, **exactly one** fenced example, ≤ 2 framing sentences before it.
16. Repeat detection (if M6 lands): same failing argv twice → escalated copy on second run; corrupt/unwritable state file → silent fallback to normal copy.
17. **Compat matrix (replaces rev 2's rich matrix):** CI runs the full suite on py 3.10–3.14 × {`typer==0.25.*` with external click, `typer>=0.27` vendored}. Plus: `no_args_is_help` command invoked bare in agent mode → help text, exit 2, no error block. Plus: simulated compat-resolution failure → wrapper is a passthrough, one `RuntimeWarning`, user CLI still works.
18. SKILL.md emitter (if M7 lands): `--agent-skill` prints valid frontmatter + every visible command/option; exits 0; hidden params excluded; `render_skill()` output identical to the flag's stdout.

## 11. Documentation

README: 3-line quickstart; a real before/after capture (Typer 0.27 Rich panel vs markdown block — and note honestly that Typer's stock output already contains a did-you-mean, so the reader sees what we actually add); mode-resolution table (§5); format selection; the §7.1 copy rules summarised for people who want to customise `copy.py`; a "compatibility" section explaining the vendored-Click situation and the passthrough guarantee; "for agent-harness authors" note (grep the `✗ Usage error` sentinel, or set `AGENT_ERRORS_FORMAT=json` for deterministic parsing); a one-liner pointing at `TYPER_USE_RICH=0` for people who only want plain text. Plus `SCHEMA.md` (JSON contract) and `CHANGELOG.md` at 0.1.0.

## 12. SKILL.md emitter (`skill.py`, milestone M7, optional)

Errors are the *reactive* channel; the proactive one is telling the agent the inventory before it guesses. The Agent Skills convention (a `SKILL.md` with YAML frontmatter `name`/`description` and a markdown body) is now used by Typer itself, which ships `typer/.agents/skills/typer/SKILL.md` in its wheel. We give any wrapped CLI the same capability.

- `render_skill(app, *, name: str | None = None, description: str | None = None, config=...) -> str` in `skill.py`, pure (no I/O). Walks `get_command(app)` and emits:
  - Frontmatter: `name` (default: prog name), `description` (default: app help, first line, ≤ 1024 chars).
  - Body sections: `## When to use` (app help), `## Commands` — one subsection per visible command with its help, arguments (name/type/required) and options in the same aligned format as §6.2, one synthesised example per command via §9 machinery, then `## On usage errors` — the §7.1 classification and anti-abandonment sentences verbatim from `copy.py`, plus "the error block always contains exactly one corrected example; run it." Same strings, so the agent has seen them before the first failure.
- Sentinel `--agent-skill` (pre-scanned and stripped like `--agent-errors`): print `render_skill(app)` to **stdout**, exit 0. Never triggers introspection of the failing command; it's a whole-app dump.
- README documents the intended workflow: `myapp --agent-skill > .claude/skills/myapp/SKILL.md` (or the agent's equivalent directory), optionally as a `post-install` step the tool author owns. We do not write files anywhere ourselves.
- Budget: ≤ 200 lines for ≤ 10 commands; beyond that, list commands with one-line help and tell the agent to run `<cmd> --help` per command.
- Must be independently removable (single module + one sentinel branch).

## 13. Milestones

1. **M1** — skeleton; `compat.py` with resolution + passthrough; `resolve_mode`/`resolve_format` + tests (9, 17-compat-failure).
2. **M2** — interception loop, exit-code fidelity, `NoArgsIsHelpError` passthrough, human passthrough; tests 7–8, 12, 17.
3. **M3** — introspection + payload dataclasses; tests 3–4, 11, 13.
4. **M4** — candidate ranking + example synthesis; tests 2, 5, 6.
5. **M5** — renderers (markdown golden files, JSON) + `copy.py` with §7 invariants; tests 1, 14, 15. Sentinel-flag pre-scan; test 10. Docs, CI matrix.
6. **M6 (optional)** — repeat-failure escalation; test 16. Cleanly removable.
7. **M7 (optional)** — SKILL.md emitter; test 18. Cleanly removable.

## 14. Non-goals (v1)

Runtime exceptions inside command bodies; i18n; bare-Click apps (may work incidentally via the `click` fallback branch, untested); other output formats (YAML etc.); interactive-prompt remediation; shell-completion changes; output routing / `--schema` / dry-run / safety rails for command bodies (that is a different library's job); cross-process agent-session tracking beyond §7.3's minimal TTL file; writing skill files to disk.

## 15. Acceptance criteria (end-to-end)

1. `CLAUDECODE=1 myapp sync --verbos` on Typer 0.27.x exits 2; stderr starts with `✗ Usage error in \`myapp sync\``, contains `Did you mean: --verbose`, contains the anti-abandonment sentence, and contains exactly one fenced, runnable corrected command.
2. Same invocation with `AGENT_ERRORS_FORMAT=json`: stderr is a single valid JSON document with `error.type == "no_such_option"` and `suggestions[0] == "--verbose"`.
3. `myapp sync --verbos` in an interactive terminal without the env var: Typer's stock error, byte-for-byte, with and without `TYPER_USE_RICH=0`.
4. Criteria 1–3 also hold on Typer 0.25.x with external Click.
5. `myapp --agent-skill` (if M7) prints a SKILL.md whose frontmatter parses and which lists `sync` with `--verbose`, `--count INTEGER`, `--env CHOICE[dev|prod]`.
