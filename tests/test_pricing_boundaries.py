"""Builder-owned boundary controls, not independent oracle or heldout cases."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from freightrec.engine.engine import price_contracts
from freightrec.reconcile.findings import classify


@pytest.fixture
def bundle():
    raw = json.loads((Path(__file__).parents[1] / "fixtures/builder/simple-shipment.json").read_text())
    return {key: [json.loads(v) for v in raw[key]] for key in ("contracts", "shipments", "fuel_index")}


def price(bundle):
    return {(e["code"], e["stop_seq"]): e for e in price_contracts(bundle["contracts"], bundle["shipments"][0], bundle["fuel_index"])}


def amount(bundle, code, stop=0):
    return price(bundle)[code, stop]["expected_cents"]


def test_minimum_half_up_and_weight_upper_endpoint(bundle):
    c, s = bundle["contracts"][0], bundle["shipments"][0]
    c["bands"] = [{"min_lb": 0, "max_lb": 1000, "rate_per_cwt": "12"}, {"min_lb": 1000, "max_lb": 2000, "rate_per_cwt": "20"}]
    c["minimum_cents"] = 15000
    s["weight_lb"] = 999
    assert amount(bundle, "LH") == 15000
    s["weight_lb"] = 1000
    assert amount(bundle, "LH") == 20000
    s["weight_lb"] = 2000
    assert amount(bundle, "LH") is None
    c["minimum_cents"] = 0
    s["weight_lb"] = 1
    c["bands"][0]["rate_per_cwt"] = "0.50"
    assert amount(bundle, "LH") == 1


def test_huge_minimum_remains_exact_integer(bundle):
    """what_bug_this_catches: minimum divided in a lower precision context."""
    expected = 10**90 + 12345
    bundle["contracts"][0]["minimum_cents"] = expected
    assert amount(bundle, "LH") == expected


@pytest.mark.parametrize("field,value", [("weight_lb", True), ("weight_lb", 1.0), ("weight_lb", None)])
def test_bad_weight_keeps_money_unknown(bundle, field, value):
    bundle["shipments"][0][field] = value
    assert amount(bundle, "LH") is None
    assert amount(bundle, "FS") is None


@pytest.mark.parametrize("location", ["contract", "shipment", "stop", "fuel"])
def test_malformed_pointer_arrays_refuse_without_crash(bundle, location):
    """what_bug_this_catches: pointer concatenation escaping refusal handling."""
    target = {"contract": bundle["contracts"][0], "shipment": bundle["shipments"][0], "stop": bundle["shipments"][0]["stops"][0], "fuel": bundle["fuel_index"][0]}[location]
    target["evidence_pointers"] = None
    results = price(bundle)
    assert results["FS", 0]["expected_cents"] is None
    if location != "fuel":
        assert all(e["expected_cents"] is None for e in results.values())


def version(bundle, *, start="2026-01-10", end="2026-02-01"):
    older = bundle["contracts"][0]
    newer = deepcopy(older)
    newer.update(contract_id="SECOND", effective_from=start, effective_to=end, minimum_cents=20000)
    older["effective_to"] = "2026-01-10"
    bundle["contracts"].append(newer)
    s = bundle["shipments"][0]
    s.update(pickup_ts="2026-01-09T10:00:00+00:00", delivery_ts="2026-01-10T10:00:00+00:00", weight_lb=1)
    return older, newer


def test_pickup_delivery_basis_and_half_open_versions(bundle):
    older, newer = version(bundle)
    assert amount(bundle, "LH") == 10000
    older["basis"] = newer["basis"] = "delivery"
    assert amount(bundle, "LH") == 20000
    older["basis"] = "pickup"
    assert amount(bundle, "LH") is None


@pytest.mark.parametrize("mode", ["internal_gap", "overlap", "duplicate_id", "outside"])
def test_invalid_version_collection_is_unknown(bundle, mode):
    """what_bug_this_catches: selecting an in-range interval despite global gap."""
    older, newer = version(bundle)
    if mode == "internal_gap":
        newer["effective_from"] = "2026-01-11"
    elif mode == "overlap":
        newer["effective_from"] = "2026-01-09"
    elif mode == "duplicate_id":
        newer["contract_id"] = older["contract_id"]
    else:
        bundle["shipments"][0]["pickup_ts"] = "2025-12-31T10:00:00+00:00"
    assert all(e["expected_cents"] is None for e in price(bundle).values())


def test_fuel_uses_pickup_latest_publication_and_linehaul_only(bundle):
    c, s = bundle["contracts"][0], bundle["shipments"][0]
    s["pickup_ts"] = "2026-01-04T10:00:00+00:00"
    c["basis"] = "delivery"
    bundle["fuel_index"] = [{"publication_date": "2026-01-02", "index_value": "2"}, {"publication_date": "2026-01-05", "index_value": "4"}]
    c["fuel"]["brackets"] = [{"low": "0", "high": "3", "percent": "12.5"}, {"low": "3", "high": "5", "percent": "50"}]
    assert amount(bundle, "FS") == 1563
    s["stops"][0]["liftgate_performed"] = True
    s["stops"][0]["liftgate_authorized"] = True
    assert amount(bundle, "FS") == 1563
    bundle["fuel_index"][0]["index_value"] = "3"
    assert amount(bundle, "FS") == 6250
    bundle["fuel_index"][0]["index_value"] = "5"
    assert amount(bundle, "FS") is None


def test_missing_and_duplicate_fuel_are_unknown(bundle):
    bundle["fuel_index"] = []
    assert amount(bundle, "FS") is None
    bundle["fuel_index"] = [{"publication_date": "2026-01-05", "index_value": "3"}] * 2
    assert amount(bundle, "FS") is None


@pytest.mark.parametrize("departure,expected", [("10:00:00", 0), ("10:00:01", 1500), ("10:15:00", 1500), ("10:15:01", 3000), ("15:00:00", 12000)])
def test_detention_free_increment_and_cap(bundle, departure, expected):
    stop = bundle["shipments"][0]["stops"][0]
    stop["depart_ts"] = "2026-01-06T" + departure + "+00:00"
    assert amount(bundle, "DETENTION", 1) == expected


def test_detention_dst_fall_fold_uses_utc(bundle):
    s = bundle["shipments"][0]
    bundle["contracts"][0].update(effective_from="2026-01-01", effective_to="2027-01-01")
    s["stops"][0].update(timezone="America/New_York", arrive_ts="2026-11-01T01:30:00-04:00", depart_ts="2026-11-01T01:30:00-05:00")
    bundle["contracts"][0]["detention"]["free_minutes"] = 0
    assert amount(bundle, "DETENTION", 1) == 6000


def test_detention_auth_is_explicit_even_with_bypass(bundle):
    stop = bundle["shipments"][0]["stops"][0]
    stop["detention_authorized"] = False
    assert amount(bundle, "DETENTION", 1) == 0
    bundle["contracts"][0]["detention"]["allow_without_preauthorization"] = True
    assert amount(bundle, "DETENTION", 1) == 6000
    stop["detention_authorized"] = None
    assert amount(bundle, "DETENTION", 1) is None


def test_stable_cap_priority_stop_order_and_input_immutability(bundle):
    c, s = bundle["contracts"][0], bundle["shipments"][0]
    one = s["stops"][0]
    one.update(liftgate_performed=True, liftgate_authorized=True)
    two = deepcopy(one)
    two["stop_seq"] = 2
    s["stops"] = [two, one]
    c["accessorial_cap_cents"] = 7000
    before = deepcopy(bundle)
    result = price(bundle)
    assert [result[code, stop]["expected_cents"] for code, stop in [("DETENTION",1),("DETENTION",2),("LIFTGATE",1),("LIFTGATE",2)]] == [6000,1000,0,0]
    assert bundle == before
    s["stops"].reverse()
    assert price(bundle) == result
    c["accessorial_priority"].reverse()
    assert amount(bundle, "LIFTGATE", 1) == 5000
    assert amount(bundle, "LIFTGATE", 2) == 2000
    assert amount(bundle, "DETENTION", 1) == 0


def test_unknown_earlier_cap_does_not_become_known_dollars(bundle):
    c, s = bundle["contracts"][0], bundle["shipments"][0]
    s["stops"][0].update(detention_authorized=None, liftgate_performed=True, liftgate_authorized=True)
    assert amount(bundle, "LIFTGATE", 1) is None
    c["accessorial_cap_cents"] = 0
    assert amount(bundle, "DETENTION", 1) == 0
    assert amount(bundle, "LIFTGATE", 1) == 0


def test_pricing_boundary_leaves_duplicate_allocation_and_no_netting_to_consumer(bundle):
    """what_bug_this_catches: pure engine mutating entitlement by billed input."""
    entitlement = amount(bundle, "LH")
    bundle["shipments"][0]["billed_cents"] = 1
    assert amount(bundle, "LH") == entitlement
    # Allocation belongs to DL2; deadband does not deduct tolerance or net losses.
    assert classify(14000, entitlement, 100) == ("overcharge", 1500)
    assert classify(11000, entitlement, 100) == ("undercharge", 0)



@pytest.mark.parametrize("field,value", [("minimum_cents", True), ("minimum_cents", 1.0), ("accessorial_cap_cents", None)])
def test_invalid_contract_money_refuses_all_charges(bundle, field, value):
    bundle["contracts"][0][field] = value
    assert all(item["expected_cents"] is None for item in price(bundle).values())


@pytest.mark.parametrize("value", [True, 1.0, None])
def test_rate_never_coerces_numeric_values(bundle, value):
    bundle["contracts"][0]["bands"][0]["rate_per_cwt"] = value
    assert amount(bundle, "LH") is None


def test_liftgate_distinguishes_absent_unauthorized_not_performed(bundle):
    stop = bundle["shipments"][0]["stops"][0]
    stop["liftgate_performed"] = None
    assert amount(bundle, "LIFTGATE", 1) is None
    stop.update(liftgate_performed=False, liftgate_authorized=None)
    assert amount(bundle, "LIFTGATE", 1) == 0
    stop["liftgate_performed"] = True
    assert amount(bundle, "LIFTGATE", 1) is None
    stop["liftgate_authorized"] = False
    assert amount(bundle, "LIFTGATE", 1) == 0
    stop["liftgate_authorized"] = True
    assert amount(bundle, "LIFTGATE", 1) == 5000


@pytest.mark.parametrize("depart", ["2026-01-06T08:00:00+00:00", "2026-01-06T11:00:00", "2026-01-06T11:00:00+01:00"])
def test_invalid_detention_time_refuses_instead_of_zero(bundle, depart):
    bundle["shipments"][0]["stops"][0]["depart_ts"] = depart
    assert amount(bundle, "DETENTION", 1) is None


def test_actual_consumer_cap_duplicates_and_undercharge_do_not_net(bundle):
    """what_bug_this_catches: cap consumed twice or undercharge offsets disputes."""
    from freightrec.sources import SourceResolver
    from freightrec.reconcile.reconcile import reconcile_batch

    c, s = bundle["contracts"][0], bundle["shipments"][0]
    c["accessorial_cap_cents"] = 7000
    s["stops"][0].update(liftgate_performed=True, liftgate_authorized=True)
    def line(line_id, code, billed, stop=0):
        return {"line_id": line_id, "shipment_ref": s["shipment_id"], "code": code,
                "stop_seq": stop, "billed_cents": billed, "currency": "USD"}
    first = {"carrier": s["carrier"], "invoice_id": "FIRST",
             "invoice_issue_ts": "2026-01-07T12:00:00Z", "currency": "USD",
             "lines": [line("LOW-LH", "LH", 10000), line("DET", "DETENTION", 6000, 1), line("LIFT", "LIFTGATE", 2000, 1)],
             "total_cents": 18000}
    second = {"carrier": s["carrier"], "invoice_id": "SECOND",
              "invoice_issue_ts": "2026-01-08T12:00:00Z", "currency": "USD",
              "lines": [line("DUP-LH", "LH", 1000)], "total_cents": 1000}
    sources = SourceResolver()
    def bind(document):
        return sources.register_document(json.dumps(document).encode("utf-8"))
    inputs = ([bind(c)], [bind(s)], [bind(second), bind(first)], [bind(bundle["fuel_index"][0])])
    findings = reconcile_batch(*inputs, sources=sources)
    by_line = {row["occurrence"]["line_id"]: row for row in findings}
    assert by_line["LOW-LH"]["verdict"] == "undercharge"
    assert by_line["LOW-LH"]["disputed_cents"] == 0
    assert by_line["LIFT"]["expected_cents"] == 1000
    assert by_line["LIFT"]["disputed_cents"] == 1000
    assert by_line["DUP-LH"]["expected_cents"] == 0
    assert by_line["DUP-LH"]["disputed_cents"] == 1000
    assert sum(row["disputed_cents"] for row in findings) == 2000
    reversed_inputs = (inputs[0], inputs[1], list(reversed(inputs[2])), inputs[3])
    assert reconcile_batch(*reversed_inputs, sources=sources) == findings
