"""§4.2 invocation loop (spec tests 7, 8, 10, 11, 12, no_args_is_help)."""

from __future__ import annotations

import json
import sys
from typing import Any

import pytest

from typer_agentic import AgentErrorsConfig, agent_errors, compat, intercept
from typer_agentic.config import Mode

from . import fixture_app
from .conftest import CliResult, app_raising

SENTINEL = "✗ Usage error in `myapp sync`"


def test_help_in_agent_mode_is_untouched(run, agent) -> None:
    result: CliResult = run(["sync", "--help"], config=agent)
    assert result.code == 0
    assert "✗" not in result.out + result.err
    assert "--verbose" in result.out


def test_success_exits_zero(run, agent) -> None:
    result: CliResult = run(["sync", "./x", "--env", "prod"], config=agent)
    assert result.code == 0
    assert "synced x False 1 prod" in result.out
    assert result.err == ""


@pytest.mark.parametrize("mode", ["agent", "human"])
def test_int_return_value_exits_zero_in_both_modes(run, mode: Mode) -> None:
    result: CliResult = run(["returns-int"], config=AgentErrorsConfig(mode=mode))
    assert result.code == 0


def test_keyboard_interrupt_exits_130(run, agent) -> None:
    assert run(["interrupt"], config=agent).code == 130


def test_typer_exit_code_preserved(run, agent) -> None:
    assert run(["fail", "--code", "7"], config=agent).code == 7
    assert run(["fail", "--code", "0"], config=agent).code == 0


def test_abort_mirrors_standalone(run, agent) -> None:
    result: CliResult = run(["fail", "--code", "-1"], config=agent)
    assert result.code == 1
    assert "Aborted" in result.err


def test_runtime_error_propagates(agent, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["myapp", "boom"])
    with pytest.raises(RuntimeError, match="boom"):
        fixture_app.build_main(agent)()


def test_runtime_error_is_tagged_for_pretty_exceptions(
    agent, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "argv", ["myapp", "boom"])
    with pytest.raises(RuntimeError) as info:
        fixture_app.build_main(agent)()
    assert getattr(info.value, compat._DEV_ATTR, None) is not None


def test_no_args_is_help_prints_help_not_error_block(run, agent) -> None:
    result: CliResult = run(["push"], config=agent)
    assert result.code == 2
    assert "✗" not in result.out + result.err
    assert "Usage: myapp push" in result.out + result.err


def test_bare_group_is_missing_command(run, agent) -> None:
    result: CliResult = run([], config=agent)
    assert result.code == 2
    assert result.err.startswith("✗ Usage error in `myapp`: Missing command.")
    assert "Valid subcommands:" in result.err


def test_usage_error_exit_code_is_two(run, agent) -> None:
    result: CliResult = run(["sync", "--verbos"], config=agent)
    assert result.code == 2
    assert result.err.startswith(SENTINEL)
    assert result.out == ""


def test_stream_stdout(run) -> None:
    cfg = AgentErrorsConfig(mode="agent", stream="stdout")
    result: CliResult = run(["sync", "--verbos"], config=cfg)
    assert result.out.startswith(SENTINEL)
    assert result.err == ""


@pytest.mark.parametrize("rich", ["0", "1"])
def test_human_mode_identical_to_unwrapped(run, rich: str) -> None:
    env = {"TYPER_USE_RICH": rich}
    wrapped: CliResult = run(
        ["sync", "--verbos"], config=AgentErrorsConfig(mode="human"), env=env
    )
    plain: CliResult = run(["sync", "--verbos"], env=env, main=fixture_app.app)
    assert wrapped.code == plain.code == 2
    assert wrapped.err == plain.err
    assert wrapped.out == plain.out
    assert "✗" not in wrapped.err


def test_auto_mode_defaults_to_human(run) -> None:
    result: CliResult = run(["sync", "--verbos"])
    assert result.code == 2
    assert "✗" not in result.err


