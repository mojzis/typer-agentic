"""Best-candidate ranking for the single corrected example."""

from __future__ import annotations

import difflib
from collections.abc import Collection, Iterable

from .payload import OptionInfo, SubcommandInfo

CUTOFF = 0.6


def rank(
    offending: str,
    candidates: Iterable[str],
    *,
    possibilities: Iterable[str] | None = None,
    primary: Collection[str] = (),
    limit: int = 3,
) -> list[str]:
    """Rank ``candidates`` by similarity to ``offending``, best first.

    Union of the caller's ``possibilities`` (Typer's own list) and difflib
    close matches; case-sensitive pass first, lowercased pass if that is
    empty. Ties break primary-before-secondary, then shorter, then alphabetic.
    """
    pool = list(dict.fromkeys(candidates))
    picked = list(possibilities or [])
    picked += difflib.get_close_matches(offending, pool, n=limit, cutoff=CUTOFF)
    if not picked:
        lowered = {c.lower(): c for c in pool}
        picked = [
            lowered[m]
            for m in difflib.get_close_matches(
                offending.lower(), list(lowered), n=limit, cutoff=CUTOFF
            )
        ]
    unique = list(dict.fromkeys(picked))
    primary_set = set(primary)

    def key(candidate: str) -> tuple[float, int, int, str]:
        ratio = difflib.SequenceMatcher(None, offending, candidate).ratio()
        return (-ratio, 0 if candidate in primary_set else 1, len(candidate), candidate)

    return sorted(unique, key=key)[:limit]


def option_candidates(options: Iterable[OptionInfo]) -> tuple[list[str], set[str]]:
    """All option spellings, plus the subset that are primary ``opts``."""
    names: list[str] = []
    primary: set[str] = set()
    for opt in options:
        names.extend(opt.names)
        primary.update(opt.primary)
    return names, primary


def subcommand_candidates(subs: Iterable[SubcommandInfo]) -> list[str]:
    return [s.name for s in subs]
