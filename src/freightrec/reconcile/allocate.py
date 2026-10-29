"""Canonical occurrence ordering, independent of input list ordering."""

from datetime import datetime, timezone

from ..link import normalize_reference
from .findings import canonical


def issue_time(value: object) -> str:
    if not isinstance(value, str):
        raise ValueError("invoice_issue_ts_missing")
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("invoice_issue_ts_invalid") from exc
    if timestamp.utcoffset() is None:
        raise ValueError("invoice_issue_ts_naive")
    return timestamp.astimezone(timezone.utc).isoformat()


def allocation_key(row: dict) -> tuple:
    """Call only after identity/link validation. Full payload breaks safe ties."""
    return (
        normalize_reference(row["carrier"]),
        row["shipment_key"], row["code"], row["stop_seq"],
        issue_time(row["invoice_issue_ts"]), row["invoice_id"], row["line_id"],
        canonical(row["line"]),
    )
