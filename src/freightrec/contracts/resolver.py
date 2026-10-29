"""No latest-version fallback: exactly one applicable policy is required."""
from .model import validate_contract
from ..models import mapping, text, sequence
from ..timeutil import date_value, local_date


def select_contract(contracts: list[dict], shipment: dict) -> dict:
    s = mapping(shipment, "shipment")
    for key in ("carrier", "origin_zone", "destination_zone"):
        text(s.get(key), key)
    matches = []
    intervals = []
    ids = set()
    for raw in sequence(contracts, "contracts"):
        c = mapping(raw, "contract")
        contract_id = text(c.get("contract_id"), "contract_id")
        if contract_id in ids:
            raise ValueError("duplicate contract IDs")
        ids.add(contract_id)
        if c.get("carrier") != s["carrier"] or c.get("origin_zone") != s["origin_zone"] or c.get("destination_zone") != s["destination_zone"]:
            continue
        validate_contract(c)
        basis = c.get("basis", "pickup")
        day = local_date(s.get(basis + "_ts"), s.get(basis + "_timezone"))
        start, end = date_value(c["effective_from"]), date_value(c["effective_to"])
        intervals.append((start, end, basis))
        if start <= day < end:
            matches.append(c)
    if len({i[2] for i in intervals}) > 1:
        raise ValueError("date basis changes across lane versions")
    ordered = sorted(intervals)
    if any(a[1] > b[0] for a, b in zip(ordered, ordered[1:])):
        raise ValueError("overlapping contract versions")
    if any(a[1] < b[0] for a, b in zip(ordered, ordered[1:])):
        raise ValueError("internal gap between contract versions")
    if len(matches) != 1:
        raise ValueError("contract gap or multiple applicable versions")
    return matches[0]
