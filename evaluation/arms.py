"""Frozen builder baselines v1, derived from PLAN-M13-v1 sections 7–8.

These policies intentionally omit product semantics; never tune them after outcomes.
All arms consume the same already-extracted/linked observation bundle. A1 wire
adapter: contracts carry carrier/effective_from/lanes/detention/liftgate; each lane
has origin_zone/destination_zone/bands. Fuel rows carry carrier/publication_date/
percentage. Billed detention units are decimal strings plus unit hour|minute|
increment; increment requires explicit billed_increment_minutes. This conversion
is billed units, deliberately NOT elapsed time or free time.
A1 requires explicit currency="USD" before any pricing; missing/non-USD abstains.
A0's flat observation adapter repeats the invoice's actual total_cents on each
line and requires explicit currency="USD" on every line used for arithmetic.
"""

from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from datetime import datetime

from .metrics import cents

POLICY_VERSION = "PLAN-M13-v1:A0-A1:1"


def _decimal(value):
    if not isinstance(value, str):
        raise ValueError("decimal inputs must be strings")
    number = Decimal(value)
    if not number.is_finite() or number < 0:
        raise ValueError("nonnegative finite decimal required")
    return number


def _money(dollars):
    return int((dollars * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def _output(amount, reason, *, abstain=False):
    return {"disputed_cents": amount,
            "status": "abstain" if abstain else "proposed" if amount else "clear",
            "reason": reason, "policy_version": POLICY_VERSION}


def _canonical(row):
    issued = datetime.fromisoformat(row["invoice_issue_ts"])
    if issued.tzinfo is None or issued.utcoffset() is None:
        raise ValueError("offset invoice issue time required")
    return (row["carrier"], row["shipment_id"], row["code"], row["stop_seq"],
            issued, row["invoice_id"], row["line_id"])


def a0(observations):
    """Arithmetic/duplicate baseline. Residual assignment never adds to a duplicate."""
    result, seen, invoices = {}, set(), {}
    for row in observations:
        oid = row["occurrence_id"]
        cents(row["billed_cents"])
        if oid in result:
            raise ValueError("duplicate occurrence_id")
        result[oid] = _output(0, "no_arithmetic_error")
        invoices.setdefault((row["carrier"], row["invoice_id"]), []).append(row)
    linked = []
    for row in observations:
        if row.get("currency") != "USD":
            result[row["occurrence_id"]] = _output(0, "missing_or_non_usd_currency", abstain=True)
        elif row.get("link_status") != "exact":
            result[row["occurrence_id"]] = _output(0, "link_not_exact", abstain=True)
        else:
            try:
                _canonical(row)
                linked.append(row)
            except (KeyError, ValueError, TypeError):
                result[row["occurrence_id"]] = _output(0, "missing_canonical_key", abstain=True)
    for row in sorted(linked, key=_canonical):
        group = (row["carrier"], row["shipment_id"], row["code"], row["stop_seq"])
        if group in seen:
            result[row["occurrence_id"]] = _output(row["billed_cents"], "canonical_duplicate")
        seen.add(group)
    for lines in invoices.values():
        designated = sorted(lines, key=lambda row: (row.get("line_id", ""), row["occurrence_id"]))[-1]
        oid = designated["occurrence_id"]
        if any(row.get("currency") != "USD" for row in lines):
            if result[oid]["reason"] != "canonical_duplicate" and result[oid]["status"] != "abstain":
                result[oid] = _output(0, "missing_or_non_usd_invoice_currency", abstain=True)
            result[oid]["residual_status"] = "abstained_missing_or_non_usd_currency"
            continue
        totals = {row.get("total_cents") for row in lines
                  if type(row.get("total_cents")) is int and row["total_cents"] >= 0}
        # All rows must repeat the same stated total; missing or conflicting facts abstain.
        if len(totals) != 1 or any(type(row.get("total_cents")) is not int or
                                   row["total_cents"] not in totals for row in lines):
            if result[oid]["reason"] != "canonical_duplicate" and result[oid]["status"] != "abstain":
                result[oid] = _output(0, "missing_or_conflicting_invoice_total", abstain=True)
            # A known full duplicate survives; unsupported arithmetic never clears.
            result[oid]["residual_status"] = "abstained_missing_or_conflicting_invoice_total"
            continue
        residual = sum(row["billed_cents"] for row in lines) - next(iter(totals))
        if result[oid]["reason"] == "canonical_duplicate":
            result[oid]["residual_status"] = "abstained_duplicate_priority"
        elif residual <= 0:
            result[oid]["residual_status"] = "nonpositive_no_proposal"
        elif result[oid]["status"] == "abstain" or residual > designated["billed_cents"]:
            result[oid] = _output(0, "residual_not_uniquely_assignable", abstain=True)
        else:
            result[oid] = _output(residual, "designated_invoice_residual")
    return result


def a1(observations, contracts, fuel_index, tolerance_cents=0):
    """Newest-flat-rate baseline: first band, no minimum/auth/free-time/cap."""
    if type(tolerance_cents) is not int or tolerance_cents not in (0, 50, 100):
        raise ValueError("invalid tolerance")
    result = {}
    for row in observations:
        oid, billed = row["occurrence_id"], cents(row["billed_cents"])
        if oid in result:
            raise ValueError("duplicate occurrence_id")
        try:
            if row.get("currency") != "USD":
                raise ValueError("missing_or_non_usd_currency")
            if row.get("link_status") != "exact":
                raise ValueError("link_not_exact")
            candidates = [contract for contract in contracts if contract["carrier"] == row["carrier"]]
            newest = max(candidates, key=lambda contract: (contract["effective_from"], contract["contract_id"]))
            if row["code"] in ("LH", "FS"):
                lanes = [lane for lane in newest["lanes"]
                         if lane["origin_zone"] == row["origin_zone"] and
                         lane["destination_zone"] == row["destination_zone"]]
                if len(lanes) != 1:
                    raise ValueError("ambiguous_lane")
                first_band = lanes[0]["bands"][0]
                linehaul = _money(_decimal(first_band["rate_per_cwt"]) * _decimal(row["weight_lb"]) / 100)
            if row["code"] == "LH":
                expected = linehaul
            elif row["code"] == "FS":
                publications = [entry for entry in fuel_index if entry["carrier"] == row["carrier"]]
                latest = max(publications, key=lambda entry: entry["publication_date"])
                # Rounded own linehaul is the baseline fuel base; no pickup-date rule.
                expected = int((Decimal(linehaul) * _decimal(latest["percentage"]) / 100)
                               .quantize(Decimal("1"), rounding=ROUND_HALF_UP))
            elif row["code"] == "DETENTION":
                units = _decimal(row["billed_detention_units"])
                unit = row["billed_detention_unit"]
                if unit == "hour":
                    hours = units
                elif unit == "minute":
                    hours = units / 60
                elif unit == "increment":
                    increment = _decimal(row["billed_increment_minutes"])
                    if increment <= 0:
                        raise ValueError("invalid billed increment")
                    hours = units * increment / 60
                else:
                    raise ValueError("unknown billed unit")
                expected = _money(hours * _decimal(newest["detention"]["hourly_rate"]))
            elif row["code"] == "LIFTGATE":
                expected = cents(newest["liftgate"]["amount_cents"])
            else:
                raise ValueError("unknown charge code")
            amount = billed - expected if billed - expected > tolerance_cents else 0
            result[oid] = _output(amount, "newest_flat_rate")
        except (KeyError, ValueError, TypeError, IndexError, InvalidOperation):
            result[oid] = _output(0, "missing_or_invalid_flat_rate_input", abstain=True)
    return result


def model_arm_status():
    """Status only. In particular A4 has no callable judgment dispatcher."""
    return {"A3": {"origin": "model", "status": "not_run", "usage": None, "external_cost_cents": None},
            "A4": {"origin": "model", "status": "not_run_guardrail", "usage": None,
                   "external_cost_cents": None}}
