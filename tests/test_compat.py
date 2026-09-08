"""§4.1 resolution and the passthrough guarantee (spec test 17)."""

from __future__ import annotations

import importlib
import subprocess
import sys
import warnings
from types import ModuleType

import pytest

from typer_agentic import AgentErrorsConfig, CompatStatus, compat, is_usage_error

from . import fixture_app
from .conftest import VENDORED_CLICK, CliResult


def test_status_ok_in_supported_env() -> None:
    assert compat.STATUS.ok
    assert compat.STATUS.get("UsageError")
    assert compat.STATUS.get("Exit") and compat.STATUS.get("Abort")


def test_resolve_prefers_vendored_then_click() -> None:
    status = compat.resolve()
    assert status.sources[0] in ("typer._click.exceptions", "click.exceptions")


def _fake_hierarchy(name: str) -> ModuleType:
    """A module carrying every required exception name as its own class."""
    mod = ModuleType(name)
    for class_name in compat._REQUIRED:
        setattr(mod, class_name, type(class_name, (Exception,), {}))
    return mod


def test_resolve_collects_both_hierarchies_when_present() -> None:
    fake_a, fake_b = _fake_hierarchy("a"), _fake_hierarchy("b")

    def importer(name: str) -> ModuleType:
        if name == "typer._click.exceptions":
            return fake_a
        if name == "click.exceptions":
            return fake_b
        raise ImportError(name)

    status = compat.resolve(import_module=importer, modules={"click": fake_b})
    assert status.ok
    assert status.sources == ("typer._click.exceptions", "click.exceptions")
    assert len(status.get("UsageError")) == 2
    assert status.get("NoArgsIsHelpError") == ()


def test_resolve_skips_external_click_unless_already_imported() -> None:
    fake_a, fake_b = _fake_hierarchy("a"), _fake_hierarchy("b")
    seen: list[str] = []

    def importer(name: str) -> ModuleType:
        seen.append(name)
        if name == "typer._click.exceptions":
            return fake_a
        if name == "click.exceptions":
            return fake_b
        raise ImportError(name)

    status = compat.resolve(import_module=importer, modules={})
    assert status.ok
    assert status.sources == ("typer._click.exceptions",)
    assert "click.exceptions" not in seen


def test_resolve_falls_back_to_external_click_without_vendored() -> None:
    fake_b = _fake_hierarchy("b")

    def importer(name: str) -> ModuleType:
        if name == "click.exceptions":
            return fake_b
        raise ImportError(name)

    status = compat.resolve(import_module=importer, modules={})
    assert status.ok
    assert status.sources == ("click.exceptions",)


def test_current_picks_up_click_imported_later(monkeypatch: pytest.MonkeyPatch) -> None:
    vendored_only = CompatStatus(
        ok=True, sources=("typer._click.exceptions",), classes=compat.STATUS.classes
    )
    monkeypatch.setattr(compat, "STATUS", vendored_only)
    fake = _fake_hierarchy("click.exceptions")
    monkeypatch.setitem(sys.modules, "click", ModuleType("click"))
    monkeypatch.setitem(sys.modules, "click.exceptions", fake)
    status = compat.current()
    assert "click.exceptions" in status.sources
    assert fake.UsageError in status.get("UsageError")
    assert compat.current() is status


@pytest.mark.skipif(not VENDORED_CLICK, reason="needs a vendored hierarchy to keep")
def test_current_tries_unusable_external_click_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    vendored_only = CompatStatus(
        ok=True,
        sources=("typer._click.exceptions",),
        classes=compat.STATUS.classes,
        tried=("typer._click.exceptions",),
    )
    monkeypatch.setattr(compat, "STATUS", vendored_only)
    monkeypatch.setitem(sys.modules, "click", ModuleType("click"))
    monkeypatch.setitem(sys.modules, "click.exceptions", ModuleType("click.exceptions"))
    calls: list[int] = []
    real_resolve = compat.resolve

    def counting_resolve(*args, **kwargs) -> CompatStatus:
        calls.append(1)
        return real_resolve(*args, **kwargs)

    monkeypatch.setattr(compat, "resolve", counting_resolve)
    first = compat.current()
    assert compat.current() is first
    assert first.sources == ("typer._click.exceptions",)
    assert "click.exceptions" in first.tried
    assert len(calls) == 1


def test_current_leaves_broken_status_alone(broken_compat: CompatStatus) -> None:
    assert compat.current() is broken_compat


@pytest.mark.skipif(not VENDORED_CLICK, reason="Typer < 0.26 imports click itself")
def test_import_does_not_load_external_click() -> None:
    code = "import sys, typer_agentic; print('click' in sys.modules)"
    out = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, check=True
    ).stdout
    assert out.strip() == "False"


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
    assert len(runtime) == 1, "exactly one RuntimeWarning"
    assert "simulated import failure" in str(runtime[0].message), "warning names cause"
    assert result.code == 2, "usage error exit code preserved"
    assert "✗ Usage error" not in result.err, "no agent block"
    assert "--verbos" in result.err, "Typer's own message shown"


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
