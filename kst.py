"""한국 시간(KST) 유틸."""

from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))


def now() -> datetime:
    """현재 한국 시간."""
    return datetime.now(KST)


def today_str() -> str:
    """오늘 날짜 (YYYY-MM-DD)."""
    return now().strftime("%Y-%m-%d")


def time_str() -> str:
    """현재 시각 (HH:MM)."""
    return now().strftime("%H:%M")


def timestamp_str() -> str:
    """날짜+시각 (YYYY-MM-DD HH:MM)."""
    return now().strftime("%Y-%m-%d %H:%M")
