"""JSON renderer: one object, indent=2, newline-terminated, nothing else."""

from __future__ import annotations

import json

from ..payload import ErrorPayload


def render_json(payload: ErrorPayload) -> str:
    return json.dumps(payload.to_dict(), indent=2, ensure_ascii=False) + "\n"
