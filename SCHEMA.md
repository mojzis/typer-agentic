# JSON error contract — `typer-agentic/v1`

Emitted when the agent-mode format is `json`. One UTF-8 JSON object, `indent=2`, newline-terminated, the only thing written to the configured stream. Additive-only after 0.1.0: new keys may appear, existing keys keep their meaning.

The dataclasses in `typer_agentic.payload` (`ErrorPayload`, `ErrorInfo`, `ArgumentInfo`, `OptionInfo`, `SubcommandInfo`, `RecoveryCopy`) are the source of truth and are exported for downstream typing.

```jsonc
{
  "schema": "typer-agentic/v1",
  "error": {
    "type": "no_such_option",       // see enum below
    "message": "No such option: --verbos",
    "offending": "--verbos",        // bad token / value, or null
    "param": null                   // canonical parameter name, or null
  },
  "command_path": "myapp sync",
  "recovery": {
    "classification": "This is a recoverable input mistake, not a bug in the tool.",
    "directive": "Do not switch tools, ...",
    "action": "Replace '--verbos' with '--verbose'. Run the corrected example.",
    "escalation": null              // string on repeated identical failures
  },
  "exit_code": 2,
  "suggestions": ["--verbose"],     // best first, at most max_suggestions
  "valid_arguments": [
    {"name": "path", "metavar": "PATH", "type": "PATH", "required": true,
     "nargs": 1, "help": "Where to sync.", "choices": null}
  ],
  "valid_options": [
    {"names": ["--verbose", "-v"], "type": "BOOL", "required": false,
     "default": false, "multiple": false, "is_flag": true, "choices": null,
     "help": "Enable verbose output.", "nargs": 1}
  ],
  "subcommands": null,              // [{"name", "help"}] for group-level errors
  "example": "myapp sync ./PATH --verbose"   // null when introspection failed
}
```

## `error.type`

| value | raised by |
|---|---|
| `no_such_option` | `NoSuchOption` |
| `bad_parameter` | `BadParameter` (wrong type, invalid choice) |
| `missing_parameter` | `MissingParameter` |
| `bad_option_usage` | `BadOptionUsage` (e.g. option requires a value) |
| `bad_argument_usage` | `BadArgumentUsage`, or "unexpected extra argument" |
| `no_such_command` | unknown subcommand |
| `missing_command` | group invoked without a subcommand |
| `usage_error` | any other `UsageError` |
| `click_exception` | non-usage `ClickException`, only with `intercept_click_exceptions=True`; no inventory |

## Types

`type` is normalised across Typer/Click versions: `INTEGER`, `FLOAT`, `TEXT`, `BOOL`, `CHOICE`, `PATH`, `FILE`, `UUID`, `DATETIME`, `INTEGER RANGE`, `FLOAT RANGE`; anything else is Click's type name upper-cased. `choices` is populated for `CHOICE` (including `typing.Literal` and `Enum` params).

`default` is JSON-safe: scalars as-is, paths and enums as strings, sequences as lists, `repr()` otherwise; `null` for required params, callables and `...`.
