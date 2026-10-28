"""Builder-owned regression controls, not independent labels or benchmark data.

what_bug_this_catches: monetary proposals must follow original source facts,
canonical entitlement allocation, exact carrier linkage and current link context.
"""

from copy import deepcopy
import json

import pytest

from freightrec.ingest import extract
from freightrec.reconcile import reconcile_batch
from freightrec.sources import SourceResolver


def contract(**changes):
    result = {
        "contract_id": "C1", "carrier": "Carrier-A",
        "origin_zone": "A", "destination_zone": "B",
        "effective_from": "2026-01-01", "effective_to": "2026-02-01",
        "basis": "pickup", "clause_id": "LH-clause",
        "bands": [{"min_lb": 0, "max_lb": 10000, "rate_per_cwt": "10.00"}],
        "minimum_cents": 10000,
        "fuel": {"clause_id": "FS-clause", "brackets": [{"low": "0", "high": "10", "percent": "10"}]},
        "detention": {"clause_id": "DET-clause", "free_minutes": 60, "increment_minutes": 15,
                      "max_billable_minutes": 120, "hourly_rate": "60.00", "allow_without_preauthorization": False},
        "liftgate": {"clause_id": "LIFT-clause", "amount_cents": 5000, "requires_authorization": True},
        "accessorial_cap_cents": 15000, "accessorial_priority": ["DETENTION", "LIFTGATE"],
    }
    result.update(changes)
    return result


def shipment(**changes):
    result = {
        "carrier": "Carrier-A", "shipment_id": "S1", "reference": "PRO-1",
        "origin_zone": "A", "destination_zone": "B", "weight_lb": 1000,
        "pickup_ts": "2026-01-05T09:00:00+00:00", "pickup_timezone": "UTC",
        "delivery_ts": "2026-01-06T09:00:00+00:00", "delivery_timezone": "UTC", "stops": [],
    }
    result.update(changes)
    return result


def line(line_id="L1", billed=12000, reference="PRO-1", **changes):
    result = {"line_id": line_id, "code": "LH", "stop_seq": 0,
              "shipment_ref": reference, "currency": "USD", "billed_cents": billed}
    result.update(changes)
    return result


def invoice(invoice_id="I1", lines=None, issued="2026-01-07T12:00:00+00:00", **changes):
    lines = [line()] if lines is None else lines
    result = {"carrier": "Carrier-A", "invoice_id": invoice_id, "invoice_issue_ts": issued,
              "currency": "USD", "total_cents": sum(item["billed_cents"] for item in lines), "lines": lines}
    result.update(changes)
    return result


def bundle(invoices=None, shipments=None, contracts=None, indexes=None):
    resolver = SourceResolver()

    def bind(items):
        return [resolver.register_document(json.dumps(item, ensure_ascii=False).encode("utf-8")) for item in items]

    documents = (
        bind([contract()] if contracts is None else contracts),
        bind([shipment()] if shipments is None else shipments),
        bind([invoice()] if invoices is None else invoices),
        bind([{"publication_date": "2026-01-05", "index_value": "3.50"}] if indexes is None else indexes),
    )
    return resolver, documents


def run_bundle(resolver, documents, **kwargs):
    return reconcile_batch(*documents, sources=resolver, **kwargs)


def test_priced_finding_contains_resolvable_original_money_and_clause_evidence():
    """what_bug_this_catches: missing contract/fuel/source evidence must not approve money."""
    resolver, documents = bundle()
    finding, = run_bundle(resolver, documents)
    assert (finding["billed_cents"], finding["expected_cents"], finding["disputed_cents"]) == (12000, 10000, 2000)
    assert finding["missing_facts"] == []
    quotes = [resolver.resolve(pointer) for pointer in finding["evidence_pointers"]]
    assert any('"minimum_cents": 10000' in quote and '"LH-clause"' in quote for quote in quotes)
    assert any('"billed_cents": 12000' in quote for quote in quotes)
    assert finding["link_context"]["carrier"] == "CARRIERA"


