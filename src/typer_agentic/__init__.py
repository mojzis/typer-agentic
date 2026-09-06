"""typer-agentic: a Typer extension that makes CLIs friendly to coding agents.

Wrap an app with :func:`agent_errors` and usage errors become compact,
corrective blocks when an agent is driving the CLI. Humans see Typer's
own output, untouched.
"""

from __future__ import annotations

from .compat import CompatStatus, is_usage_error
from .config import (
    DEFAULT_AGENT_ENV_VARS,
    AgentErrorsConfig,
    resolve_format,
    resolve_mode,
    scan_argv,
)
from .intercept import agent_errors
from .payload import (
    SCHEMA,
    ArgumentInfo,
    ErrorInfo,
    ErrorPayload,
    OptionInfo,
    RecoveryCopy,
    SubcommandInfo,
)
from .render import render, render_json, render_markdown
from .skill import render_skill

__all__ = [
    "DEFAULT_AGENT_ENV_VARS",
    "SCHEMA",
    "AgentErrorsConfig",
    "ArgumentInfo",
    "CompatStatus",
    "ErrorInfo",
    "ErrorPayload",
    "OptionInfo",
    "RecoveryCopy",
    "SubcommandInfo",
    "agent_errors",
    "is_usage_error",
    "render",
    "render_json",
    "render_markdown",
    "render_skill",
    "resolve_format",
    "resolve_mode",
    "scan_argv",
]
