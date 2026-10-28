"""Pure pricing, with null unknowns and stable per-shipment cap allocation."""
from decimal import Decimal, localcontext
from ..models import mapping, sequence, boolean, evidence
from ..money import cents, decimal_string, rounded_cents
from ..timeutil import local_date, elapsed_seconds
from ..contracts.model import validate_contract
from ..contracts.resolver import select_contract
from ..contracts.fuel import fuel_percent

ENGINE_VERSION = "rate-spec-v0-construction-5"


def _item(code, stop=0, amount=None, clause=None, trace=None, missing=None, pointers=None, reason=None):
    return {"code": code, "stop_seq": stop, "expected_cents": amount,
            "clause_id": clause, "trace": trace or [], "missing_facts": missing or [],
            "evidence_pointers": pointers or [],
            "reason_code": reason or ("priced" if amount is not None else "cannot_determine")}


def _unknown(shipment, reason):
    result = [_item("LH", missing=[reason]), _item("FS", missing=[reason])]
    if type(shipment) is dict and type(shipment.get("stops")) is list:
        for stop in shipment["stops"]:
            if type(stop) is dict and type(stop.get("stop_seq")) is int and stop["stop_seq"] > 0:
                result.extend(_item(code, stop["stop_seq"], missing=[reason]) for code in ("DETENTION", "LIFTGATE"))
    return result


def price_contracts(contracts: list[dict], shipment: dict, fuel_index: list[dict]) -> list[dict]:
    """Resolve the unique lane version, refusing gaps and overlaps."""
    try:
        contract = select_contract(contracts, shipment)
    except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
        return _unknown(shipment, str(exc))
    return price_shipment(contract, shipment, fuel_index)


def price_shipment(contract: dict, shipment: dict, fuel_index: list[dict]) -> list[dict]:
    """Price a resolved contract. Recheck applicability, never choose a fallback."""
    try:
        validate_contract(contract)
        select_contract([contract], shipment)
        s = mapping(shipment, "shipment")
        evidence(s.get("evidence_pointers", []))
        stops = sequence(s.get("stops"), "stops")
        ids = []
        for raw in stops:
            stop = mapping(raw, "stop")
            evidence(stop.get("evidence_pointers", []))
            seq = cents(stop.get("stop_seq"))
            if seq == 0:
                raise ValueError("delivery stop_seq must be positive")
            ids.append(seq)
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate delivery stop_seq")
    except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
        return _unknown(shipment, str(exc))
    c = contract
    pointers = c.get("evidence_pointers", []) + s.get("evidence_pointers", [])
    try:
        weight = cents(s.get("weight_lb"))
        bands = [b for b in c["bands"] if b["min_lb"] <= weight < b["max_lb"]]
        if len(bands) != 1:
            raise ValueError("weight outside unique band")
        rate = decimal_string(bands[0]["rate_per_cwt"])
        with localcontext() as ctx:
            ctx.prec = max(64, len(str(weight)) + len(rate.as_tuple().digits) + 20)
            raw_dollars = rate * Decimal(weight) / 100
            amount = max(c["minimum_cents"], rounded_cents(raw_dollars))
        lh = _item("LH", amount=amount, clause=c["clause_id"], pointers=pointers,
                   trace=[{"weight_lb": weight, "rate_per_cwt": str(rate), "minimum_cents": c["minimum_cents"], "unrounded_dollars": str(raw_dollars)}])
    except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
        lh = _item("LH", clause=c["clause_id"], missing=[str(exc)], pointers=pointers)
    try:
        if lh["expected_cents"] is None:
            raise ValueError("linehaul unknown: fuel base unavailable")
        pickup = local_date(s.get("pickup_ts"), s.get("pickup_timezone"))
        percent, publication = fuel_percent(c["fuel"], fuel_index, pickup)
        with localcontext() as ctx:
            ctx.prec = max(64, len(str(lh["expected_cents"])) + len(percent.as_tuple().digits) + 20)
            amount = rounded_cents(Decimal(lh["expected_cents"]) * percent / 10000)
        fs = _item("FS", amount=amount, clause=c["fuel"]["clause_id"],
                   pointers=pointers + c["fuel"].get("evidence_pointers", []) + publication.get("evidence_pointers", []),
                   trace=[{"pickup_local_date": str(pickup), "publication_date": publication["publication_date"], "percent": str(percent), "base_linehaul_cents": lh["expected_cents"]}])
    except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
        fs = _item("FS", clause=c["fuel"]["clause_id"], missing=[str(exc)], pointers=pointers)
    accessorials = []
    for stop in stops:
        accessorials.append(_detention(c["detention"], stop, pointers))
        accessorials.append(_liftgate(c["liftgate"], stop, pointers))
    priority = {code: index for index, code in enumerate(c["accessorial_priority"])}
    accessorials.sort(key=lambda item: (priority[item["code"]], item["stop_seq"]))
    remaining = c["accessorial_cap_cents"]
    uncertain = False
    for item in accessorials:
        amount = item["expected_cents"]
        if amount is None:
            # A depleted cap establishes zero even if raw entitlement is unknown.
            if remaining == 0:
                item.update(expected_cents=0, missing_facts=[], reason_code="cap_exhausted")
            else:
                uncertain = True
            continue
        if amount == 0:
            continue
        if uncertain:
            item.update(expected_cents=None, missing_facts=["earlier cap allocation unknown"], reason_code="cannot_determine")
            continue
        allocated = min(amount, remaining)
        item["trace"].append({"uncapped_cents": amount, "cap_remaining_before_cents": remaining, "allocated_cents": allocated})
        item["expected_cents"] = allocated
        remaining -= allocated
    return [lh, fs] + accessorials


