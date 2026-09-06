"""§5 mode/format resolution (spec test 9, 10)."""

from __future__ import annotations

from typing import cast

import pytest

from typer_agentic import AgentErrorsConfig, resolve_format, resolve_mode, scan_argv
from typer_agentic.config import DEFAULT_AGENT_ENV_VARS, Format, Mode

CFG = AgentErrorsConfig()


def test_default_is_human() -> None:
    assert resolve_mode(CFG, [], {}) == "human"


@pytest.mark.parametrize("mode", ["agent", "human"])
def test_explicit_mode_beats_everything(mode: str) -> None:
    cfg = AgentErrorsConfig(mode=cast(Mode, mode))
    env = {"AGENT_ERRORS": "0" if mode == "agent" else "1", "CLAUDECODE": "1"}
    other_flag = "--human-errors" if mode == "agent" else "--agent-errors"
    assert resolve_mode(cfg, [other_flag], env) == mode


def test_agent_flag_beats_env_off() -> None:
    assert resolve_mode(CFG, ["--agent-errors"], {"AGENT_ERRORS": "0"}) == "agent"


def test_human_flag_beats_env_on() -> None:
    assert (
        resolve_mode(CFG, ["sync", "--human-errors"], {"AGENT_ERRORS": "1"}) == "human"
    )


def test_agent_flag_beats_human_flag() -> None:
    assert resolve_mode(CFG, ["--human-errors", "--agent-errors"], {}) == "agent"


@pytest.mark.parametrize("value", ["1", "true", "YES", "on", "anything"])
def test_env_truthy(value: str) -> None:
    assert resolve_mode(CFG, [], {"AGENT_ERRORS": value}) == "agent"


@pytest.mark.parametrize("value", ["0", "false", "No", "off", ""])
def test_env_falsy_beats_detection(value: str) -> None:
    env = {"AGENT_ERRORS": value, "CLAUDECODE": "1"}
    assert resolve_mode(CFG, [], env) == "human"


@pytest.mark.parametrize("name", DEFAULT_AGENT_ENV_VARS)
def test_each_detect_var(name: str) -> None:
    assert resolve_mode(CFG, [], {name: "1"}) == "agent"
    assert resolve_mode(CFG, [], {name: ""}) == "human"


def test_custom_detect_vars() -> None:
    cfg = AgentErrorsConfig(agent_detect_env_vars=("MY_AGENT",))
    assert resolve_mode(cfg, [], {"CLAUDECODE": "1"}) == "human"
    assert resolve_mode(cfg, [], {"MY_AGENT": "x"}) == "agent"


def test_empty_detect_list_disables_detection() -> None:
    cfg = AgentErrorsConfig(agent_detect_env_vars=())
    assert resolve_mode(cfg, [], {"CLAUDECODE": "1"}) == "human"


def test_resolve_mode_accepts_precomputed_scan() -> None:
    scan = scan_argv(CFG, ["--agent-errors"])
    assert resolve_mode(CFG, [], {}, scan=scan) == "agent"


def test_custom_env_var_and_flag() -> None:
    cfg = AgentErrorsConfig(env_var="MY_ERRS", flag="--robot")
    assert resolve_mode(cfg, [], {"MY_ERRS": "1"}) == "agent"
    assert resolve_mode(cfg, ["--robot"], {}) == "agent"
    assert resolve_mode(cfg, ["--agent-errors"], {}) == "human"


def test_flag_disabled() -> None:
    cfg = AgentErrorsConfig(flag=None)
    assert resolve_mode(cfg, ["--agent-errors"], {}) == "human"
    assert scan_argv(cfg, ["--agent-errors"]).args == ["--agent-errors"]


def test_tty_heuristic_off_by_default() -> None:
    assert resolve_mode(CFG, [], {}, stderr_isatty=False) == "human"


def test_tty_heuristic_on() -> None:
    cfg = AgentErrorsConfig(tty_heuristic=True)
    assert resolve_mode(cfg, [], {}, stderr_isatty=False) == "agent"
    assert resolve_mode(cfg, [], {}, stderr_isatty=True) == "human"


def test_tty_heuristic_reads_stderr(monkeypatch: pytest.MonkeyPatch) -> None:
    import sys

    cfg = AgentErrorsConfig(tty_heuristic=True)
    monkeypatch.setattr(sys.stderr, "isatty", lambda: False)
    assert resolve_mode(cfg, [], {}) == "agent"


def test_scan_strips_sentinels_but_not_after_double_dash() -> None:
    scan = scan_argv(
        CFG, ["a", "--agent-errors", "--", "--agent-errors", "--agent-skill"]
    )
    assert scan.args == ["a", "--", "--agent-errors", "--agent-skill"]
    assert scan.agent_flag and not scan.skill_flag and not scan.human_flag


def test_scan_skill_flag() -> None:
    scan = scan_argv(CFG, ["--agent-skill", "sync"])
    assert scan.skill_flag and scan.args == ["sync"]


def test_resolve_format_default_and_config() -> None:
    assert resolve_format(CFG, {}) == "markdown"
    assert resolve_format(AgentErrorsConfig(format="json"), {}) == "json"


@pytest.mark.parametrize("value", ["json", "JSON", " json "])
def test_resolve_format_env_override(value: str) -> None:
    assert resolve_format(CFG, {"AGENT_ERRORS_FORMAT": value}) == "json"
    assert (
        resolve_format(
            AgentErrorsConfig(format="json"), {"AGENT_ERRORS_FORMAT": "markdown"}
        )
        == "markdown"
    )


@pytest.mark.parametrize("value", ["yaml", "", "1", "garbage"])
def test_resolve_format_garbage_falls_back(value: str) -> None:
    assert resolve_format(CFG, {"AGENT_ERRORS_FORMAT": value}) == "markdown"
    assert (
        resolve_format(AgentErrorsConfig(format="json"), {"AGENT_ERRORS_FORMAT": value})
        == "json"
    )


def test_resolve_format_bad_config_value_falls_back() -> None:
    cfg = AgentErrorsConfig(format=cast(Format, "yaml"))
    assert resolve_format(cfg, {}) == "markdown"
