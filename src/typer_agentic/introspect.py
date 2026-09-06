"""Click command/context -> parameter inventory."""

from __future__ import annotations

import contextlib
import enum
from collections.abc import Iterable, Sequence
from pathlib import PurePath
from typing import Any

from .config import END_OF_OPTIONS, AgentErrorsConfig
from .payload import ArgumentInfo, OptionInfo, SubcommandInfo

_TYPE_ALIASES = {
    "INT": "INTEGER",
    "STR": "TEXT",
    "STRING": "TEXT",
    "BOOLEAN": "BOOL",
    "FILENAME": "FILE",
    "INT RANGE": "INTEGER RANGE",
}
_SKIPPED_OPTIONS = frozenset({"help", "install_completion", "show_completion"})
_SCALARS = (bool, int, float, str)


def normalise_type_name(param_type: Any) -> str:
    """Stable, version-independent upper-case type name (``INTEGER``, ``TEXT``)."""
    raw = getattr(param_type, "name", None) or type(param_type).__name__
    name = str(raw).upper()
    return _TYPE_ALIASES.get(name, name)


def choices_of(param: Any) -> list[str] | None:
    raw = getattr(getattr(param, "type", None), "choices", None)
    if raw is None:
        return None
    return [_choice_str(c) for c in raw]


def _choice_str(choice: Any) -> str:
    if isinstance(choice, enum.Enum):
        return str(choice.value)
    return str(choice)


def sanitise_default(param: Any) -> Any:
    """A JSON-serialisable default, or ``None`` when there is none worth showing."""
    if getattr(param, "required", False):
        return None
    value = getattr(param, "default", None)
    return _sanitise(value)


def _sanitise(value: Any) -> Any:
    if value is None or value is Ellipsis or callable(value):
        return None
    if isinstance(value, _SCALARS):
        return value
    if isinstance(value, enum.Enum):
        return _sanitise(value.value)
    if isinstance(value, PurePath):
        return str(value)
    if isinstance(value, (list, tuple, set, frozenset)):
        return [_sanitise(v) for v in value]
    return repr(value)


def is_group(command: Any) -> bool:
    return callable(getattr(command, "list_commands", None)) and callable(
        getattr(command, "get_command", None)
    )


def _visible(param: Any, config: AgentErrorsConfig) -> bool:
    return config.include_hidden or not getattr(param, "hidden", False)


def _is_argument(param: Any) -> bool:
    return getattr(param, "param_type_name", "") == "argument"


def argument_info(param: Any) -> ArgumentInfo:
    name = str(param.name)
    return ArgumentInfo(
        name=name,
        metavar=str(getattr(param, "metavar", None) or name.upper()),
        type=normalise_type_name(param.type),
        required=bool(getattr(param, "required", False)),
        nargs=int(getattr(param, "nargs", 1) or 1),
        help=getattr(param, "help", None) or None,
        choices=choices_of(param),
    )


def option_info(param: Any) -> OptionInfo:
    primary = list(getattr(param, "opts", []) or [])
    secondary = list(getattr(param, "secondary_opts", []) or [])
    return OptionInfo(
        names=[*primary, *secondary],
        type=normalise_type_name(param.type),
        required=bool(getattr(param, "required", False)),
        default=sanitise_default(param),
        multiple=bool(getattr(param, "multiple", False)),
        is_flag=bool(getattr(param, "is_flag", False)),
        choices=choices_of(param),
        help=getattr(param, "help", None) or None,
        nargs=int(getattr(param, "nargs", 1) or 1),
        primary=primary,
    )


def inventory(
    command: Any, config: AgentErrorsConfig
) -> tuple[list[ArgumentInfo], list[OptionInfo]]:
    """Visible arguments and options of one Click command."""
    arguments: list[ArgumentInfo] = []
    options: list[OptionInfo] = []
    for param in getattr(command, "params", []) or []:
        if not _visible(param, config):
            continue
        if _is_argument(param):
            arguments.append(argument_info(param))
        elif param.name not in _SKIPPED_OPTIONS:
            options.append(option_info(param))
    return arguments, options


def subcommands(group: Any, ctx: Any = None) -> list[SubcommandInfo]:
    """Visible subcommands of a group, with their one-line help."""
    if not is_group(group):
        return []
    result: list[SubcommandInfo] = []
    for name in group.list_commands(ctx):
        sub = group.get_command(ctx, name)
        if sub is None or getattr(sub, "hidden", False):
            continue
        result.append(SubcommandInfo(name=str(name), help=_short_help(sub)))
    return result


def _short_help(command: Any) -> str | None:
    getter = getattr(command, "get_short_help_str", None)
    if callable(getter):
        with contextlib.suppress(Exception):
            return str(getter()) or None
    text = getattr(command, "help", None)
    return str(text).strip().splitlines()[0] if text else None


def resolve_from_argv(
    root: Any, prog_name: str, argv: Sequence[str]
) -> tuple[Any, str]:
    """Walk argv from the root command as far as subcommand names allow.

    Used when the exception carries no context. Never parses options, never
    raises: it stops at the first token that is not a known subcommand.
    """
    command, path = root, prog_name
    for token in _positional_tokens(argv):
        if not is_group(command):
            break
        sub = command.get_command(None, token)
        if sub is None:
            break
        command, path = sub, f"{path} {token}"
    return command, path


def _positional_tokens(argv: Iterable[str]) -> Iterable[str]:
    for arg in argv:
        if arg == END_OF_OPTIONS:
            return
        if not arg.startswith("-"):
            yield arg
