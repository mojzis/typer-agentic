"""Turn a usage error into an :class:`ErrorPayload`."""

from __future__ import annotations

import re
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from . import compat, introspect, suggest, wording
from .config import AgentErrorsConfig
from .example import Fix, build_example
from .payload import (
    ArgumentInfo,
    ErrorInfo,
    ErrorPayload,
    ErrorType,
    OptionInfo,
    RecoveryCopy,
    SubcommandInfo,
)
from .render.markdown import type_label

_NO_SUCH_COMMAND = re.compile(r"No such command '(?P<name>[^']*)'")
_DID_YOU_MEAN = re.compile(r"\s*Did you mean .*\?$")
_EXTRA_ARGS = re.compile(r"unexpected extra argument", re.IGNORECASE)
_MISSING_COMMAND = re.compile(r"^Missing command", re.IGNORECASE)
_QUOTED_VALUE = re.compile(r"^'(?P<value>[^']*)'")
# "Got unexpected extra argument(s) (extra)": the offending tokens are in the
# *last* parenthesised group; the first one is the "(s)" of "argument(s)".
_PARENS = re.compile(r"\((?P<inner>[^)]*)\)")

_BY_CLASS: tuple[tuple[str, ErrorType], ...] = (
    ("NoSuchOption", "no_such_option"),
    ("MissingParameter", "missing_parameter"),
    ("BadParameter", "bad_parameter"),
    ("BadOptionUsage", "bad_option_usage"),
    ("BadArgumentUsage", "bad_argument_usage"),
    # Click >= 8.3 raises a dedicated NoSuchCommand; older/vendored Click uses
    # a plain UsageError, which the message patterns below catch.
    ("NoSuchCommand", "no_such_command"),
)
_BY_MESSAGE: tuple[tuple[re.Pattern[str], ErrorType], ...] = (
    (_NO_SUCH_COMMAND, "no_such_command"),
    (_MISSING_COMMAND, "missing_command"),
    (_EXTRA_ARGS, "bad_argument_usage"),
)


def classify(exc: BaseException) -> ErrorType:
    """Best-effort stable error type for any resolvable usage error."""
    status = compat.current()
    for class_name, error_type in _BY_CLASS:
        if isinstance(exc, status.get(class_name)):
            return error_type
    message = str(getattr(exc, "message", exc))
    for pattern, error_type in _BY_MESSAGE:
        if pattern.search(message):
            return error_type
    return "usage_error"


def _format_message(exc: BaseException) -> str:
    formatter = getattr(exc, "format_message", None)
    return str(formatter()) if callable(formatter) else str(exc)


def _message(exc: BaseException, error_type: ErrorType) -> str:
    if error_type == "no_such_option":
        # format_message() appends "(Possible options: ...)"; we render our own
        # ranked suggestion instead, so use the bare message.
        text = str(getattr(exc, "message", exc))
    else:
        text = _format_message(exc)
    if error_type == "no_such_command":
        # Typer appends "Did you mean 'x'?" for subcommands; same reason.
        text = _DID_YOU_MEAN.sub("", text)
    return text.strip()


def _offending(exc: BaseException, error_type: ErrorType, message: str) -> str | None:
    option_name = getattr(exc, "option_name", None)
    if option_name:
        return str(option_name)
    if error_type == "no_such_command":
        match = _NO_SUCH_COMMAND.search(message)
        return match.group("name") if match else None
    if error_type == "bad_parameter":
        # The raw message starts with the quoted value ("'prd' is not one of");
        # the formatted one is prefixed with "Invalid value for '--env':".
        match = _QUOTED_VALUE.match(str(getattr(exc, "message", "")))
        return match.group("value") if match else None
    if error_type == "bad_argument_usage":
        groups = _PARENS.findall(message)
        return groups[-1] if groups else None
    return None


def _param_name(exc: BaseException) -> str | None:
    param = getattr(exc, "param", None)
    name = getattr(param, "name", None)
    return str(name) if name else None


