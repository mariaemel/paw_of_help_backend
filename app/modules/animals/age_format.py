from __future__ import annotations


def _plural_ru(n: int, one: str, few: str, many: str) -> str:
    abs_n = abs(n) % 100
    last = abs_n % 10
    if 10 < abs_n < 20:
        return many
    if 1 < last < 5:
        return few
    if last == 1:
        return one
    return many


def format_age_months_ru(months: int) -> str:
    total = max(0, int(months or 0))
    if total == 0:
        return "0 месяцев"
    if total < 12:
        return f"{total} {_plural_ru(total, 'месяц', 'месяца', 'месяцев')}"

    years = total // 12
    rem = total % 12
    year_label = _plural_ru(years, "год", "года", "лет")
    if rem == 0:
        return f"{years} {year_label}"
    month_label = _plural_ru(rem, "месяц", "месяца", "месяцев")
    return f"{years} {year_label} {rem} {month_label}"