@pytest.mark.parametrize("billed,tolerance,verdict,disputed", [
    (10050, 50, "justified", 0), (10051, 50, "overcharge", 51),
    (9900, 50, "undercharge", 0),
])
def test_full_overage_deadband(billed, tolerance, verdict, disputed):
    """what_bug_this_catches: subtracting tolerance understates eligible overage."""
    resolver, documents = bundle(invoices=[invoice(lines=[line(billed=billed)])])
    finding, = run_bundle(resolver, documents, tolerance_cents=tolerance)
    assert (finding["verdict"], finding["disputed_cents"]) == (verdict, disputed)


def test_canonical_duplicate_allocation_no_undercharge_netting_and_shuffle():
    """what_bug_this_catches: input order must not move entitlement or stale approvals."""
    first = invoice("I1", [line("L1", 9000)], "2026-01-07T12:00:00+00:00")
    second = invoice("I2", [line("L2", 3000)], "2026-01-08T12:00:00+00:00")
    contracts = [contract(), contract(contract_id="C2", effective_from="2026-02-01", effective_to="2026-03-01")]
    indexes = [{"publication_date": "2025-12-29", "index_value": "3.00"},
               {"publication_date": "2026-01-05", "index_value": "3.50"}]
    resolver, documents = bundle([second, first], contracts=contracts, indexes=indexes)
    baseline = run_bundle(resolver, documents)
    by_invoice = {finding["occurrence"]["invoice_id"]: finding for finding in baseline}
    assert (by_invoice["I1"]["expected_cents"], by_invoice["I1"]["verdict"], by_invoice["I1"]["disputed_cents"]) == (10000, "undercharge", 0)
    assert (by_invoice["I2"]["expected_cents"], by_invoice["I2"]["disputed_cents"]) == (0, 3000)
    assert sum(item["disputed_cents"] for item in baseline) == 3000
    shuffled = tuple(list(reversed(collection)) for collection in documents)
    assert run_bundle(resolver, shuffled) == baseline


def test_unknown_entitlement_never_becomes_zero_even_for_duplicate():
    """what_bug_this_catches: unknown first charge must not establish duplicate dollars."""
    resolver, documents = bundle(invoices=[invoice("I1"), invoice("I2")], shipments=[shipment(weight_lb=None)])
    findings = run_bundle(resolver, documents)
    assert len(findings) == 2
    assert all(item["expected_cents"] is None and item["disputed_cents"] is None for item in findings)


def test_namespace_normalization_exact_priority_and_cross_carrier_refusal():
    """what_bug_this_catches: similar or other-carrier IDs must not auto-link."""
    resolver, documents = bundle(invoices=[invoice(carrier="carrier_a")])

    def forbidden(_):
        pytest.fail("manual callback must not override exact auto-link")

    finding, = run_bundle(resolver, documents, link_resolver=forbidden)
    assert finding["expected_cents"] == 10000
    assert finding["link_context"] is not None
    resolver, documents = bundle(invoices=[invoice(carrier="Carrier-B")])
    finding, = run_bundle(resolver, documents)
    assert finding["verdict"] == "cannot_determine"
    assert finding["disputed_cents"] is None


def test_manual_link_preserves_prelink_context_and_binds_final_target():
    """what_bug_this_catches: ruling/finding recursion and unbound target changes."""
    resolver, documents = bundle(invoices=[invoice(lines=[line(reference="PRO-2")])])
    baseline, = run_bundle(resolver, documents)
    assert baseline["disputed_cents"] is None
    observed = []

    def human_store_seam(context):
        # Trusted CODE seam only; this builder fixture is not human evidence.
        observed.append(context)
        return "S1"

    resolved, = run_bundle(resolver, documents, link_resolver=human_store_seam)
    assert observed == [baseline["link_context"]]
    assert resolved["link_context"] == baseline["link_context"]
    assert resolved["occurrence_id"] == baseline["occurrence_id"]
    assert resolved["disputed_cents"] == 2000
    assert resolved["dependency_hash"] != baseline["dependency_hash"]


