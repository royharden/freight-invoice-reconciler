"""Validate contract policy before deriving any entitlement."""
from ..models import mapping, sequence, text, boolean, evidence
from ..money import cents, decimal_string
from ..timeutil import date_value


def validate_contract(contract: dict) -> dict:
    c = mapping(contract, "contract")
    evidence(c.get("evidence_pointers", []))
    for key in ("contract_id", "carrier", "origin_zone", "destination_zone", "clause_id"):
        text(c.get(key), key)
    if date_value(c.get("effective_from")) >= date_value(c.get("effective_to")):
        raise ValueError("empty contract interval")
    if c.get("basis", "pickup") not in ("pickup", "delivery"):
        raise ValueError("invalid date basis")
    cents(c.get("minimum_cents"))
    bands = sequence(c.get("bands"), "bands")
    if not bands:
        raise ValueError("empty weight bands")
    ranges = []
    for band in bands:
        b = mapping(band, "band")
        low, high = cents(b.get("min_lb")), cents(b.get("max_lb"))
        if low >= high:
            raise ValueError("invalid weight band")
        decimal_string(b.get("rate_per_cwt"))
        ranges.append((low, high))
    _disjoint(ranges)
    f = mapping(c.get("fuel"), "fuel")
    text(f.get("clause_id"), "fuel clause")
    evidence(f.get("evidence_pointers", []))
    brackets = sequence(f.get("brackets"), "brackets")
    if not brackets:
        raise ValueError("empty fuel brackets")
    ranges = []
    for bracket in brackets:
        b = mapping(bracket, "bracket")
        low, high = decimal_string(b.get("low")), decimal_string(b.get("high"))
        if low >= high:
            raise ValueError("invalid fuel bracket")
        decimal_string(b.get("percent"))
        ranges.append((low, high))
    _disjoint(ranges)
    d = mapping(c.get("detention"), "detention")
    text(d.get("clause_id"), "detention clause")
    evidence(d.get("evidence_pointers", []))
    for key in ("free_minutes", "increment_minutes", "max_billable_minutes"):
        cents(d.get(key))
    if not d["increment_minutes"] or d["max_billable_minutes"] % d["increment_minutes"]:
        raise ValueError("detention cap must be an increment multiple")
    decimal_string(d.get("hourly_rate"))
    boolean(d.get("allow_without_preauthorization"))
    lift = mapping(c.get("liftgate"), "liftgate")
    text(lift.get("clause_id"), "liftgate clause")
    evidence(lift.get("evidence_pointers", []))
    cents(lift.get("amount_cents"))
    boolean(lift.get("requires_authorization"))
    cents(c.get("accessorial_cap_cents"))
    priority = sequence(c.get("accessorial_priority"), "priority")
    if len(priority) != 2 or set(priority) != {"DETENTION", "LIFTGATE"}:
        raise ValueError("priority must name each accessorial exactly once")
    return c


def _disjoint(ranges: list) -> None:
    ordered = sorted(ranges)
    if any(a[1] > b[0] for a, b in zip(ordered, ordered[1:])):
        raise ValueError("overlapping policy bands")
