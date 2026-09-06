"""§7.3 repeat-failure escalation (spec test 16)."""

from __future__ import annotations

import json
from pathlib import Path

from typer_agentic import AgentErrorsConfig, repeat, wording

from .conftest import CliResult


def test_escalates_on_second_and_third_identical_failure(run, tmp_path: Path) -> None:
    cfg = AgentErrorsConfig(
        mode="agent", repeat_detection=True, repeat_state_dir=tmp_path
    )
    first: CliResult = run(["sync", "--verbos"], config=cfg)
    second: CliResult = run(["sync", "--verbos"], config=cfg)
    third: CliResult = run(["sync", "--verbos"], config=cfg)
    assert "Second identical failure" not in first.err
    assert "Second identical failure" in second.err
    assert "report the exact error" not in second.err
    assert "report the exact error above to the user" in third.err
    assert third.err.count("```") == 2
    state = json.loads((tmp_path / repeat.state_dirname() / "myapp.json").read_text())
    assert state["count"] == 3


def test_different_failure_resets(run, tmp_path: Path) -> None:
    cfg = AgentErrorsConfig(
        mode="agent", repeat_detection=True, repeat_state_dir=tmp_path
    )
    run(["sync", "--verbos"], config=cfg)
    other: CliResult = run(["sync", "--count", "x"], config=cfg)
    assert "Second identical failure" not in other.err


def test_disabled_by_default_writes_nothing(run, tmp_path: Path) -> None:
    cfg = AgentErrorsConfig(mode="agent", repeat_state_dir=tmp_path)
    run(["sync", "--verbos"], config=cfg)
    run(["sync", "--verbos"], config=cfg)
    assert not (tmp_path / repeat.state_dirname()).exists()


def test_corrupt_state_file_is_ignored(tmp_path: Path) -> None:
    directory = tmp_path / repeat.state_dirname()
    directory.mkdir()
    (directory / "myapp.json").write_text("{not json")
    assert repeat.record_failure("myapp", ["a"], "x", base_dir=tmp_path) == 1
    assert repeat.record_failure("myapp", ["a"], "x", base_dir=tmp_path) == 2


def test_unwritable_state_dir_falls_back_silently(run, tmp_path: Path) -> None:
    blocker = tmp_path / repeat.state_dirname()
    blocker.write_text("i am a file, not a directory")
    cfg = AgentErrorsConfig(
        mode="agent", repeat_detection=True, repeat_state_dir=tmp_path
    )
    run(["sync", "--verbos"], config=cfg)
    second: CliResult = run(["sync", "--verbos"], config=cfg)
    assert second.code == 2
    assert "Second identical failure" not in second.err
    assert second.err.startswith("✗")


def test_ttl_expiry(tmp_path: Path) -> None:
    assert repeat.record_failure("p", ["a"], "x", base_dir=tmp_path, now=1000.0) == 1
    assert (
        repeat.record_failure(
            "p", ["a"], "x", base_dir=tmp_path, now=1000.0 + repeat.TTL_SECONDS + 1
        )
        == 1
    )
    assert (
        repeat.record_failure(
            "p", ["a"], "x", base_dir=tmp_path, now=1000.0 + repeat.TTL_SECONDS + 2
        )
        == 2
    )


def test_escalation_copy_in_json(run, tmp_path: Path) -> None:
    cfg = AgentErrorsConfig(
        mode="agent", format="json", repeat_detection=True, repeat_state_dir=tmp_path
    )
    run(["sync", "--verbos"], config=cfg)
    data = json.loads(run(["sync", "--verbos"], config=cfg).err)
    assert data["recovery"]["escalation"] == wording.ESCALATION_SECOND.format(
        command_path="myapp sync"
    )


def test_state_dir_default_under_tmp() -> None:
    assert repeat.state_dir().name.startswith("typer-agentic")


def test_state_path_sanitises_prog_name(tmp_path: Path) -> None:
    assert repeat.state_path("my app/x", tmp_path).name == "my_app_x.json"


def test_next_count_is_pure() -> None:
    assert repeat.next_count(None, "h", 10.0) == 1
    assert repeat.next_count({"hash": "h", "count": 1, "ts": 0.0}, "h", 10.0) == 2
    assert repeat.next_count({"hash": "h", "count": 1, "ts": 0.0}, "h", 601.0) == 1
    assert repeat.next_count({"hash": "other", "count": 4, "ts": 0.0}, "h", 1.0) == 1
    assert repeat.next_count({"garbage": True}, "h", 1.0) == 1


def test_record_failure_accepts_now_zero(tmp_path: Path) -> None:
    assert repeat.record_failure("p", ["a"], "x", base_dir=tmp_path, now=0.0) == 1
    assert repeat.record_failure("p", ["a"], "x", base_dir=tmp_path, now=0.0) == 2
