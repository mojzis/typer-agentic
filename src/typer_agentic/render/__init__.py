"""Renderers: dumb views over :class:`typer_agentic.payload.ErrorPayload`."""

from __future__ import annotations

from ..config import Format
from ..payload import ErrorPayload
from .json_format import render_json
from .markdown import render_markdown


def render(payload: ErrorPayload, fmt: Format) -> str:
    return render_json(payload) if fmt == "json" else render_markdown(payload)


__all__ = ["render", "render_json", "render_markdown"]
