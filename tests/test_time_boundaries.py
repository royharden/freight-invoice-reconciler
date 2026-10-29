"""Builder regressions for explicit-offset and UTC elapsed-time boundaries."""
from datetime import date

import pytest

from freightrec.timeutil import date_value, elapsed_seconds, local_date


def test_local_date_uses_declared_local_day_not_utc_day():
    """what_bug_this_catches: version selection shifted to UTC calendar day."""
    assert local_date("2026-01-04T23:30:00-05:00", "America/New_York") == date(2026, 1, 4)
    assert local_date("2026-01-05T04:30:00Z", "UTC") == date(2026, 1, 5)


@pytest.mark.parametrize("arrival,departure", [
    ("2026-03-08T01:30:00-05:00", "2026-03-08T03:30:00-04:00"),
    ("2026-11-01T01:30:00-04:00", "2026-11-01T01:30:00-05:00"),
])
def test_dst_transitions_use_elapsed_utc_seconds(arrival, departure):
    """what_bug_this_catches: wall-clock subtraction over spring/fall DST."""
    assert elapsed_seconds(arrival, departure, "America/New_York") == 3600


def test_utc_zero_and_multiday_elapsed():
    assert elapsed_seconds("2026-01-05T09:00:00Z", "2026-01-05T09:00:00+00:00", "UTC") == 0
    assert elapsed_seconds("2026-01-05T09:00:00Z", "2026-01-07T09:00:01Z", "UTC") == 172801


@pytest.mark.parametrize("timestamp,zone", [
    ("2026-01-05T09:00:00", "UTC"),
    ("2026-01-05 09:00:00+00:00", "UTC"),
    ("2026-01-05T09:00:00+01:00", "UTC"),
    ("2026-07-05T09:00:00-05:00", "America/New_York"),
    ("2026-03-08T02:30:00-05:00", "America/New_York"),
    ("2026-03-08T02:30:00-04:00", "America/New_York"),
    ("2026-01-05T09:00:00Z", "Invented/Nowhere"),
    ("2026-01-05T09:00:00Z", None),
    (None, "UTC"),
    (True, "UTC"),
])
def test_missing_naive_wrong_offset_and_nonexistent_times_refuse(timestamp, zone):
    """what_bug_this_catches: guessing timezone/offset for missing or impossible facts."""
    with pytest.raises(ValueError):
        local_date(timestamp, zone)


@pytest.mark.parametrize("arrival,departure", [
    ("2026-01-05T09:00:01Z", "2026-01-05T09:00:00Z"),
    ("2026-01-05T09:00:00.5Z", "2026-01-05T10:00:00Z"),
    ("2026-01-05T09:00:00Z", "2026-01-05T10:00:00.001Z"),
])
def test_negative_or_fractional_detention_facts_refuse(arrival, departure):
    """what_bug_this_catches: truncating invalid seconds into a billable interval."""
    with pytest.raises(ValueError):
        elapsed_seconds(arrival, departure, "UTC")


@pytest.mark.parametrize("value", ["2026-1-5", "2026-02-30", "2026-01-05T00:00:00", None, True])
def test_calendar_dates_are_strict(value):
    with pytest.raises(ValueError):
        date_value(value)


def test_valid_calendar_leap_day():
    assert date_value("2024-02-29") == date(2024, 2, 29)
