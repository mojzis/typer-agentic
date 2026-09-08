"""Resolve Click exception classes regardless of where Typer keeps Click.

Typer >= 0.26 vendors Click as ``typer._click``; its exception classes are
unrelated by inheritance to ``click.exceptions``. Older Typer raises the
external Click classes. This module is the only place that knows about either.
Resolution failure never raises: ``STATUS.ok`` becomes ``False`` and the
wrapper degrades to a transparent passthrough.
"""

from __future__ import annotations

import importlib
import sys
import warnings
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType
from typing import Any

from typer.main import get_command as _typer_get_command

_DevConfig: Any = None
_DEV_ATTR: str = ""
_typer_except_hook: Any = None
try:
    from typer.main import (
        DeveloperExceptionConfig,
        _typer_developer_exception_attr_name,
        except_hook,
    )
except ImportError:  # pragma: no cover - a Typer without the pretty hook
    pass
else:
    _DevConfig = DeveloperExceptionConfig
    _DEV_ATTR = _typer_developer_exception_attr_name
    _typer_except_hook = except_hook

_VENDORED = "typer._click.exceptions"
_EXTERNAL = "click.exceptions"
_EXTERNAL_PACKAGE = "click"
_EXCEPTION_MODULES = (_VENDORED, _EXTERNAL)
_REQUIRED = (
    "UsageError",
    "BadParameter",
    "MissingParameter",
    "NoSuchOption",
    "BadOptionUsage",
    "BadArgumentUsage",
    "ClickException",
)
_OPTIONAL = ("NoArgsIsHelpError", "NoSuchCommand", "Exit", "Abort")
_ALL_NAMES = (*_REQUIRED, *_OPTIONAL)


@dataclass(frozen=True)
class CompatStatus:
    """Outcome of resolving Click's exception hierarchy."""

    ok: bool
    reason: str = ""
    sources: tuple[str, ...] = ()
    classes: dict[str, tuple[type[BaseException], ...]] = field(default_factory=dict)
    tried: tuple[str, ...] = ()
    """Every module resolution attempted, whether or not it was usable."""

    def get(self, name: str) -> tuple[type[BaseException], ...]:
        """Every resolvable class with this name, across all hierarchies."""
        return self.classes.get(name, ())


def resolve(
    import_module: Callable[[str], ModuleType] = importlib.import_module,
    *,
    modules: Mapping[str, Any] = sys.modules,
) -> CompatStatus:
    """Collect exception classes from every relevant Click hierarchy.

    External ``click`` is imported only when Typer does not vendor Click or
    when something else already imported it (``modules``): a Typer >= 0.26
    app never raises external Click exceptions on its own.
    """
    classes: dict[str, list[type[BaseException]]] = {n: [] for n in _ALL_NAMES}
    sources: list[str] = []
    tried: list[str] = []
    problems: list[str] = []
    for modname in _EXCEPTION_MODULES:
        if modname == _EXTERNAL and sources and _EXTERNAL_PACKAGE not in modules:
            continue
        tried.append(modname)
        try:
            mod = import_module(modname)
        except Exception as exc:
            problems.append(f"{modname}: {exc!r}")
            continue
        missing = [n for n in _REQUIRED if not hasattr(mod, n)]
        if missing:
            problems.append(f"{modname}: missing {', '.join(missing)}")
            continue
        sources.append(modname)
        for name in _ALL_NAMES:
            cls = getattr(mod, name, None)
            if isinstance(cls, type) and cls not in classes[name]:
                classes[name].append(cls)
    for name in ("Exit", "Abort"):
        cls = _typer_signal(name, import_module)
        if cls is not None and cls not in classes[name]:
            classes[name].append(cls)
    if not sources:
        return CompatStatus(ok=False, reason="; ".join(problems), tried=tuple(tried))
    return CompatStatus(
        ok=True,
        sources=tuple(sources),
        classes={n: tuple(v) for n, v in classes.items()},
        tried=tuple(tried),
    )


def _typer_signal(
    name: str, import_module: Callable[[str], ModuleType]
) -> type[BaseException] | None:
    try:
        cls = getattr(import_module("typer"), name, None)
    except Exception:
        return None
    return cls if isinstance(cls, type) else None


STATUS: CompatStatus = resolve()


def current() -> CompatStatus:
    """``STATUS``, re-resolved once external ``click`` shows up after import."""
    global STATUS  # noqa: PLW0603 - lazy pickup of a late external-click import
    if STATUS.ok and _EXTERNAL not in STATUS.tried and _EXTERNAL_PACKAGE in sys.modules:
        STATUS = resolve()
    return STATUS


def is_usage_error(exc: BaseException) -> bool:
    """True if ``exc`` is a UsageError from any resolvable Click hierarchy."""
    return isinstance(exc, current().get("UsageError"))


def get_command(app: Any) -> Any:
    """Typer's ``get_command``: build the Click command tree for an app."""
    return _typer_get_command(app)


def detect_program_name() -> str:
    """Program name the way Click would detect it, with a plain fallback."""
    for modname in ("typer._click.utils", "click.utils"):
        try:
            detect = importlib.import_module(modname)._detect_program_name
        except (ImportError, AttributeError):
            continue
        try:
            return str(detect())
        except Exception:
            break
    return Path(sys.argv[0]).name if sys.argv and sys.argv[0] else "cli"


def install_pretty_exceptions() -> None:
    """Mirror ``Typer.__call__``: route uncaught exceptions to Typer's hook."""
    if _typer_except_hook is not None and sys.excepthook is not _typer_except_hook:
        sys.excepthook = _typer_except_hook


def tag_developer_exception(app: Any, exc: BaseException) -> None:
    """Attach Typer's pretty-exception config so its excepthook renders it."""
    if _DevConfig is None:
        return
    try:
        setattr(
            exc,
            _DEV_ATTR,
            _DevConfig(
                pretty_exceptions_enable=app.pretty_exceptions_enable,
                pretty_exceptions_show_locals=app.pretty_exceptions_show_locals,
                pretty_exceptions_short=app.pretty_exceptions_short,
            ),
        )
    except Exception:
        return


_warned = False


def warn_unsupported_once(status: CompatStatus) -> None:
    """Emit one RuntimeWarning per process when interception is unavailable."""
    global _warned  # noqa: PLW0603 - once-per-process guard
    if _warned:
        return
    _warned = True
    warnings.warn(
        "typer-agentic: could not resolve Click exception classes "
        f"({status.reason}); usage errors are passed through unchanged.",
        RuntimeWarning,
        stacklevel=3,
    )