@pytest.mark.parametrize("target", [None, "missing", "foreign", "duplicate", "unverified", {"verified": True}])
def test_manual_targets_fail_closed(target):
    """what_bug_this_catches: a callback cannot introduce or cross-link a shipment."""
    shipments = [shipment(), shipment(shipment_id="foreign", reference="X1", carrier="Carrier-B"),
                 shipment(shipment_id="duplicate", reference="X2"),
                 shipment(shipment_id="duplicate", reference="X3"),
                 shipment(shipment_id="unverified", reference="X4")]
    resolver, documents = bundle(invoices=[invoice(lines=[line(reference="TYPO")])], shipments=shipments)
    documents[1][-1].pop("field_values")
    finding, = run_bundle(resolver, documents, link_resolver=lambda context: target)
    assert finding["expected_cents"] is None
    assert finding["disputed_cents"] is None


def test_invalid_source_has_no_actionable_context_and_no_callback():
    """what_bug_this_catches: arbitrary valid pointers must not certify changed money."""
    resolver, documents = bundle()
    documents[2][0]["lines"][0]["billed_cents"] = 99999
    documents[2][0]["total_cents"] = 99999

    def forbidden(_):
        pytest.fail("invalid original proof cannot request a link ruling")

    finding, = run_bundle(resolver, documents, link_resolver=forbidden)
    assert finding["link_context"] is None
    assert finding["disputed_cents"] is None


@pytest.mark.parametrize("currency", [None, "EUR"])
def test_structured_line_currency_cannot_inherit_root_usd(currency):
    """what_bug_this_catches: verified JSON line currency used to bypass USD policy."""
    resolver, documents = bundle(invoices=[invoice(lines=[line(currency=currency)])])
    finding, = run_bundle(resolver, documents)
    assert finding["expected_cents"] is None and finding["disputed_cents"] is None
    assert "line_currency_must_be_USD" in finding["missing_facts"]


def native_invoice(resolver):
    text = ("FREIGHTREC INVOICE V1\nCarrier: Carrier-A\nInvoice: I1\n"
            "Issued: 2026-01-07T12:00:00+00:00\nCurrency: USD\nTotal: 120.00\n"
            "Lines:\nL1|PRO-1|LH|0|USD|120.00\n")
    result = extract({"template_id": "freightrec-invoice-v1", "media_type": "text/plain",
                      "text": text, "resolver": resolver})
    assert result["status"] == "ok"
    return result["invoice"]


def test_reassigned_equal_quote_changes_dependency_with_same_archived_sources():
    """what_bug_this_catches: certificate reassignment once preserved dependency_hash."""
    resolver, documents = bundle()
    original = native_invoice(resolver)
    original.pop("source_sha256")
    original.pop("evidence_pointers")
    for item in original["lines"]:
        item.pop("evidence_pointers")
    alternate_hash = resolver.register_text(b"120.00")
    alternate = deepcopy(original)
    alternate["field_values"]["lines.0.billed_cents"]["pointer"] = resolver.pointer(alternate_hash, 0, 0, 6).to_dict()
    before, = run_bundle(resolver, (documents[0], documents[1], [original], documents[3]))
    after, = run_bundle(resolver, (documents[0], documents[1], [alternate], documents[3]))
    assert before["disputed_cents"] == after["disputed_cents"] == 2000
    assert before["dependency_hash"] != after["dependency_hash"]


def test_callback_refusal_and_duplicate_stable_identity_remain_unknown():
    """what_bug_this_catches: duplicate IDs and callback exceptions cannot establish zero."""
    resolver, documents = bundle(invoices=[invoice(lines=[line(reference="TYPO")])])

    def refuse(_):
        raise ValueError("stale context")

    finding, = run_bundle(resolver, documents, link_resolver=refuse)
    assert finding["expected_cents"] is None and finding["disputed_cents"] is None
    assert "link_resolver_refused" in finding["missing_facts"]
    resolver, documents = bundle(shipments=[shipment(), shipment(reference="PRO-2")])
    finding, = run_bundle(resolver, documents)
    assert finding["reason_code"] == "shipment_identity_ambiguous"
    assert finding["disputed_cents"] is None


