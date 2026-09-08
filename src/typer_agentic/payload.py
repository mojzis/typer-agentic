"""The format-agnostic error model. Renderers are dumb views over it."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

SCHEMA = "typer-agentic/v1"

ErrorType = Literal[
    "no_such_option",
    "bad_parameter",
    "missing_parameter",
    "bad_option_usage",
    "bad_argument_usage",
    "no_such_command",
    "missing_command",
    "usage_error",
    "click_exception",
]


@dataclass(frozen=True)
class ErrorInfo:
    type: ErrorType
    message: str
    offending: str | None = None
    param: str | None = None


@dataclass(frozen=True)
class RangeInfo:
    """Bounds of a Click ``IntRange``/``FloatRange``; ``None`` means unbounded."""

    min: int | float | None = None
    max: int | float | None = None
    min_open: bool = False
    max_open: bool = False


@dataclass(frozen=True)
class ArgumentInfo:
    name: str
    metavar: str
    type: str
    required: bool
    nargs: int
    help: str | None = None
    choices: list[str] | None = None
    range: RangeInfo | None = None


@dataclass(frozen=True)
class OptionInfo:
    names: list[str]
    type: str
    required: bool
    default: Any = None
    multiple: bool = False
    is_flag: bool = False
    choices: list[str] | None = None
    help: str | None = None
    nargs: int = 1
    range: RangeInfo | None = None
    primary: list[str] = field(default_factory=list)
    """The ``opts`` subset of ``names`` (excludes ``--no-*`` secondaries)."""


@dataclass(frozen=True)
class SubcommandInfo:
    name: str
    help: str | None = None


@dataclass(frozen=True)
class RecoveryCopy:
    classification: str
    directive: str
    action: str
    escalation: str | None = None


@dataclass(frozen=True)
class ErrorPayload:
    error: ErrorInfo
    command_path: str
    recovery: RecoveryCopy
    exit_code: int
    schema: str = SCHEMA
    suggestions: list[str] = field(default_factory=list)
    valid_arguments: list[ArgumentInfo] = field(default_factory=list)
    valid_options: list[OptionInfo] = field(default_factory=list)
    subcommands: list[SubcommandInfo] | None = None
    example: str | None = None

    @property
    def best(self) -> str | None:
        return self.suggestions[0] if self.suggestions else None

    def to_dict(self) -> dict[str, Any]:
        """JSON-ready mapping. Field names mirror the dataclasses, except that
        ``OptionInfo.primary`` (a render-time helper) is omitted."""
        data = asdict(self)
        for option in data["valid_options"]:
            option.pop("primary", None)
        return data