def _display_name(param: Any, fallback: str | None) -> str:
    """How the agent should spell the parameter: ``--env`` for options."""
    opts = list(getattr(param, "opts", []) or [])
    if opts and getattr(param, "param_type_name", "") == "option":
        return str(opts[0])
    return fallback or "?"


def _locate(
    exc: BaseException, root: Any, prog_name: str, argv: Sequence[str]
) -> tuple[Any, Any, str]:
    """(ctx, command, command_path) from ``exc.ctx``, or by walking argv."""
    ctx = getattr(exc, "ctx", None)
    if ctx is not None and getattr(ctx, "command", None) is not None:
        return ctx, ctx.command, str(ctx.command_path)
    command, path = introspect.resolve_from_argv(root, prog_name, argv)
    return None, command, path


def _find_option(options: Sequence[OptionInfo], spelling: str) -> OptionInfo | None:
    return next((o for o in options if spelling in o.names), None)


def _find_option_by_param(
    options: Sequence[OptionInfo], param: Any
) -> OptionInfo | None:
    opts = list(getattr(param, "opts", []) or [])
    return next((o for o in options if o.primary == opts), None) if opts else None


@dataclass(frozen=True)
class _Inputs:
    """Everything a per-error-type analyser may need."""

    exc: BaseException
    error: ErrorInfo
    command_path: str
    config: AgentErrorsConfig
    arguments: list[ArgumentInfo]
    options: list[OptionInfo]
    subcommands: list[SubcommandInfo]

    def example(self, *, fix: Fix | None = None, extra: Sequence[str] = ()) -> str:
        return build_example(
            self.command_path, self.arguments, self.options, fix=fix, extra=extra
        )


@dataclass(frozen=True)
class Analysis:
    """What the analyser derived: ranked suggestions, one example, one action."""

    suggestions: list[str]
    example: str | None = None
    action: str | None = None


def _no_such_option(inp: _Inputs) -> Analysis:
    names, primary = suggest.option_candidates(inp.options)
    ranked = suggest.rank(
        inp.error.offending or "",
        names,
        possibilities=getattr(inp.exc, "possibilities", None),
        primary=primary,
        limit=inp.config.max_suggestions,
    )
    if not ranked:
        return Analysis(ranked)
    target_option = _find_option(inp.options, ranked[0])
    return Analysis(
        ranked,
        example=inp.example(fix=Fix(target_option)),
        action=wording.ACTION_NO_SUCH_OPTION.format(
            offending=inp.error.offending, best=ranked[0]
        ),
    )


def _missing_parameter(inp: _Inputs) -> Analysis:
    param = getattr(inp.exc, "param", None)
    kind = getattr(param, "param_type_name", None) or "parameter"
    target_option = _find_option_by_param(inp.options, param)
    return Analysis(
        [],
        example=inp.example(fix=Fix(target_option)),
        action=wording.ACTION_MISSING_PARAMETER.format(
            kind=kind, param=_display_name(param, inp.error.param)
        ),
    )


def _bad_parameter(inp: _Inputs) -> Analysis:
    param = getattr(inp.exc, "param", None)
    target_option = _find_option_by_param(inp.options, param)
    choices = target_option.choices if target_option else introspect.choices_of(param)
    if choices:
        ranked = suggest.rank(
            inp.error.offending or "", choices, limit=inp.config.max_suggestions
        )
        return Analysis(
            ranked,
            example=inp.example(
                fix=Fix(target_option, ranked[0] if ranked else choices[0])
            ),
            action=wording.ACTION_BAD_PARAMETER_CHOICES.format(
                choices=", ".join(choices)
            ),
        )
    if target_option:
        type_name, bounds = target_option.type, target_option.range
    else:
        type_name, bounds = introspect.type_and_range(param)
    return Analysis(
        [],
        example=inp.example(fix=Fix(target_option)),
        action=wording.ACTION_BAD_PARAMETER.format(
            param=_display_name(param, inp.error.param),
            type=type_label(type_name, bounds=bounds),
        ),
    )


