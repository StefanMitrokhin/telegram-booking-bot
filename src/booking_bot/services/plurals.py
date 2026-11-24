"""Russian plural forms."""

from __future__ import annotations


def hours(n: int) -> str:
    n_abs = abs(n)
    if 11 <= n_abs % 100 <= 14:
        form = "часов"
    else:
        mod = n_abs % 10
        if mod == 1:
            form = "час"
        elif 2 <= mod <= 4:
            form = "часа"
        else:
            form = "часов"
    return f"{n} {form}"


def format_lead(minutes: int) -> str:
    if minutes % 60 == 0:
        return hours(minutes // 60)
    return f"{minutes} мин"
