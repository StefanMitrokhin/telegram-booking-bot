"""Schedule resolution and persistence."""

from __future__ import annotations

from collections.abc import Sequence


def resolve_intervals(
    *,
    weekday: int,
    weekly: Sequence[tuple[int, int, int]],
    override_kind: str | None,
    override_intervals: Sequence[tuple[int, int]],
) -> list[tuple[int, int]]:
    if override_kind == "day_off":
        return []
    if override_kind == "custom":
        return sorted(override_intervals, key=lambda item: item[0])
    return sorted(
        ((start, end) for w, start, end in weekly if w == weekday),
        key=lambda item: item[0],
    )