def _no_such_command(inp: _Inputs) -> Analysis:
    ranked = suggest.rank(
        inp.error.offending or "",
        suggest.subcommand_candidates(inp.subcommands),
        limit=inp.config.max_suggestions,
    )
    if not ranked:
        return Analysis(ranked)
    return Analysis(
        ranked,
        example=inp.example(extra=[ranked[0]]),
        action=wording.ACTION_NO_SUCH_COMMAND.format(best=ranked[0]),
    )


def _missing_command(inp: _Inputs) -> Analysis:
    if not inp.subcommands:
        return Analysis([])
    return Analysis(
        [],
        example=inp.example(extra=[inp.subcommands[0].name]),
        action=wording.ACTION_MISSING_COMMAND,
    )


def _bad_option_usage(inp: _Inputs) -> Analysis:
    offending = inp.error.offending
    target_option = _find_option(inp.options, offending) if offending else None
    return Analysis(
        [],
        example=inp.example(fix=Fix(target_option)),
        action=wording.ACTION_BAD_OPTION_USAGE.format(offending=offending)
        if offending
        else None,
    )


def _bad_argument_usage(inp: _Inputs) -> Analysis:
    return Analysis([], action=wording.ACTION_BAD_ARGUMENT_USAGE)


def _generic(inp: _Inputs) -> Analysis:
    return Analysis([])


_ANALYSERS: dict[ErrorType, Callable[[_Inputs], Analysis]] = {
    "no_such_option": _no_such_option,
    "missing_parameter": _missing_parameter,
    "bad_parameter": _bad_parameter,
    "no_such_command": _no_such_command,
    "missing_command": _missing_command,
    "bad_option_usage": _bad_option_usage,
    "bad_argument_usage": _bad_argument_usage,
    "usage_error": _generic,
    "click_exception": _generic,
}


def _action_text(analysis: Analysis, command_path: str) -> str:
    if analysis.action is None:
        return wording.ACTION_HELP_FALLBACK.format(command_path=command_path)
    return analysis.action + wording.ACTION_EXAMPLE_SUFFIX


def _recovery(action: str, escalation: str | None = None) -> RecoveryCopy:
    return RecoveryCopy(
        classification=wording.CLASSIFICATION,
        directive=wording.DIRECTIVE,
        action=action,
        escalation=escalation,
    )


def build_payload(
    exc: BaseException,
    *,
    root: Any,
    prog_name: str,
    argv: Sequence[str],
    config: AgentErrorsConfig,
) -> ErrorPayload:
    """Full payload for a usage error; ``exc.ctx`` may be ``None``."""
    error_type = classify(exc)
    message = _message(exc, error_type)
    error = ErrorInfo(
        type=error_type,
        message=message,
        offending=_offending(exc, error_type, message),
        param=_param_name(exc),
    )
    ctx, command, command_path = _locate(exc, root, prog_name, argv)
    exit_code = int(getattr(exc, "exit_code", 2))
    if command is None:
        return ErrorPayload(
            error=error,
            command_path=command_path,
            recovery=_recovery(_action_text(Analysis([]), command_path)),
            exit_code=exit_code,
        )
    arguments, options = introspect.inventory(command, config)
    inputs = _Inputs(
        exc=exc,
        error=error,
        command_path=command_path,
        config=config,
        arguments=arguments,
        options=options,
        subcommands=introspect.subcommands(command, ctx),
    )
    analysis = _ANALYSERS[error_type](inputs)
    return ErrorPayload(
        error=error,
        command_path=command_path,
        recovery=_recovery(_action_text(analysis, command_path)),
        exit_code=exit_code,
        suggestions=analysis.suggestions,
        valid_arguments=arguments,
        valid_options=options,
        subcommands=inputs.subcommands if introspect.is_group(command) else None,
        example=analysis.example or inputs.example(),
    )


def build_click_exception_payload(
    exc: BaseException, *, command_path: str
) -> ErrorPayload:
    """Reduced payload for non-usage ClickExceptions (no inventory)."""
    return ErrorPayload(
        error=ErrorInfo(type="click_exception", message=_format_message(exc)),
        command_path=command_path,
        recovery=_recovery(wording.ACTION_CLICK_EXCEPTION),
        exit_code=int(getattr(exc, "exit_code", 1)),
    )