def test_auto_mode_detects_claude_code(run) -> None:
    result: CliResult = run(["sync", "--verbos"], env={"CLAUDECODE": "1"})
    assert result.err.startswith(SENTINEL)


def test_sentinel_flag_forces_agent_and_is_stripped(run) -> None:
    result: CliResult = run(["sync", "--agent-errors", "./x"])
    assert result.code == 0
    assert "synced x" in result.out
    failed: CliResult = run(["--agent-errors", "sync", "--verbos"])
    assert failed.err.startswith(SENTINEL)
    assert "--agent-errors" not in failed.err


def test_human_flag_is_stripped_and_beats_env(run) -> None:
    result: CliResult = run(
        ["sync", "./x", "--human-errors"], env={"AGENT_ERRORS": "1"}
    )
    assert result.code == 0
    assert "synced x" in result.out
    failed: CliResult = run(
        ["sync", "--verbos", "--human-errors"], env={"AGENT_ERRORS": "1"}
    )
    assert "✗" not in failed.err
    assert "--human-errors" not in failed.err


def test_explicit_argv_argument(capsys: pytest.CaptureFixture[str]) -> None:
    main = fixture_app.build_main(AgentErrorsConfig(mode="agent"))
    with pytest.raises(SystemExit) as info:
        main(["sync", "--verbos"])
    assert info.value.code == 2
    assert capsys.readouterr().err.startswith("✗ Usage error in `")


def test_ctx_none_gives_minimal_block(run, agent) -> None:
    result: CliResult = run(["sync", "./x", "--count"], config=agent)
    assert result.code == 2
    assert result.err.startswith(SENTINEL)
    assert "```" in result.err


def test_raw_usage_error_without_ctx(agent, capsys: pytest.CaptureFixture[str]) -> None:
    usage_error: Any = compat.STATUS.get("UsageError")[0]
    main = agent_errors(
        app_raising(usage_error("custom failure", ctx=None)), config=agent
    )
    with pytest.raises(SystemExit) as info:
        main([])
    err = capsys.readouterr().err
    assert info.value.code == 2
    assert err.startswith("✗ Usage error in `")
    assert "custom failure" in err
    assert "--help" in err


def test_introspection_failure_never_masks_error(run, agent, monkeypatch) -> None:
    def explode(*_args, **_kwargs):
        raise ZeroDivisionError("bug in typer-agentic")

    monkeypatch.setattr(intercept, "build_payload", explode)
    result: CliResult = run(["sync", "--verbos"], config=agent)
    assert result.code == 2
    assert "✗" not in result.err
    assert "--verbos" in result.err


def test_render_failure_never_masks_error(run, agent, monkeypatch) -> None:
    def explode(*_args, **_kwargs):
        raise ZeroDivisionError("bug in renderer")

    monkeypatch.setattr(intercept, "render", explode)
    result: CliResult = run(["sync", "./x", "--env", "prd"], config=agent)
    assert result.code == 2
    assert "prd" in result.err
    assert "✗" not in result.err


def test_click_exception_default_replicates_standalone(run, agent) -> None:
    click_exception = compat.STATUS.get("ClickException")[0]
    app = app_raising(click_exception("plain click failure"))
    result: CliResult = run([], config=agent, main=agent_errors(app, config=agent))
    assert result.code == 1
    assert "plain click failure" in result.err
    assert "✗" not in result.err


def test_click_exception_intercepted_when_configured(run) -> None:
    click_exception = compat.STATUS.get("ClickException")[0]
    app = app_raising(click_exception("plain click failure"))
    cfg = AgentErrorsConfig(
        mode="agent", intercept_click_exceptions=True, format="json"
    )
    result: CliResult = run([], config=cfg, main=agent_errors(app, config=cfg))
    assert result.code == 1
    data = json.loads(result.err)
    assert data["error"]["type"] == "click_exception"
    assert data["valid_options"] == []
    assert data["example"] is None


def test_wrapping_does_not_mutate_app() -> None:
    before = list(fixture_app.app.registered_commands)
    agent_errors(fixture_app.app)
    assert fixture_app.app.registered_commands == before
