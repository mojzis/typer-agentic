"""§15 acceptance criteria, run as real subprocesses (fresh env per run)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from .conftest import AGENT_ENV_VARS

ROOT = Path(__file__).resolve().parent.parent


def cli(*argv: str, **env: str) -> subprocess.CompletedProcess[str]:
    clean = {k: v for k, v in os.environ.items() if k not in AGENT_ENV_VARS}
    clean.update(env)
    return subprocess.run(
        [sys.executable, "-m", "tests.fixture_app", *argv],
        capture_output=True,
        text=True,
        cwd=ROOT,
        env=clean,
        check=False,
    )


def test_claude_code_env_gets_markdown_block() -> None:
    proc = cli("sync", "--verbos", CLAUDECODE="1")
    assert proc.returncode == 2
    assert proc.stderr.startswith("✗ Usage error in `")
    assert "sync`" in proc.stderr.splitlines()[0]
    assert "Did you mean: --verbose" in proc.stderr
    assert "Do not switch tools" in proc.stderr
    assert proc.stderr.count("```") == 2
    assert proc.stdout == ""


def test_json_format_env() -> None:
    proc = cli("sync", "--verbos", CLAUDECODE="1", AGENT_ERRORS_FORMAT="json")
    assert proc.returncode == 2
    data = json.loads(proc.stderr)
    assert data["error"]["type"] == "no_such_option"
    assert data["suggestions"][0] == "--verbose"


@pytest.mark.parametrize("rich", ["0", "1"])
def test_no_agent_env_is_stock_typer(rich: str) -> None:
    proc = cli("sync", "--verbos", TYPER_USE_RICH=rich)
    assert proc.returncode == 2
    assert "✗" not in proc.stderr
    assert "--verbos" in proc.stderr
    assert ("╭" in proc.stderr) == (rich == "1")


def test_skill_flag() -> None:
    proc = cli("--agent-skill")
    assert proc.returncode == 0
    assert proc.stdout.startswith("---\nname:")
    assert "--env          CHOICE[dev|prod]" in proc.stdout
    assert proc.stderr == ""


def test_success_path_unchanged() -> None:
    proc = cli("sync", "./x", "-v", CLAUDECODE="1")
    assert proc.returncode == 0
    assert proc.stdout.strip() == "synced x True 1 dev x"