def test_known_unsupported_inside_deadband_proposes_zero():
    """what_bug_this_catches: unsupported must still respect the monetary deadband."""
    stop = {"stop_seq": 1, "timezone": "UTC", "arrive_ts": "2026-01-06T09:00:00+00:00",
            "depart_ts": "2026-01-06T11:00:00+00:00", "detention_authorized": False,
            "liftgate_requested": False, "liftgate_authorized": False, "liftgate_performed": False}
    resolver, documents = bundle(shipments=[shipment(stops=[stop])],
                                 invoices=[invoice(lines=[line(code="LIFTGATE", stop_seq=1, billed=50)])])
    finding, = run_bundle(resolver, documents, tolerance_cents=50)
    assert (finding["verdict"], finding["expected_cents"], finding["disputed_cents"]) == ("unsupported", 0, 0)


def test_cap_and_duplicate_allocation_ignore_invoice_charge_order():
    """what_bug_this_catches: cap priority must precede cross-invoice duplicate allocation."""
    stop = {"stop_seq": 1, "timezone": "UTC", "arrive_ts": "2026-01-06T09:00:00+00:00",
            "depart_ts": "2026-01-06T11:00:00+00:00", "detention_authorized": True,
            "liftgate_requested": True, "liftgate_authorized": True, "liftgate_performed": True}
    earlier = invoice("I1", [line("LG", 5000, code="LIFTGATE", stop_seq=1),
                             line("DET", 5000, code="DETENTION", stop_seq=1)])
    later = invoice("I2", [line("DUP", 2000, code="DETENTION", stop_seq=1)],
                    issued="2026-01-08T12:00:00+00:00")
    resolver, documents = bundle([later, earlier], shipments=[shipment(stops=[stop])],
                                 contracts=[contract(accessorial_cap_cents=7000)])
    findings = run_bundle(resolver, documents)
    by_line = {item["occurrence"]["line_id"]: item for item in findings}
    assert (by_line["DET"]["expected_cents"], by_line["DET"]["disputed_cents"]) == (6000, 0)
    assert (by_line["LG"]["expected_cents"], by_line["LG"]["disputed_cents"]) == (1000, 4000)
    assert (by_line["DUP"]["expected_cents"], by_line["DUP"]["disputed_cents"]) == (0, 2000)
    assert sum(item["disputed_cents"] for item in findings) == 6000


def test_native_line_permutation_with_matching_certificates_keeps_finding_snapshot():
    """what_bug_this_catches: equivalent source observations must not churn review hashes."""
    resolver, documents = bundle()
    text = ("FREIGHTREC INVOICE V1\nCarrier: Carrier-A\nInvoice: I1\n"
            "Issued: 2026-01-07T12:00:00+00:00\nCurrency: USD\nTotal: 120.00\n"
            "Lines:\nL1|PRO-1|LH|0|USD|90.00\nL2|PRO-1|LH|0|USD|30.00\n")
    result = extract({"template_id": "freightrec-invoice-v1", "media_type": "text/plain",
                      "text": text, "resolver": resolver})
    assert result["status"] == "ok"
    original = result["invoice"]
    reordered = deepcopy(original)
    reordered["lines"].reverse()
    reordered["field_values"] = {
        ("lines.1." + key[len("lines.0."):] if key.startswith("lines.0.") else
         "lines.0." + key[len("lines.1."):] if key.startswith("lines.1.") else key): value
        for key, value in reordered["field_values"].items()
    }
    before = run_bundle(resolver, (documents[0], documents[1], [original], documents[3]))
    after = run_bundle(resolver, (documents[0], documents[1], [reordered], documents[3]))
    assert before == after
