"""Offset-explicit timestamps checked against declared IANA timezone rules."""

from datetime import date, datetime, timezone
import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\Z")
_TIMESTAMP = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}:[0-9]{2})\Z"
)


def date_value(value: object) -> date:
    """Require an exact ISO calendar date, excluding datetime/coercion input."""
    if type(value) is not str or _DATE.fullmatch(value) is None:
        raise ValueError("date must use YYYY-MM-DD")
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("invalid calendar date") from exc


def _checked_timestamp(value: object, zone: object) -> datetime:
    if type(value) is not str or _TIMESTAMP.fullmatch(value) is None:
        raise ValueError("timestamp must contain seconds and an explicit UTC offset")
    if type(zone) is not str or not zone:
        raise ValueError("timestamp requires an IANA timezone")
    try:
        declared_zone = ZoneInfo(zone)
        instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
        # Round-tripping through UTC detects nonexistent local wall times; both
        # sides of a fall-back fold remain valid when their explicit offset agrees.
        zoned = instant.astimezone(timezone.utc).astimezone(declared_zone)
        if (
            instant.utcoffset() != zoned.utcoffset()
            or instant.replace(tzinfo=None) != zoned.replace(tzinfo=None)
        ):
            raise ValueError("timestamp offset or wall time conflicts with IANA zone")
        return instant
    except (ZoneInfoNotFoundError, ValueError, OverflowError, OSError) as exc:
        raise ValueError("invalid timestamp or unavailable timezone rules") from exc


def local_date(timestamp: str, zone: str) -> date:
    """Return the validated local calendar date used for rate applicability."""
    return _checked_timestamp(timestamp, zone).date()


def elapsed_seconds(arrive: str, depart: str, zone: str) -> int:
    """Use exact UTC elapsed whole seconds, refusing negative/fractional facts."""
    arrival = _checked_timestamp(arrive, zone)
    departure = _checked_timestamp(depart, zone)
    if arrival.microsecond or departure.microsecond:
        raise ValueError("detention timestamps require whole seconds")
    elapsed = departure.astimezone(timezone.utc) - arrival.astimezone(timezone.utc)
    if elapsed.days < 0:
        raise ValueError("departure precedes arrival")
    return elapsed.days * 86400 + elapsed.seconds
