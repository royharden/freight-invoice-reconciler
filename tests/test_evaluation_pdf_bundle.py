"""Builder-only PDF capability refusal controls, never independent evaluation."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

import evaluation.observations as observations
from freightrec.bundles import decode_pdf_descriptor, hydrate_original_bundle
from freightrec.engine.engine import ENGINE_VERSION
from freightrec.reconcile.findings import POLICY_VERSION
from freightrec.reconcile.reconcile import reconcile_batch


ROOT = Path(__file__).resolve().parents[1]


def freeze(documents, resolver, findings=None, links=None, strata=None):
    return observations.freeze_recording(
        documents, [] if findings is None else findings,
        {} if links is None else links, {} if strata is None else strata,
        engine_version=ENGINE_VERSION, policy_version=POLICY_VERSION,
        source_resolver=resolver)


def capture_json(bundle):
    resolver, documents = hydrate_original_bundle(bundle)
    findings = reconcile_batch(**documents, sources=resolver)
    links = {}
    for finding in findings:
        step = next(step for step in finding["trace"] if step.get("step") == "link")
        links[finding["occurrence_id"]] = {
            "status": "exact" if step["shipment_id"] else "unresolved",
            "shipment_id": step["shipment_id"],
        }
    strata = {oid: "builder" for oid in links}
    return documents, resolver, findings, links, strata


@pytest.fixture(scope="module")
def json_bundle():
    return json.loads((ROOT / "fixtures/builder/simple-shipment.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def json_capture(json_bundle):
    return capture_json(json_bundle)


@pytest.fixture(scope="module")
def pdf_descriptor():
    bundle = json.loads((ROOT / "fixtures/builder/native-pdf-bundle.json").read_text(encoding="utf-8"))
    descriptor = bundle["invoices"][0]
    assert decode_pdf_descriptor(descriptor) == (ROOT / "fixtures/builder/native-invoice-v1.pdf").read_bytes()
    return descriptor


@pytest.fixture(scope="module")
def pdf_capture():
    bundle = json.loads((ROOT / "fixtures/builder/native-pdf-bundle.json").read_text(encoding="utf-8"))
    resolver, documents = hydrate_original_bundle(bundle)
    invoice = documents["invoices"][0]
    assert invoice["source_sha256"] == sha256(
        (ROOT / "fixtures/builder/native-invoice-v1.pdf").read_bytes()).hexdigest()
    assert any(pointer["parser_profile"].endswith("-isolated-v2")
               for pointer in invoice["evidence_pointers"])
    return documents, resolver


def test_original_pdf_descriptor_refuses_before_recording_or_parser(pdf_descriptor, monkeypatch):
    """what_bug_this_catches: PDF bytes being silently converted into JSON originals."""
    import freightrec.ingest
    import freightrec.sources
    monkeypatch.setattr(freightrec.ingest, "extract", lambda *_: pytest.fail("recording parsed unsupported PDF"))
    monkeypatch.setattr(freightrec.sources, "verify_document", lambda *_: pytest.fail("descriptor treated as facts"))
    documents = {name: [] for name in ("contracts", "shipments", "invoices", "fuel_index")}
    documents["invoices"] = [pdf_descriptor]
    with pytest.raises(ValueError, match="^unsupported_source:"):
        freeze(documents, None)


@pytest.mark.parametrize("damage", ["extra_field", "noncanonical"])
def test_descriptor_validation_uses_shared_codec_before_capability_refusal(pdf_descriptor, damage):
    """what_bug_this_catches: a second, looser descriptor codec in evaluation."""
    descriptor = deepcopy(pdf_descriptor)
    if damage == "extra_field":
        descriptor["verified"] = True
    else:
        descriptor["data_base64"] = "Zh=="  # Nonzero unused pad bits; canonical encoding is Zg==.
    documents = {name: [] for name in ("contracts", "shipments", "invoices", "fuel_index")}
    documents["invoices"] = [descriptor]
    with pytest.raises(ValueError, match="^pdf_descriptor_"):
        freeze(documents, None)


def test_guarded_pdf_derived_invoice_cannot_be_frozen_as_original_json(pdf_capture):
    """what_bug_this_catches: stripping the descriptor after ingest bypassing PDF refusal."""
    documents, resolver = pdf_capture
    with pytest.raises(ValueError, match="^unsupported_source:"):
        freeze(documents, resolver)


@pytest.mark.parametrize("flavor", ["descriptor", "guarded_invoice"])
@pytest.mark.parametrize("consumer", ["load", "product_input", "diagnostic_outputs", "scoring_observations"])
def test_hash_valid_snapshot_still_rejects_pdf_replay_and_diagnostics(
        json_capture, pdf_descriptor, pdf_capture, flavor, consumer, monkeypatch):
    """what_bug_this_catches: manually rehashed snapshots bypassing the source-flavor gate."""
    documents, resolver, findings, links, strata = json_capture
    payload = freeze(documents, resolver, findings, links, strata).load()
    invoice = pdf_descriptor if flavor == "descriptor" else pdf_capture[0]["invoices"][0]
    payload["source_documents"]["invoices"] = [deepcopy(invoice)]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    snapshot = observations.FrozenObservations(encoded, sha256(encoded.encode("utf-8")).hexdigest())
    monkeypatch.setattr(observations, "a0", lambda *_: pytest.fail("A0 ran on unsupported PDF edition"))
    monkeypatch.setattr(observations, "a1", lambda *_: pytest.fail("A1 ran on unsupported PDF edition"))
    with pytest.raises(ValueError, match="^unsupported_source:"):
        if consumer == "load":
            snapshot.load()
        elif consumer == "scoring_observations":
            observations.scoring_observations(snapshot, {})
        else:
            getattr(observations, consumer)(snapshot)


@pytest.mark.parametrize("extra", [{"field_values": {}}, {"verified": True}],
                         ids=["empty_field_values", "extra_field"])
@pytest.mark.parametrize("consumer", ["load", "product_input", "diagnostic_outputs", "scoring_observations"])
def test_hash_valid_snapshot_cannot_disguise_pdf_descriptor_as_json(
        json_capture, pdf_descriptor, extra, consumer, monkeypatch):
    """what_bug_this_catches: empty field_values bypassing descriptor validation on replay."""
    documents, resolver, findings, links, strata = json_capture
    payload = freeze(documents, resolver, findings, links, strata).load()
    payload["source_documents"]["invoices"] = [dict(deepcopy(pdf_descriptor), **extra)]
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    snapshot = observations.FrozenObservations(encoded, sha256(encoded.encode("utf-8")).hexdigest())
    monkeypatch.setattr(observations, "a0", lambda *_: pytest.fail("A0 ran on malformed PDF descriptor"))
    monkeypatch.setattr(observations, "a1", lambda *_: pytest.fail("A1 ran on malformed PDF descriptor"))
    with pytest.raises(ValueError, match="^pdf_descriptor_"):
        if consumer == "load":
            snapshot.load()
        elif consumer == "scoring_observations":
            references = {row["occurrence_id"]: None for row in payload["rows"]}
            observations.scoring_observations(snapshot, references)
        else:
            getattr(observations, consumer)(snapshot)


def test_original_json_capture_and_replay_remain_compatible(json_capture):
    """what_bug_this_catches: PDF refusal accidentally breaking the accepted JSON path."""
    documents, resolver, findings, links, strata = json_capture
    snapshot = freeze(documents, resolver, findings, links, strata)
    assert observations.product_input(snapshot) == documents
    universe = set(links)
    assert all(set(output) == universe for output in observations.diagnostic_outputs(snapshot)["arm_outputs"].values())
    assert all(row["reference_cents"] is None for row in
               observations.scoring_observations(snapshot, {oid: None for oid in universe}))
    assert "reference_cents" not in snapshot.canonical_json


def test_json_business_fact_named_parser_profile_is_not_pdf_evidence(json_bundle):
    """what_bug_this_catches: ordinary JSON facts being confused with PDF pointer metadata."""
    bundle = deepcopy(json_bundle)
    invoice = json.loads(bundle["invoices"][0])
    invoice["description"] = {"parser_profile": "pdfplumber-business-fact"}
    bundle["invoices"] = [json.dumps(invoice)]
    documents, resolver, findings, links, strata = capture_json(bundle)
    snapshot = freeze(documents, resolver, findings, links, strata)
    assert observations.product_input(snapshot) == documents
