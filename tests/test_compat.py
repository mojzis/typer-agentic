"""§4.1 resolution and the passthrough guarantee (spec test 17)."""

from __future__ import annotations

import importlib
import warnings
from types import ModuleType

import pytest

from typer_agentic import AgentErrorsConfig, CompatStatus, compat, is_usage_error

from . import fixture_app
from .conftest import CliResult


def test_status_ok_in_supported_env() -> None:
    assert compat.STATUS.ok
    assert compat.STATUS.get("UsageError")
    assert compat.STATUS.get("Exit") and compat.STATUS.get("Abort")


def test_resolve_prefers_vendored_then_click() -> None:
    status = compat.resolve()
    assert status.sources[0] in ("typer._click.exceptions", "click.exceptions")


def test_resolve_collects_both_hierarchies_when_present() -> None:
    fake_a, fake_b = ModuleType("a"), ModuleType("b")
    for mod in (fake_a, fake_b):
        for name in compat._REQUIRED:
            setattr(mod, name, type(name, (Exception,), {}))

    def importer(name: str) -> ModuleType:
        if name == "typer._click.exceptions":
            return fake_a
        if name == "click.exceptions":
            return fake_b
        raise ImportError(name)

    status = compat.resolve(import_module=importer)
    assert status.ok
    assert status.sources == ("typer._click.exceptions", "click.exceptions")
    assert len(status.get("UsageError")) == 2
    assert status.get("NoArgsIsHelpError") == ()


def test_resolve_failure_is_reported_not_raised() -> None:
    def importer(name: str) -> ModuleType:
        raise ImportError(f"nope {name}")

    status = compat.resolve(import_module=importer)
    assert not status.ok
    assert "nope" in status.reason
    assert status.get("UsageError") == ()


def test_resolve_missing_required_name_degrades() -> None:
    partial = ModuleType("partial")
    partial.UsageError = type("UsageError", (Exception,), {})  # ty: ignore[unresolved-attribute]

    def importer(name: str) -> ModuleType:
        if name == "typer":
            raise ImportError(name)
        return partial

    status = compat.resolve(import_module=importer)
    assert not status.ok
    assert "missing" in status.reason


def test_is_usage_error() -> None:
    usage_error = compat.STATUS.get("UsageError")[0]
    assert is_usage_error(usage_error("x"))
    assert not is_usage_error(ValueError("x"))


def test_detect_program_name_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    real_import = importlib.import_module

    def no_click(name: str) -> ModuleType:
        if name.endswith(".utils"):
            raise ImportError(name)
        return real_import(name)

    monkeypatch.setattr(importlib, "import_module", no_click)
    monkeypatch.setattr("sys.argv", ["/usr/bin/mytool"])
    assert compat.detect_program_name() == "mytool"


@pytest.fixture
def broken_compat(monkeypatch: pytest.MonkeyPatch) -> CompatStatus:
    status = CompatStatus(ok=False, reason="simulated import failure")
    monkeypatch.setattr(compat, "STATUS", status)
    monkeypatch.setattr(compat, "_warned", False)
    return status


def test_passthrough_when_unresolvable_agent_mode(
    run, broken_compat: CompatStatus
) -> None:
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        result: CliResult = run(
            ["sync", "--verbos"], config=AgentErrorsConfig(mode="agent")
        )
    runtime = [w for w in caught if issubclass(w.category, RuntimeWarning)]
    assert len(runtime) == 1
    assert "simulated import failure" in str(runtime[0].message)
    assert result.code == 2
    assert "✗ Usage error" not in result.err
    assert "--verbos" in result.err


def test_passthrough_warns_only_once(run, broken_compat: CompatStatus) -> None:
    cfg = AgentErrorsConfig(mode="agent")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        run(["sync", "--verbos"], config=cfg)
        run(["sync", "--verbos"], config=cfg)
    assert len([w for w in caught if issubclass(w.category, RuntimeWarning)]) == 1


def test_passthrough_silent_in_human_mode(run, broken_compat: CompatStatus) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        result: CliResult = run(["sync", "./x"], config=AgentErrorsConfig(mode="human"))
    assert result.code == 0
    assert "synced" in result.out


def test_user_cli_still_works_when_unresolvable(
    run, broken_compat: CompatStatus
) -> None:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        result: CliResult = run(
            ["sync", "./x", "-v"], config=AgentErrorsConfig(mode="agent")
        )
    assert result.code == 0
    assert "synced x True" in result.out


def test_wrap_never_raises_when_unresolvable(broken_compat: CompatStatus) -> None:
    assert callable(fixture_app.build_main(AgentErrorsConfig(mode="agent")))
