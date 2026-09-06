"""Optional repeat-failure detection (M6). Best-effort, never raises.

State: one small JSON file per program under ``$TMPDIR/typer-agentic-<uid>/``
(``typer-agentic`` where there is no uid), ``{"hash", "count", "ts"}``,
10-minute TTL, atomic replace.
"""

from __future__ import annotations

import contextlib
import dataclasses
import hashlib
import json
import os
import tempfile
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from . import wording
from .payload import ErrorPayload

TTL_SECONDS = 600
SECOND_FAILURE = 2


def state_dirname() -> str:
    getuid = getattr(os, "getuid", None)
    return f"typer-agentic-{getuid()}" if getuid else "typer-agentic"


def state_dir(base: Path | None = None) -> Path:
    return (base or Path(tempfile.gettempdir())) / state_dirname()


def state_path(prog_name: str, base: Path | None = None) -> Path:
    safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in prog_name)
    return state_dir(base) / f"{safe or 'cli'}.json"


def failure_hash(prog_name: str, argv: Sequence[str], error_type: str) -> str:
    raw = "\0".join([prog_name, error_type, *argv])
    return hashlib.sha256(raw.encode("utf-8", "replace")).hexdigest()


def next_count(previous: dict[str, Any] | None, digest: str, now: float) -> int:
    """Consecutive identical failures so far, counting this one (pure)."""
    if previous is None:
        return 1
    try:
        fresh = now - float(previous["ts"]) <= TTL_SECONDS
        if fresh and previous["hash"] == digest:
            return int(previous["count"]) + 1
    except (KeyError, TypeError, ValueError):
        pass
    return 1


def _read_state(path: Path) -> dict[str, Any] | None:
    with contextlib.suppress(OSError, ValueError):
        loaded = json.loads(path.read_text("utf-8"))
        if isinstance(loaded, dict):
            return loaded
    return None


def _write_state(path: Path, state: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(state))
        Path(tmp).replace(path)
    except OSError:
        Path(tmp).unlink(missing_ok=True)
        raise


def record_failure(
    prog_name: str,
    argv: Sequence[str],
    error_type: str,
    *,
    base_dir: Path | None = None,
    now: float | None = None,
) -> int:
    """Store this failure; return how many identical failures in a row (>= 1)."""
    timestamp = time.time() if now is None else now
    try:
        path = state_path(prog_name, base_dir)
        digest = failure_hash(prog_name, argv, error_type)
        count = next_count(_read_state(path), digest, timestamp)
        _write_state(path, {"hash": digest, "count": count, "ts": timestamp})
    except Exception:
        return 1
    return count


def escalate(payload: ErrorPayload, count: int) -> ErrorPayload:
    """Return a copy of ``payload`` with escalation copy for repeat failures."""
    if count < SECOND_FAILURE:
        return payload
    template = (
        wording.ESCALATION_SECOND
        if count == SECOND_FAILURE
        else wording.ESCALATION_THIRD
    )
    recovery = dataclasses.replace(
        payload.recovery,
        escalation=template.format(command_path=payload.command_path),
    )
    return dataclasses.replace(payload, recovery=recovery)
