"""Markdown renderer (default). Plain text, no ANSI, no box-drawing."""

from __future__ import annotations

from collections.abc import Iterable, Sequence

from .. import wording
from ..introspect import RANGE_SUFFIX
from ..payload import (
    ArgumentInfo,
    ErrorPayload,
    OptionInfo,
    RangeInfo,
    SubcommandInfo,
)

MAX_OPTIONS = 20
INDENT = "  "
EXAMPLE_INDENT = "    "


def type_label(
    type_name: str,
    *,
    choices: list[str] | None = None,
    bounds: RangeInfo | None = None,
) -> str:
    """``CHOICE[a|b]``, ``INTEGER[1..365]`` or the bare normalised type name."""
    if choices:
        return f"CHOICE[{'|'.join(choices)}]"
    if bounds is not None:
        low = _endpoint(bounds.min, bounds.min_open, ">")
        high = _endpoint(bounds.max, bounds.max_open, "<")
        return f"{type_name.removesuffix(RANGE_SUFFIX)}[{low}..{high}]"
    return type_name


def _endpoint(value: int | float | None, is_open: bool, marker: str) -> str:
    return "" if value is None else f"{marker if is_open else ''}{value}"


def option_names(opt: OptionInfo) -> str:
    return ", ".join(opt.names)


def option_type_label(opt: OptionInfo) -> str:
    if opt.is_flag and not opt.choices:
        return "flag"
    label = type_label(opt.type, choices=opt.choices, bounds=opt.range)
    return f"{label} (required)" if opt.required else label


def align(rows: Iterable[Sequence[str]]) -> list[str]:
    """Left-align columns; trailing empty cells are dropped."""
    rows = [list(r) for r in rows]
    if not rows:
        return []
    width = max(len(r) for r in rows)
    widths = [max(len(r[i]) if i < len(r) else 0 for r in rows) for i in range(width)]
    lines = []
    for row in rows:
        cells = [
            cell.ljust(widths[i]) if i < len(row) - 1 else cell
            for i, cell in enumerate(row)
        ]
        lines.append(INDENT + "  ".join(cells).rstrip())
    return lines


def _rank_options(payload: ErrorPayload) -> list[OptionInfo]:
    suggested = set(payload.suggestions)

    def key(opt: OptionInfo) -> tuple[int, int, str]:
        hit = 0 if suggested & set(opt.names) else 1
        return (hit, 0 if opt.required else 1, opt.names[0].lstrip("-").lower())

    return sorted(payload.valid_options, key=key)


def _options_section(payload: ErrorPayload) -> list[str]:
    """Declaration order normally; relevance-ranked only when truncating."""
    options = payload.valid_options
    if not options:
        return []
    if len(options) > MAX_OPTIONS:
        shown, hidden = _rank_options(payload)[:MAX_OPTIONS], len(options) - MAX_OPTIONS
    else:
        shown, hidden = options, 0
    lines = [wording.OPTIONS_HEADING]
    lines += align((option_names(o), option_type_label(o), o.help or "") for o in shown)
    if hidden:
        lines.append(
            wording.OPTIONS_TRUNCATED.format(
                count=hidden, command_path=payload.command_path
            )
        )
    return lines


def _argument_line(args: list[ArgumentInfo], *, required: bool) -> list[str]:
    picked = [a for a in args if a.required == required]
    if not picked:
        return []
    heading = (
        wording.ARGUMENTS_HEADING if required else wording.OPTIONAL_ARGUMENTS_HEADING
    )
    return [heading.format(names=", ".join(argument_label(a) for a in picked))]


def argument_label(arg: ArgumentInfo) -> str:
    """``PATH`` when the metavar already says the type, else ``NAME (TYPE)``."""
    label = type_label(arg.type, choices=arg.choices, bounds=arg.range)
    return arg.metavar if label == arg.metavar else f"{arg.metavar} ({label})"


def _subcommands_section(subs: list[SubcommandInfo] | None) -> list[str]:
    if not subs:
        return []
    return [wording.SUBCOMMANDS_HEADING, *align((s.name, s.help or "") for s in subs)]


def _paragraphs(payload: ErrorPayload) -> list[list[str]]:
    header = wording.HEADER.format(
        command_path=payload.command_path, message=payload.error.message
    )
    framing = [f"{payload.recovery.classification} {payload.recovery.directive}"]
    blocks: list[list[str]] = [[header], framing]
    if payload.recovery.escalation:
        blocks.append([payload.recovery.escalation])
    if payload.best:
        blocks.append([wording.DID_YOU_MEAN.format(best=payload.best)])
    fix = [wording.FIX_HEADING.format(action=payload.recovery.action)]
    if payload.example:
        fix += ["", "```", payload.example, "```"]
    blocks.append(fix)
    blocks.append(_subcommands_section(payload.subcommands))
    blocks.append(_options_section(payload))
    blocks.append(_argument_line(payload.valid_arguments, required=True))
    blocks.append(_argument_line(payload.valid_arguments, required=False))
    blocks.append([wording.FOOTER.format(command_path=payload.command_path)])
    return [b for b in blocks if b]


def render_markdown(payload: ErrorPayload) -> str:
    return "\n\n".join("\n".join(block) for block in _paragraphs(payload)) + "\n"
