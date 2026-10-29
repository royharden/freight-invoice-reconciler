"""Original-PDF observation regressions; all data are builder-only logical vectors."""

import base64
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

import evaluation.observations as observations
from evaluation.metrics import score_arm
from freightrec import bundles
from freightrec.engine.engine import ENGINE_VERSION
from freightrec.reconcile.findings import POLICY_VERSION
from freightrec.reconcile.reconcile import reconcile_batch
from freightrec.sources import verify_document


ROOT = Path(__file__).resolve().parents[1]
CONSUMERS = ("load", "product_input", "diagnostic_outputs", "scoring_observations")


def capture(bundle):
    resolver, documents = bundles.hydrate_original_bundle(bundle)
    findings = reconcile_batch(**documents, sources=resolver)
    links = {}
    for finding in findings:
        step = next(item for item in finding["trace"] if item.get("step") == "link")
        links[finding["occurrence_id"]] = {
            "status": "exact" if step["shipment_id"] else "unresolved",
            "shipment_id": step["shipment_id"],
        }
    return documents, resolver, findings, links, {oid: "builder" for oid in links}


def freeze(bundle, recording, *, findings=None, documents=None, **kwargs):
    source, resolver, actual, links, strata = recording
    return observations.freeze_original_bundle_recording(
        bundle, source if documents is None else documents,
        actual if findings is None else findings, links, strata,
        engine_version=ENGINE_VERSION, policy_version=POLICY_VERSION,
        source_resolver=resolver, **kwargs)


def rehash(payload):
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                         ensure_ascii=False, allow_nan=False)
    return observations.FrozenObservations(encoded, sha256(encoded.encode("utf-8")).hexdigest())


def consume(snapshot, consumer, occurrence_ids):
    if consumer == "load":
        return snapshot.load()
    if consumer == "scoring_observations":
        # Complete external unknown labels, never a missing-reference shortcut.
        return observations.scoring_observations(snapshot, {oid: None for oid in occurrence_ids})
    return getattr(observations, consumer)(snapshot)


