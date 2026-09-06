"""SKILL.md emitter (M7): the whole CLI inventory, before the first failure."""

from __future__ import annotations

from typing import Any

from . import compat, introspect, wording
from .config import AgentErrorsConfig
from .example import build_example
from .payload import ArgumentInfo, OptionInfo
from .render.markdown import align, option_names, option_type_label, type_label

MAX_FULL_COMMANDS = 10
MAX_DESCRIPTION = 1024  # Agent Skills frontmatter limit for `description`


def _help_text(command: Any) -> str:
    text = getattr(command, "help", None) or ""
    return str(text).strip()


def _first_line(text: str) -> str:
    return text.splitlines()[0].strip() if text.strip() else ""


def _walk(command: Any, path: str) -> list[tuple[str, Any]]:
    """Depth-first (path, command) for every visible leaf command."""
    if not introspect.is_group(command):
        return [(path, command)]
    found: list[tuple[str, Any]] = []
    for name in command.list_commands(None):
        sub = command.get_command(None, name)
        if sub is None or getattr(sub, "hidden", False):
            continue
        found.extend(_walk(sub, f"{path} {name}"))
    return found


def _arguments_block(arguments: list[ArgumentInfo]) -> list[str]:
    if not arguments:
        return []
    rows = (
        (
            a.metavar,
            type_label(a.type, a.choices),
            "required" if a.required else "optional",
            a.help or "",
        )
        for a in arguments
    )
    return ["Arguments:", *align(rows)]


def _options_block(options: list[OptionInfo]) -> list[str]:
    if not options:
        return []
    rows = ((option_names(o), option_type_label(o), o.help or "") for o in options)
    return ["Options:", *align(rows)]


def _command_section(path: str, command: Any, config: AgentErrorsConfig) -> list[str]:
    arguments, options = introspect.inventory(command, config)
    lines = [f"### {path}"]
    help_text = _help_text(command)
    if help_text:
        lines += ["", help_text]
    for block in (_arguments_block(arguments), _options_block(options)):
        if block:
            lines += ["", *block]
    lines += ["", "Example:", "", "```", build_example(path, arguments, options), "```"]
    return lines


def _yaml_scalar(text: str) -> str:
    """Double-quoted YAML scalar; escapes backslashes, quotes and newlines."""
    escaped = (
        text.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
    )
    return f'"{escaped}"'


def render_skill(
    app: Any,
    *,
    name: str | None = None,
    description: str | None = None,
    config: AgentErrorsConfig | None = None,
    prog_name: str | None = None,
) -> str:
    """Pure: return a SKILL.md for ``app``. Never writes to disk."""
    cfg = config or AgentErrorsConfig()
    root = compat.get_command(app)
    prog = prog_name or compat.detect_program_name()
    app_help = _help_text(root)
    skill_name = name or prog
    skill_description = (
        description or _first_line(app_help) or f"Use the {prog} CLI."
    )[:MAX_DESCRIPTION]
    lines = [
        "---",
        f"name: {_yaml_scalar(skill_name)}",
        f"description: {_yaml_scalar(skill_description)}",
        "---",
        "",
        f"# {prog}",
        "",
        wording.SKILL_WHEN_TO_USE,
        "",
        app_help or f"Use `{prog}` for the commands listed below.",
        "",
        wording.SKILL_COMMANDS,
    ]
    commands = _walk(root, prog)
    if len(commands) > MAX_FULL_COMMANDS:
        lines += [
            "",
            wording.SKILL_TOO_MANY.format(count=len(commands), command_path=prog),
        ]
        lines += [
            "",
            *align((path, _first_line(_help_text(c))) for path, c in commands),
        ]
    else:
        for path, command in commands:
            lines += ["", *_command_section(path, command, cfg)]
    lines += [
        "",
        wording.SKILL_ON_ERRORS,
        "",
        f"{wording.CLASSIFICATION} {wording.DIRECTIVE} {wording.EXAMPLE_NOTE}",
        "",
    ]
    return "\n".join(lines)
