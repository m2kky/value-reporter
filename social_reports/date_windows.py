from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo


@dataclass(frozen=True)
class DateWindow:
    label: str
    start: date
    end: date
    previous_label: str
    previous_start: date
    previous_end: date


class DateWindowError(ValueError):
    pass


def _month_bounds(year: int, month: int) -> tuple[date, date]:
    start = date(year, month, 1)
    if month == 12:
        next_month = date(year + 1, 1, 1)
    else:
        next_month = date(year, month + 1, 1)
    return start, next_month - timedelta(days=1)


def _previous_month(year: int, month: int) -> tuple[int, int]:
    if month == 1:
        return year - 1, 12
    return year, month - 1


def resolve_month(month: str | None, timezone: str) -> DateWindow:
    if month:
        try:
            year, month_number = [int(part) for part in month.split("-", 1)]
            if not 1 <= month_number <= 12:
                raise ValueError
        except ValueError as error:
            raise DateWindowError("Month must use YYYY-MM format, for example 2026-04.") from error
    else:
        today = datetime.now(ZoneInfo(timezone)).date()
        first_this_month = today.replace(day=1)
        last_previous_month = first_this_month - timedelta(days=1)
        year = last_previous_month.year
        month_number = last_previous_month.month

    start, end = _month_bounds(year, month_number)
    previous_year, previous_month_number = _previous_month(year, month_number)
    previous_start, previous_end = _month_bounds(previous_year, previous_month_number)

    return DateWindow(
        label=f"{year:04d}-{month_number:02d}",
        start=start,
        end=end,
        previous_label=f"{previous_year:04d}-{previous_month_number:02d}",
        previous_start=previous_start,
        previous_end=previous_end,
    )


def resolve_date_range(since_str: str, until_str: str, timezone: str) -> DateWindow:
    try:
        start = date.fromisoformat(since_str)
        end = date.fromisoformat(until_str)
    except ValueError as error:
        raise DateWindowError("Dates must be in YYYY-MM-DD format.") from error
        
    if start > end:
        raise DateWindowError("Start date must be before or equal to end date.")
        
    duration = (end - start).days + 1
    previous_end = start - timedelta(days=1)
    previous_start = previous_end - timedelta(days=duration - 1)
    
    label = f"{start.strftime('%Y-%m-%d')}_to_{end.strftime('%Y-%m-%d')}"
    previous_label = f"{previous_start.strftime('%Y-%m-%d')}_to_{previous_end.strftime('%Y-%m-%d')}"
    
    return DateWindow(
        label=label,
        start=start,
        end=end,
        previous_label=previous_label,
        previous_start=previous_start,
        previous_end=previous_end,
    )
