"""날짜·문자열 공통 도우미."""
import datetime as dt
import re

DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def parse_date(s) -> dt.date | None:
    if not isinstance(s, str) or not DATE_RE.match(s):
        return None
    try:
        return dt.date.fromisoformat(s)
    except ValueError:
        return None


def is_date(s) -> bool:
    return parse_date(s) is not None


def add_days(s: str, n: int) -> str:
    return (dt.date.fromisoformat(s) + dt.timedelta(days=n)).isoformat()


def days_between(a: str, b: str) -> int:
    return (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S")


def blank_to_none(v):
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v