@pytest.fixture(scope="module")
def original_bundle():
    return json.loads((ROOT / "fixtures/builder/native-pdf-bundle.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def recording(original_bundle):
    return capture(original_bundle)


@pytest.fixture(scope="module")
def frozen(original_bundle, recording):
    snapshot = freeze(original_bundle, recording)
    return snapshot, snapshot.load()


def test_capture_rehydrates_with_the_actual_retained_resolver(original_bundle, recording, monkeypatch):
    """what_bug_this_catches: capture accepting facts verified against a replacement archive."""
    original_hydrate = bundles.hydrate_original_bundle
    resolvers = []

    def tracked(bundle, *, resolver=None):
        resolvers.append(resolver)
        return original_hydrate(bundle, resolver=resolver)

    monkeypatch.setattr(bundles, "hydrate_original_bundle", tracked)
    snapshot = freeze(original_bundle, recording)
    assert resolvers == [recording[1]]
    snapshot.load()
    assert resolvers == [recording[1], None]


def test_original_bytes_quotes_typed_values_and_common_arms_survive_replay(
        original_bundle, recording, frozen):
    """what_bug_this_catches: replay replacing original PDF evidence with derived JSON facts."""
    snapshot, payload = frozen
    assert payload["adapter_version"] == "freightrec-observation-v2-originals"
    assert observations.ADAPTER_VERSION == "freightrec-observation-v1"
    assert payload["original_bundle"] == original_bundle
    replay = observations.product_input(snapshot)
    assert replay == original_bundle
    assert set(replay) == set(original_bundle)
    raw = (ROOT / "fixtures/builder/native-invoice-v1.pdf").read_bytes()
    assert bundles.decode_pdf_descriptor(replay["invoices"][0]) == raw
    resolver, documents = bundles.hydrate_original_bundle(replay)
    assert documents == recording[0] == payload["source_documents"]
    invoice = documents["invoices"][0]
    assert invoice["source_sha256"] == sha256(raw).hexdigest()
    assert verify_document(invoice, resolver)
    for field in invoice["field_values"].values():
        pointer = field["pointer"]
        assert pointer["source_sha256"] == sha256(raw).hexdigest()
        assert pointer["parser_profile"].endswith("-isolated-v2")
        assert pointer["page_index"] == 0
        assert resolver.resolve(pointer) == field["raw_quote"]
    amount = invoice["field_values"]["lines.0.billed_cents"]
    assert amount["raw_quote"] == "1400.00"
    assert type(amount["typed_value"]) is int and amount["typed_value"] == 140000
    outputs = observations.diagnostic_outputs(snapshot)
    universe = {row["occurrence_id"] for row in payload["rows"]}
    assert len(universe) == 3
    assert all(set(arm) == universe for arm in outputs["arm_outputs"].values())
    assert outputs["arm_outputs"]["A2"] == payload["a2_attempt"]
    assert outputs["snapshot_sha256"] == snapshot.sha256
    assert outputs["tolerance_cents"] == payload["tolerance_cents"] == 0


def test_reference_join_and_returned_copies_cannot_change_original_product_input(frozen, original_bundle):
    """what_bug_this_catches: external scoring labels or mutable copies leaking into replay."""
    snapshot, payload = frozen
    references = {row["occurrence_id"]: None for row in payload["rows"]}
    references[next(iter(references))] = 1  # A tiny logical vector, not adjudicated truth.
    scored = observations.scoring_observations(snapshot, references)
    assert {row["occurrence_id"]: row["reference_cents"] for row in scored} == references
    replay = observations.product_input(snapshot)
    assert replay == original_bundle
    assert "reference_cents" not in json.dumps(replay)
    assert "field_values" not in json.dumps(replay)
    replay["invoices"][0]["data_base64"] = "changed-returned-copy"
    scored[0]["billed_cents"] = 0
    assert observations.product_input(snapshot) == original_bundle


INVALID_ENVELOPE_METADATA = (
    pytest.param("data_origin", {"reference_cents": {"builder_occurrence": 12345},
                                 "expected_cents": 99}, id="nested-labels"),
    pytest.param("data_origin", {"note": "builder_non_independent"}, id="unknown-object"),
    pytest.param("data_origin", [{"gold_cents": 99}], id="label-list"),
    pytest.param("data_origin", None, id="null"),
    pytest.param("data_origin", True, id="boolean"),
    pytest.param("data_origin", 99, id="number"),
    pytest.param("data_origin", "reference_cents=99", id="label-string"),
    pytest.param("data_origin", "independent", id="unknown-marker"),
    pytest.param("data_origin", "", id="empty-marker"),
    pytest.param("reference_cents", {"builder_occurrence": 99}, id="root-label"),
    pytest.param("notes", {"expected_cents": 99}, id="root-extra"),
)


@pytest.mark.parametrize("key,metadata", INVALID_ENVELOPE_METADATA)
def test_capture_rejects_original_envelope_metadata(original_bundle, recording, key, metadata):
    """what_bug_this_catches: ignored original metadata carrying labels into product replay."""
    original = deepcopy(original_bundle)
    original[key] = deepcopy(metadata)
    before = deepcopy(original)
    with pytest.raises(ValueError, match="original bundle (fields|data_origin)"):
        freeze(original, recording)
    assert original == before  # Reject the complete original, never strip its metadata.


@pytest.mark.parametrize("consumer", CONSUMERS)
@pytest.mark.parametrize("key,metadata", INVALID_ENVELOPE_METADATA)
def test_rehashed_original_envelope_metadata_refuses_every_consumer(frozen, key, metadata, consumer):
    """what_bug_this_catches: rehashing label-bearing ignored metadata bypassing capture checks."""
    _, original_payload = frozen
    payload = deepcopy(original_payload)
    payload["original_bundle"][key] = deepcopy(metadata)
    snapshot = rehash(payload)
    before = snapshot.canonical_json
    with pytest.raises(ValueError, match="original bundle (fields|data_origin)"):
        consume(snapshot, consumer, [row["occurrence_id"] for row in payload["rows"]])
    assert snapshot.canonical_json == before


def test_absent_optional_origin_preserves_exact_original_envelope(original_bundle, recording):
    """what_bug_this_catches: metadata validation adding or requiring an optional codec marker."""
    original = deepcopy(original_bundle)
    del original["data_origin"]
    snapshot = freeze(original, recording)
    payload = snapshot.load()
    assert payload["original_bundle"] == original
    assert observations.product_input(snapshot) == original
    assert "data_origin" not in original
    outputs = observations.diagnostic_outputs(snapshot)["arm_outputs"]
    scored = observations.scoring_observations(snapshot, {oid: None for oid in recording[3]})
    assert set(outputs["A2"]) == {row["occurrence_id"] for row in scored} == set(recording[3])


def damage_payload(payload, damage):
    invoice = payload["source_documents"]["invoices"][0]
    if damage == "original_pdf_bytes":
        descriptor = payload["original_bundle"]["invoices"][0]
        raw = bundles.decode_pdf_descriptor(descriptor)
        # A valid PDF comment changes original SHA without reconstructing source facts.
        descriptor["data_base64"] = base64.b64encode(raw + b"\n% builder altered original\n").decode("ascii")
    elif damage == "original_json_bytes":
        payload["original_bundle"]["shipments"][0] += "\n "
    elif damage == "source_sha":
        invoice["source_sha256"] = "0" * 64
    elif damage == "reassigned_field_pointer":
        invoice["field_values"]["lines.0.billed_cents"]["pointer"] = deepcopy(
            invoice["field_values"]["lines.1.billed_cents"]["pointer"])
    elif damage == "quote":
        invoice["field_values"]["lines.0.billed_cents"]["raw_quote"] = "1400.01"
    elif damage == "typed_value":
        invoice["field_values"]["lines.0.billed_cents"]["typed_value"] = 140001
    elif damage == "profile":
        invoice["evidence_pointers"][0]["parser_profile"] += "-changed"
    elif damage == "normalizer":
        invoice["field_values"]["lines.0.billed_cents"]["normalizer_id"] = "string-v1"
    elif damage == "rows":
        payload["rows"][0]["billed_cents"] += 1
    elif damage == "contracts":
        payload["contracts"][0]["minimum_cents"] += 1
    elif damage == "fuel_index":
        payload["fuel_index"][0]["index_value"] = "9.99"
    elif damage == "a2_attempt":
        next(iter(payload["a2_attempt"].values()))["disputed_cents"] += 1
    elif damage == "link":
        next(iter(payload["links"].values())).update(status="unresolved", shipment_id=None)
    elif damage == "stratum":
        oid = next(iter(payload["strata"]))
        payload["strata"][oid] = "changed-builder-stratum"
    elif damage == "near_duplicate":
        payload["near_duplicate_ids"][payload["rows"][0]["occurrence_id"]] = "changed-builder-copy"
    elif damage == "tolerance":
        payload["tolerance_cents"] = 50
    elif damage == "unknown_version":
        payload["adapter_version"] = "freightrec-observation-v999"
    elif damage == "extra_root":
        payload["verified"] = True
    elif damage == "engine":
        payload["engine_version"] += "-changed"
    elif damage == "policy":
        payload["policy_version"] += "-changed"
    else:
        raise AssertionError(damage)


@pytest.mark.parametrize("consumer", CONSUMERS)
@pytest.mark.parametrize("damage", [
    "original_pdf_bytes", "original_json_bytes", "source_sha", "reassigned_field_pointer",
    "quote", "typed_value", "profile", "normalizer", "rows", "contracts", "fuel_index",
    "a2_attempt", "link", "stratum", "near_duplicate", "tolerance",
    "unknown_version", "extra_root", "engine", "policy",
])
def test_rehashed_changed_source_or_derivation_refuses_every_consumer(frozen, damage, consumer, monkeypatch):
    """what_bug_this_catches: recomputing a public hash bypassing canonical source edition checks."""
    _, original_payload = frozen
    payload = deepcopy(original_payload)
    damage_payload(payload, damage)
    snapshot = rehash(payload)
    monkeypatch.setattr(observations, "a0", lambda *_: pytest.fail("A0 ran before source refusal"))
    monkeypatch.setattr(observations, "a1", lambda *_: pytest.fail("A1 ran before source refusal"))
    with pytest.raises(ValueError):
        consume(snapshot, consumer, [row["occurrence_id"] for row in original_payload["rows"]])


@pytest.mark.parametrize("damage", ["source_sha", "reassigned_field_pointer", "quote", "typed_value", "profile", "normalizer"])
def test_capture_rejects_changed_full_supplied_binding(original_bundle, recording, damage):
    """what_bug_this_catches: capture checking only amount/SHA while accepting reassigned evidence."""
    payload = {"source_documents": deepcopy(recording[0])}
    damage_payload(payload, damage)
    with pytest.raises(ValueError):
        freeze(original_bundle, recording, documents=payload["source_documents"])


@pytest.mark.parametrize("consumer", CONSUMERS)
@pytest.mark.parametrize("format_name", ["v1", "v2"])
@pytest.mark.parametrize("extra", [{"field_values": {}}, {"verified": True}], ids=["empty_fields", "extra_field"])
def test_descriptor_extras_refuse_old_and_new_formats(frozen, original_bundle, format_name, extra, consumer):
    """what_bug_this_catches: descriptor plus empty field_values reviving the old replay bypass."""
    _, original_payload = frozen
    payload = deepcopy(original_payload)
    if format_name == "v1":
        for key in ("original_bundle", "links", "strata", "near_duplicate_ids", "runtime_edition"):
            payload.pop(key)
        payload["adapter_version"] = observations.ADAPTER_VERSION
        payload["source_documents"]["invoices"] = [dict(deepcopy(original_bundle["invoices"][0]), **extra)]
    else:
        payload["original_bundle"]["invoices"][0].update(deepcopy(extra))
    with pytest.raises(ValueError, match="^pdf_descriptor_"):
        consume(rehash(payload), consumer, [row["occurrence_id"] for row in original_payload["rows"]])


@pytest.mark.parametrize("consumer", CONSUMERS)
@pytest.mark.parametrize("reason", ["pdf_worker_unavailable", "pdf_worker_timeout"])
def test_canonical_worker_refusal_propagates_without_fallback(frozen, monkeypatch, consumer, reason):
    """what_bug_this_catches: replay falling back to saved parsed facts when guarded parsing fails."""
    snapshot, payload = frozen
    calls = []

    def refused(*args, **kwargs):
        calls.append((args, kwargs))
        raise ValueError("pdf_ingest_refused:" + reason)

    monkeypatch.setattr(bundles, "hydrate_original_bundle", refused)
    with pytest.raises(ValueError, match=reason):
        consume(snapshot, consumer, [row["occurrence_id"] for row in payload["rows"]])
    assert len(calls) == 1


@pytest.mark.parametrize("reason", ["pdf_worker_unavailable", "pdf_worker_timeout"])
def test_capture_propagates_canonical_worker_refusal(original_bundle, recording, monkeypatch, reason):
    """what_bug_this_catches: capture falling back to supplied derived documents after parser refusal."""
    def refused(*_args, **_kwargs):
        raise ValueError("pdf_ingest_refused:" + reason)

    monkeypatch.setattr(bundles, "hydrate_original_bundle", refused)
    with pytest.raises(ValueError, match=reason):
        freeze(original_bundle, recording)


@pytest.mark.parametrize("consumer", CONSUMERS)
def test_installed_dependency_edition_change_refuses_before_hydration(frozen, monkeypatch, consumer):
    """what_bug_this_catches: upgrading parser dependencies silently retuning a frozen edition."""
    snapshot, payload = frozen
    installed_version = observations.version
    monkeypatch.setattr(observations, "version", lambda package: "builder-changed-version" if package == "pdfplumber" else installed_version(package))
    monkeypatch.setattr(bundles, "hydrate_original_bundle", lambda *_args, **_kwargs: pytest.fail("parsed after edition changed"))
    with pytest.raises(ValueError, match="edition changed"):
        consume(snapshot, consumer, [row["occurrence_id"] for row in payload["rows"]])


@pytest.mark.parametrize("consumer", CONSUMERS)
def test_fresh_canonical_parser_profile_change_refuses(frozen, monkeypatch, consumer):
    """what_bug_this_catches: matching original bytes accepted despite a new extraction profile."""
    snapshot, payload = frozen
    hydrate = bundles.hydrate_original_bundle

    def changed_profile(*args, **kwargs):
        resolver, documents = hydrate(*args, **kwargs)
        documents["invoices"][0]["evidence_pointers"][0]["parser_profile"] += "-new-edition"
        return resolver, documents

    monkeypatch.setattr(bundles, "hydrate_original_bundle", changed_profile)
    with pytest.raises(ValueError, match="source edition differs"):
        consume(snapshot, consumer, [row["occurrence_id"] for row in payload["rows"]])


@pytest.mark.parametrize("malformed", ["missing", "duplicate", "nonmapping", "bad_deadband"])
def test_malformed_a2_attempt_preserves_full_denominator_and_invalidates_whole_arm(
        original_bundle, recording, malformed):
    """what_bug_this_catches: fixing or dropping invalid A2 attempts before builder-only scoring."""
    findings = deepcopy(recording[2])
    if malformed == "missing":
        findings.pop()
    elif malformed == "duplicate":
        findings.append(deepcopy(findings[0]))
    elif malformed == "nonmapping":
        findings[0] = "malformed builder attempt"
    else:
        next(step for step in findings[0]["trace"] if step.get("step") == "allocation")["deadband_cents"] = True
    snapshot = freeze(original_bundle, recording, findings=findings)
    payload = snapshot.load()
    assert payload["recorded_findings"] == findings
    references = {oid: None for oid in recording[3]}
    scored = observations.scoring_observations(snapshot, references)
    outputs = observations.diagnostic_outputs(snapshot)["arm_outputs"]
    assert len(scored) == len(references) == 3
    assert set(outputs["A0"]) == set(outputs["A1"]) == set(references)
    assert outputs["A2"] == payload["a2_attempt"]
    result = score_arm(scored, outputs["A2"])
    assert result["status"] == "invalid_arm"
    assert result["metrics"] is result["components"] is None
    assert result["attempted_output"] == payload["a2_attempt"]


def test_v1_json_recording_still_uses_original_compatible_api():
    """what_bug_this_catches: introducing v2 silently reclassifying legitimate JSON v1 records."""
    bundle = json.loads((ROOT / "fixtures/builder/simple-shipment.json").read_text(encoding="utf-8"))
    documents, resolver, findings, links, strata = capture(bundle)
    snapshot = observations.freeze_recording(
        documents, findings, links, strata, engine_version=ENGINE_VERSION,
        policy_version=POLICY_VERSION, source_resolver=resolver)
    assert snapshot.load()["adapter_version"] == observations.ADAPTER_VERSION
    assert observations.product_input(snapshot) == documents
    assert set(observations.diagnostic_outputs(snapshot)["arm_outputs"]["A2"]) == set(links)
