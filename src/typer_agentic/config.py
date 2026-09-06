"""Configuration and pure mode/format resolution."""

from __future__ import annotations

import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

Mode = Literal["auto", "agent", "human"]
ResolvedMode = Literal["agent", "human"]
Format = Literal["markdown", "json"]
Stream = Literal["stderr", "stdout"]

DEFAULT_AGENT_ENV_VARS: tuple[str, ...] = (
    "CLAUDECODE",
    "CLAUDE_CODE",
    "CLAUDE_CODE_ENTRYPOINT",
    "CODEX",
    "CODEX_CLI",
    "CURSOR",
    "CURSOR_SESSION_ID",
    "OPENCODE",
    "AGENT",
)
"""Environment variables whose presence marks an agent-driven session."""

END_OF_OPTIONS = "--"
_FALSY = frozenset({"", "0", "false", "no", "off"})
_FORMATS: frozenset[str] = frozenset({"markdown", "json"})


@dataclass(frozen=True)
class AgentErrorsConfig:
    """Behaviour knobs for :func:`typer_agentic.agent_errors`."""

    mode: Mode = "auto"
    format: Format = "markdown"
    stream: Stream = "stderr"
    env_var: str = "AGENT_ERRORS"
    format_env_var: str = "AGENT_ERRORS_FORMAT"
    flag: str | None = "--agent-errors"
    human_flag: str | None = "--human-errors"
    skill_flag: str | None = "--agent-skill"
    max_suggestions: int = 3
    include_hidden: bool = False
    tty_heuristic: bool = False
    agent_detect_env_vars: tuple[str, ...] = DEFAULT_AGENT_ENV_VARS
    intercept_click_exceptions: bool = False
    repeat_detection: bool = False
    repeat_state_dir: Path | None = None


@dataclass(frozen=True)
class ArgvScan:
    """Result of pre-scanning argv for sentinel flags."""

    args: list[str]
    agent_flag: bool = False
    human_flag: bool = False
    skill_flag: bool = False


def scan_argv(config: AgentErrorsConfig, argv: Sequence[str]) -> ArgvScan:
    """Find and strip sentinel flags; tokens after ``--`` are left alone."""
    sentinels = {
        name: flag
        for name, flag in (
            ("agent_flag", config.flag),
            ("human_flag", config.human_flag),
            ("skill_flag", config.skill_flag),
        )
        if flag
    }
    found: dict[str, bool] = {}
    kept: list[str] = []
    passthrough = False
    for arg in argv:
        if passthrough:
            kept.append(arg)
            continue
        if arg == END_OF_OPTIONS:
            passthrough = True
            kept.append(arg)
            continue
        hit = next((n for n, f in sentinels.items() if f == arg), None)
        if hit is None:
            kept.append(arg)
        else:
            found[hit] = True
    return ArgvScan(args=kept, **found)


def _is_truthy(value: str) -> bool:
    return value.strip().lower() not in _FALSY


def resolve_mode(  # noqa: PLR0911 - a precedence chain
    config: AgentErrorsConfig,
    argv: Sequence[str],
    environ: Mapping[str, str],
    *,
    scan: ArgvScan | None = None,
    stderr_isatty: bool | None = None,
) -> ResolvedMode:
    """Decide agent vs human output. Pure; see the README precedence table.

    Pass ``scan`` to reuse an existing :func:`scan_argv` result.
    """
    if config.mode in ("agent", "human"):
        return config.mode
    if scan is None:
        scan = scan_argv(config, argv)
    if scan.agent_flag:
        return "agent"
    if scan.human_flag:
        return "human"
    toggle = environ.get(config.env_var)
    if toggle is not None:
        return "agent" if _is_truthy(toggle) else "human"
    if any(environ.get(name) for name in config.agent_detect_env_vars):
        return "agent"
    if config.tty_heuristic:
        if stderr_isatty is None:
            stderr_isatty = sys.stderr.isatty()
        if not stderr_isatty:
            return "agent"
    return "human"


def resolve_format(config: AgentErrorsConfig, environ: Mapping[str, str]) -> Format:
    """Wire format for agent mode; unknown env values fall back to markdown."""
    override = environ.get(config.format_env_var, "").strip().lower()
    if override in _FORMATS:
        return "json" if override == "json" else "markdown"
    return config.format if config.format in _FORMATS else "markdown"
