"""Synthesise the one corrected example invocation."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .payload import ArgumentInfo, OptionInfo, RangeInfo


@dataclass(frozen=True)
class Fix:
    """The corrected form of the offending option: which one, with what value."""

    option: OptionInfo | None
    value: str | None = None


REPEAT_TWICE = 2

_PLACEHOLDERS = {
    "INTEGER": "1",
    "INTEGER RANGE": "1",
    "FLOAT": "1.0",
    "FLOAT RANGE": "1.0",
    "TEXT": "VALUE",
    "PATH": "./PATH",
    "FILE": "./PATH",
    "DIRECTORY": "./PATH",
    "UUID": "00000000-0000-0000-0000-000000000000",
    "DATETIME": "2024-01-01",
    "BOOL": "true",
}


def placeholder(
    type_name: str,
    *,
    choices: list[str] | None = None,
    bounds: RangeInfo | None = None,
) -> str:
    if choices:
        return choices[0]
    if bounds is not None and (in_range := _in_range(bounds)) is not None:
        return str(in_range)
    return _PLACEHOLDERS.get(type_name, "VALUE")


def _in_range(bounds: RangeInfo) -> int | float | None:
    """A value known to satisfy the bounds, or ``None`` if none is certain."""
    if bounds.min is not None and not bounds.min_open:
        return bounds.min
    if bounds.max is not None and not bounds.max_open:
        return bounds.max
    if isinstance(bounds.min, int) and (
        bounds.max is None or bounds.min + 1 < bounds.max
    ):
        return bounds.min + 1
    return None


def option_tokens(opt: OptionInfo, value: str | None = None) -> list[str]:
    """Tokens for one option: bare flag, or name plus placeholder value(s)."""
    name = opt.primary[0] if opt.primary else opt.names[0]
    if opt.is_flag and value is None:
        return [name]
    values = [value or placeholder(opt.type, choices=opt.choices, bounds=opt.range)]
    values *= max(opt.nargs, 1)
    tokens = [name, *values]
    # A repeatable option is shown twice so the agent sees it can repeat.
    return tokens * REPEAT_TWICE if opt.multiple and value is None else tokens


def argument_tokens(arg: ArgumentInfo) -> list[str]:
    value = placeholder(arg.type, choices=arg.choices, bounds=arg.range)
    # Variadic (nargs=-1) arguments are shown twice to signal repetition.
    count = arg.nargs if arg.nargs > 0 else REPEAT_TWICE
    return [value] * count


def build_example(
    command_path: str,
    arguments: list[ArgumentInfo],
    options: list[OptionInfo],
    *,
    fix: Fix | None = None,
    extra: Sequence[str] = (),
) -> str:
    """``command_path`` + required params + the corrected form of the fix."""
    fix_option = fix.option if fix else None
    fix_value = fix.value if fix else None
    tokens: list[str] = [command_path]
    for arg in arguments:
        if arg.required:
            tokens.extend(argument_tokens(arg))
    for opt in options:
        if opt is fix_option:
            tokens.extend(option_tokens(opt, fix_value))
        elif opt.required:
            tokens.extend(option_tokens(opt))
    if fix_option is not None and not any(o is fix_option for o in options):
        tokens.extend(option_tokens(fix_option, fix_value))
    tokens.extend(extra)
    return " ".join(tokens)