def _detention(policy, stop, pointers):
    clause, seq = policy["clause_id"], stop["stop_seq"]
    evidence = pointers + policy.get("evidence_pointers", []) + stop.get("evidence_pointers", [])
    try:
        authorized = boolean(stop.get("detention_authorized"), "detention_authorized")
        if not authorized and not policy["allow_without_preauthorization"]:
            return _item("DETENTION", seq, 0, clause, pointers=evidence, reason="unauthorized")
        elapsed = elapsed_seconds(stop.get("arrive_ts"), stop.get("depart_ts"), stop.get("timezone"))
        chargeable = max(0, elapsed - policy["free_minutes"] * 60)
        increment = policy["increment_minutes"] * 60
        billable = min(((chargeable + increment - 1) // increment) * policy["increment_minutes"], policy["max_billable_minutes"])
        rate = decimal_string(policy["hourly_rate"])
        with localcontext() as ctx:
            ctx.prec = max(64, len(str(billable)) + len(rate.as_tuple().digits) + 20)
            amount = rounded_cents(Decimal(billable) * rate / 60)
        return _item("DETENTION", seq, amount, clause,
                     trace=[{"elapsed_utc_seconds": elapsed, "free_minutes": policy["free_minutes"], "increment_minutes": policy["increment_minutes"], "billable_minutes": billable, "hourly_rate": str(rate)}], pointers=evidence)
    except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
        return _item("DETENTION", seq, clause=clause, missing=[str(exc)], pointers=evidence)


def _liftgate(policy, stop, pointers):
    clause, seq = policy["clause_id"], stop["stop_seq"]
    evidence = pointers + policy.get("evidence_pointers", []) + stop.get("evidence_pointers", [])
    try:
        performed = boolean(stop.get("liftgate_performed"), "liftgate_performed")
        if not performed:
            return _item("LIFTGATE", seq, 0, clause, pointers=evidence, reason="not_performed")
        if policy["requires_authorization"]:
            authorized = boolean(stop.get("liftgate_authorized"), "liftgate_authorized")
            if not authorized:
                return _item("LIFTGATE", seq, 0, clause, pointers=evidence, reason="unauthorized")
        return _item("LIFTGATE", seq, policy["amount_cents"], clause, pointers=evidence,
                     trace=[{"performed": True, "requires_authorization": policy["requires_authorization"], "flat_cents": policy["amount_cents"]}])
    except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
        return _item("LIFTGATE", seq, clause=clause, missing=[str(exc)], pointers=evidence)
