"""Synthetic pickup-date fuel publication resolution."""
from ..models import sequence, mapping, evidence
from ..money import decimal_string
from ..timeutil import date_value


def fuel_percent(policy: dict, publications: list[dict], pickup_day) -> tuple:
    eligible = []
    dates = set()
    for raw in sequence(publications, "fuel_index"):
        row = mapping(raw, "publication")
        evidence(row.get("evidence_pointers", []))
        day = date_value(row.get("publication_date"))
        value = decimal_string(row.get("index_value"))
        if day in dates:
            raise ValueError("duplicate fuel publication date")
        dates.add(day)
        if day <= pickup_day:
            eligible.append((day, value, row))
    if not eligible:
        raise ValueError("missing pickup-date fuel publication")
    day, value, row = max(eligible, key=lambda item: item[0])
    matches = [b for b in policy["brackets"] if decimal_string(b["low"]) <= value < decimal_string(b["high"])]
    if len(matches) != 1:
        raise ValueError("fuel index outside bracket or ambiguous")
    return decimal_string(matches[0]["percent"]), row
