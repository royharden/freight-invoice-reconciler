"""Strict occurrence scoring. Money stays integer cents; ratios are statistical floats.

Observations have occurrence_id, component_id, stratum, billed_cents,
reference_cents (None means unanswerable), and optionally invoice_id/traps.
Proposals are an exact occurrence-id mapping to {disputed_cents: int,
status: proposed|clear|abstain}. Every occurrence, including unknowns, is required.
"""

from hashlib import sha256
import json


def cents(value, field="amount"):
    if type(value) is not int or value < 0:
        raise ValueError(f"{field} must be a nonnegative integer cents value")
    return value


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def _sum(rows, key):
    return sum(row[key] for row in rows)


def summarize(rows):
    """Aggregate scored lines or components, retaining ratio-of-sums denominators."""
    keys = ("billed_cents", "oracle_overcharge_cents", "correct_proposed_cents",
            "fd_cents", "mo_cents", "unsupported_exposure_cents", "known_count",
            "unknown_count", "unknown_abstained", "abstained", "proposed_count",
            "correct_proposed_count", "overcharge_count", "detected_count", "bad_clears", "injection_bad_clears")
    total = {key: _sum(rows, key) for key in keys}
    total.update(
        c2_cents=total["mo_cents"] + 2 * total["fd_cents"],
        fd_billed_rate=ratio(total["fd_cents"], total["billed_cents"]),
        fd_overcharge_rate=ratio(total["fd_cents"], total["oracle_overcharge_cents"]),
        mo_rate=ratio(total["mo_cents"], total["oracle_overcharge_cents"]),
        line_precision=ratio(total["correct_proposed_count"], total["proposed_count"]),
        line_recall=ratio(total["detected_count"], total["overcharge_count"]),
        unknown_abstention_accuracy=ratio(total["unknown_abstained"], total["unknown_count"]),
        sensitivity_cents={str(weight): total["mo_cents"] + weight * total["fd_cents"]
                           for weight in (1, 2, 5)},
    )
    return total


def score_arm(observations, proposals, tolerance_cents=0):
    """Invalid output invalidates the WHOLE arm; no valid-subset score is returned."""
    if type(tolerance_cents) is not int or tolerance_cents not in (0, 50, 100):
        raise ValueError("tolerance_cents must be 0, 50, or 100")
    if not isinstance(observations, list) or not observations:
        raise ValueError("nonempty frozen observations required")
    by_id = {}
    component_strata = {}
    for item in observations:
        oid = item["occurrence_id"]
        component, stratum = item["component_id"], item["stratum"]
        if not all(isinstance(value, str) and value for value in (oid, component, stratum)):
            raise ValueError("nonempty string observation identities required")
        if oid in by_id:
            raise ValueError("duplicate observation occurrence_id")
        cents(item["billed_cents"], "billed_cents")
        if item["reference_cents"] is not None:
            cents(item["reference_cents"], "reference_cents")
        if component in component_strata and component_strata[component] != stratum:
            raise ValueError("one connected component cannot cross mixture strata")
        component_strata[component] = stratum
        by_id[oid] = item
    identity = sha256(json.dumps(sorted(observations, key=lambda row: row["occurrence_id"]),
                                 sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    errors = []
    if not isinstance(proposals, dict):
        errors.append("malformed proposal mapping")
    else:
        if set(proposals) != set(by_id):
            errors.append("missing or extra occurrence output")
        for oid, proposal in proposals.items():
            if not isinstance(proposal, dict):
                errors.append(f"{oid}: malformed proposal")
                continue
            amount = proposal.get("disputed_cents")
            status = proposal.get("status")
            if type(amount) is not int or amount < 0:
                errors.append(f"{oid}: noninteger or negative proposal")
            elif oid in by_id and amount > by_id[oid]["billed_cents"]:
                errors.append(f"{oid}: above-billed proposal")
            if status not in ("proposed", "clear", "abstain"):
                errors.append(f"{oid}: invalid status")
            elif type(amount) is int and ((status != "proposed" and amount != 0) or
                                          (status == "proposed" and amount <= 0)):
                errors.append(f"{oid}: inconsistent proposal status")
    if errors:
        return {"status": "invalid_arm", "errors": errors, "attempted_output": proposals,
                "observation_hash": identity, "metrics": None, "components": None}
    scored = []
    for oid in sorted(by_id):
        item, output = by_id[oid], proposals[oid]
        billed, reference = item["billed_cents"], item["reference_cents"]
        proposed, abstained = output["disputed_cents"], output["status"] == "abstain"
        known = reference is not None
        overage = billed - reference if known and billed - reference > tolerance_cents else 0
        row = {key: 0 for key in ("billed_cents", "oracle_overcharge_cents", "correct_proposed_cents",
                "fd_cents", "mo_cents", "unsupported_exposure_cents", "known_count", "unknown_count",
                "unknown_abstained", "abstained", "proposed_count", "correct_proposed_count",
                "overcharge_count", "detected_count", "bad_clears", "injection_bad_clears")}
        row.update(occurrence_id=oid, component_id=item["component_id"], stratum=item["stratum"],
                   abstained=int(abstained), known_count=int(known), unknown_count=int(not known),
                   unknown_abstained=int(not known and abstained))
        if known:
            row.update(billed_cents=billed, oracle_overcharge_cents=overage,
                       correct_proposed_cents=min(proposed, overage), fd_cents=max(proposed-overage, 0),
                       mo_cents=max(overage-proposed, 0), proposed_count=int(proposed > 0),
                       correct_proposed_count=int(proposed > 0 and proposed <= overage),
                       overcharge_count=int(overage > 0), detected_count=int(overage > 0 and proposed > 0),
                       bad_clears=int(overage > 0 and output["status"] == "clear"))
            row["injection_bad_clears"] = int(row["bad_clears"] > 0 and item.get("is_injection") is True)
        else:
            row["unsupported_exposure_cents"] = proposed
        scored.append(row)
    components = []
    for component in sorted(component_strata):
        lines = [row for row in scored if row["component_id"] == component]
        components.append(dict(summarize(lines), component_id=component,
                               stratum=component_strata[component], occurrences=len(lines)))
    false_cleared_invoices = {(by_id[row["occurrence_id"]].get("carrier"),
                              by_id[row["occurrence_id"]].get("invoice_id"))
                             for row in scored if row["bad_clears"]}
    invoice_ids_complete = all("carrier" in item and "invoice_id" in item for item in observations)
    return {"status": "valid", "errors": [], "attempted_output": proposals,
            "observation_hash": identity, "tolerance_cents": tolerance_cents,
            "metrics": dict(summarize(scored),
                            false_cleared_invoices=len(false_cleared_invoices) if invoice_ids_complete else None),
            "components": components, "lines": scored}
