from __future__ import annotations

import json
import os
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

import pytest
import typer

from typer_agentic import AgentErrorsConfig, compat

from . import fixture_app

PROG = "myapp"
VENDORED_CLICK = bool(compat.STATUS.sources) and compat.STATUS.sources[0].startswith(
    "typer._click"
)
golden_only = pytest.mark.skipif(
    not VENDORED_CLICK, reason="golden files use Typer >= 0.26 (vendored Click) wording"
)
GOLDEN_DIR = Path(__file__).parent / "golden"

AGENT_ENV_VARS = (
    "AGENT_ERRORS",
    "AGENT_ERRORS_FORMAT",
    "CLAUDECODE",
    "CLAUDE_CODE",
    "CLAUDE_CODE_ENTRYPOINT",
    "CODEX",
    "CODEX_CLI",
    "CURSOR",
    "CURSOR_SESSION_ID",
    "OPENCODE",
    "AGENT",
    "TYPER_USE_RICH",
)


@dataclass
class CliResult:
    code: int
    out: str
    err: str


@pytest.fixture(autouse=True)
def _clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in AGENT_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


@pytest.fixture
def run(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> Callable[..., CliResult]:
    """Invoke the wrapped fixture app with a patched ``sys.argv``."""

    def _run(
        argv: Sequence[str],
        *,
        config: AgentErrorsConfig | None = None,
        env: dict[str, str] | None = None,
        main: Callable[[], object] | None = None,
    ) -> CliResult:
        for key, value in (env or {}).items():
            monkeypatch.setenv(key, value)
        monkeypatch.setattr(sys, "argv", [PROG, *argv])
        capsys.readouterr()
        entry = main or fixture_app.build_main(config)
        with pytest.raises(SystemExit) as info:
            entry()
        captured = capsys.readouterr()
        code = info.value.code
        return CliResult(
            code=0 if code is None else int(code), out=captured.out, err=captured.err
        )

    return _run


JSON_AGENT = AgentErrorsConfig(mode="agent", format="json")


@pytest.fixture
def json_payload(run: Callable[..., CliResult]) -> Callable[..., dict]:
    """Run in agent/json mode and return the parsed payload from stderr."""

    def _payload(argv: Sequence[str], config: AgentErrorsConfig = JSON_AGENT) -> dict:
        return json.loads(run(argv, config=config).err)

    return _payload


def app_raising(exc: BaseException) -> typer.Typer:
    """A one-command Typer app whose only command raises ``exc``."""
    app = typer.Typer()

    @app.command()
    def only() -> None:
        raise exc

    return app


@pytest.fixture
def agent() -> AgentErrorsConfig:
    return AgentErrorsConfig(mode="agent")


def golden(name: str, actual: str) -> None:
    """Compare against ``tests/golden/<name>``; ``UPDATE_GOLDEN=1`` rewrites."""
    path = GOLDEN_DIR / name
    if os.environ.get("UPDATE_GOLDEN") == "1":
        path.write_text(actual, encoding="utf-8")
    expected = path.read_text(encoding="utf-8")
    assert actual == expected, f"golden mismatch: {path} (UPDATE_GOLDEN=1 to rewrite)"
