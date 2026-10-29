"""Builder-only integer regression controls; no independent corpus or gold data."""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from evaluation.bootstrap import paired_bootstrap, raw_bootstrap
from evaluation.components import connected_components, inspect_splits
from evaluation.metrics import score_arm
from evaluation.observations import (
    diagnostic_outputs,
    freeze_recording,
    product_input,
    scoring_observations,
)
from evaluation.report import development_report, jsonl, not_run_report, report_json
from evaluation.run_eval import run_confirmatory, run_development
from evaluation.sizing import analytic_policy, n_req
from freightrec.engine.engine import ENGINE_VERSION
from freightrec.reconcile.findings import POLICY_VERSION
from freightrec.reconcile.reconcile import reconcile_batch
from freightrec.sources import SourceResolver


def observation(oid, billed, reference, component=None, stratum="builder"):
    return {"occurrence_id": oid, "component_id": component or oid,
            "stratum": stratum, "billed_cents": billed, "reference_cents": reference,
            "carrier": "BUILDER", "invoice_id": "INVOICE-" + oid}


def proposal(amount=0, status=None):
    return {"disputed_cents": amount,
            "status": status or ("proposed" if amount else "clear")}


@pytest.mark.parametrize("invalid", [
    None, [], {}, {"a": None}, {"a": proposal(101)}, {"a": proposal(-1)},
    {"a": proposal(True)}, {"a": proposal(1.0)}, {"a": proposal(1, "abstain")},
    {"a": proposal(0, "proposed")}, {"other": proposal(1)},
])
def test_invalid_attempt_never_gets_a_valid_subset_score(invalid):
    """what_bug_this_catches: malformed/missing/over-billed rows shrinking an arm."""
    result = score_arm([observation("a", 100, 0)], invalid)
    assert result["status"] == "invalid_arm"
    assert result["metrics"] is None and result["components"] is None
    assert result["attempted_output"] is invalid
    assert result["errors"]


def test_abstention_cannot_beat_complete_correct_dispute():
    """what_bug_this_catches: tiny/selective proposals receiving credit for missed dollars."""
    rows = [observation("small", 100, 0), observation("expensive", 10000, 0)]
    correct = score_arm(rows, {"small": proposal(100), "expensive": proposal(10000)})
    partial = score_arm(rows, {"small": proposal(1), "expensive": proposal(1)})
    abstain = score_arm(rows, {oid: proposal(0, "abstain") for oid in ("small", "expensive")})
    selective = score_arm(rows, {"small": proposal(100), "expensive": proposal(0, "abstain")})
    assert correct["metrics"]["c2_cents"] == 0
    assert [item["metrics"]["mo_cents"] for item in (partial, abstain, selective)] == [10098, 10100, 10000]
    assert all(item["metrics"]["c2_cents"] > correct["metrics"]["c2_cents"]
               for item in (partial, abstain, selective))


def test_unknown_exposure_and_zero_denominators_are_separate():
    """what_bug_this_catches: unknown reference dollars treated as known zero error."""
    rows = [observation("unknown", 100, None), observation("zero", 0, 0)]
    metrics = score_arm(rows, {"unknown": proposal(17), "zero": proposal()})["metrics"]
    assert metrics["unsupported_exposure_cents"] == 17
    assert metrics["billed_cents"] == 0
    assert metrics["fd_billed_rate"] is None
    assert metrics["fd_overcharge_rate"] is None
    assert metrics["mo_rate"] is None
    assert metrics["unknown_abstention_accuracy"] == 0


@pytest.mark.parametrize("tolerance,expected", [(0, 50), (50, 0), (100, 0)])
def test_deadband_is_strict_and_does_not_subtract_margin(tolerance, expected):
    """what_bug_this_catches: >= deadband or subtracting tolerance from eligible overage."""
    result = score_arm([observation("a", 150, 100)], {"a": proposal()}, tolerance)
    assert result["metrics"]["oracle_overcharge_cents"] == expected


def test_component_identity_is_order_independent_and_namespace_aware():
    """what_bug_this_catches: invoice splits or cross-carrier ID collisions leaking copies."""
    rows = [
        {"occurrence_id": "a", "carrier": "A", "invoice_id": "one", "shipment_id": "s"},
        {"occurrence_id": "b", "carrier": "A", "invoice_id": "two", "shipment_id": "s"},
        {"occurrence_id": "c", "carrier": "B", "invoice_id": "one", "shipment_id": "s"},
    ]
    result = connected_components(rows)
    assert result == connected_components(list(reversed(rows)))
    assert result["a"] == result["b"] != result["c"]
    shared_copy = deepcopy(rows)
    shared_copy[0]["document_sha256"] = shared_copy[2]["document_sha256"] = "original-copy"
    assert len(set(connected_components(shared_copy).values())) == 1
    split_rows = [dict(row, split="pilot" if row["occurrence_id"] == "a" else "dev") for row in rows]
    assert inspect_splits(split_rows)["status"] == "fail"


def test_bootstrap_keeps_whole_components_and_strata():
    """what_bug_this_catches: independent line resampling splitting an invoice component."""
    rows = [observation("a", 100, 0, "same", "one"),
            observation("b", 200, 0, "same", "one"),
            observation("c", 1000, 1000, "other", "two")]
    arm = score_arm(rows, {row["occurrence_id"]: proposal(0, "abstain") for row in rows})
    raw = raw_bootstrap(arm, draws=32, seed=13)
    assert raw["stratum_counts"] == {"one": 1, "two": 1}
    assert raw["estimates"]["mo_cents"]["observed"] == 300
    assert raw["estimates"]["mo_cents"]["status"] == "degenerate"
    assert raw["estimates"]["mo_cents"]["low"] is None
    paired = paired_bootstrap(arm, arm, draws=32, seed=13)
    assert all(item["status"] == "degenerate" and item["observed"] == 0
               for item in paired["deltas"].values())


def test_paired_rate_is_ratio_of_sums_and_seed_reproducible():
    """what_bug_this_catches: averaging unequal line rates instead of dollar denominators."""
    rows = [observation("small", 10, 0), observation("large", 90, 0)]
    candidate = score_arm(rows, {"small": proposal(10), "large": proposal()})
    baseline = score_arm(rows, {"small": proposal(), "large": proposal(90)})
    result = paired_bootstrap(candidate, baseline, draws=64, seed=11)
    assert result == paired_bootstrap(candidate, baseline, draws=64, seed=11)
    assert result["deltas"]["mo_rate"]["observed"] == pytest.approx(.8)
    assert result["deltas"]["c2_per_component_cents"]["observed"] == 40
    assert result["deltas"]["mo_rate"]["status"] == "estimated"
    assert raw_bootstrap(candidate, draws=64, seed=11)["estimates"]["mo_rate"]["observed"] == pytest.approx(.9)


@pytest.fixture
def original_capture():
    """Original non-independent builder documents, never an oracle or held-out sample."""
    bundle = json.loads((Path(__file__).resolve().parents[1] / "fixtures" / "builder" /
                         "simple-shipment.json").read_text(encoding="utf-8"))
    resolver = SourceResolver()
    documents = {key: [resolver.register_document(raw.encode("utf-8")) for raw in bundle[key]]
                 for key in ("contracts", "shipments", "invoices", "fuel_index")}
    findings = reconcile_batch(**documents, sources=resolver, tolerance_cents=0)
    links = {}
    for finding in findings:
        target = next(step["shipment_id"] for step in finding["trace"] if step.get("step") == "link")
        links[finding["occurrence_id"]] = {
            "status": "exact" if target else "unresolved", "shipment_id": target}
    strata = {oid: "builder" for oid in links}
    return documents, findings, links, strata, resolver


def freeze(capture, findings=None, tolerance=0):
    documents, actual, links, strata, resolver = capture
    return freeze_recording(documents, actual if findings is None else findings, links, strata,
                            engine_version=ENGINE_VERSION, policy_version=POLICY_VERSION,
                            source_resolver=resolver, tolerance_cents=tolerance)


def test_recording_replays_original_facts_without_reference_labels(original_capture):
    """what_bug_this_catches: per-arm copies or scoring labels leaking into product replay."""
    snapshot = freeze(original_capture)
    payload = snapshot.load()
    outputs = diagnostic_outputs(snapshot)
    universe = {row["occurrence_id"] for row in payload["rows"]}
    assert all(set(outputs["arm_outputs"][arm]) == universe for arm in ("A0", "A1", "A2"))
    assert outputs["tolerance_cents"] == payload["tolerance_cents"] == 0
    assert product_input(snapshot) == original_capture[0]
    scoring = scoring_observations(snapshot, {oid: None for oid in universe})
    assert all(row["reference_cents"] is None for row in scoring)
    assert "reference_cents" not in snapshot.canonical_json
    with pytest.raises(ValueError, match="exact frozen"):
        scoring_observations(snapshot, {})
    changed = product_input(snapshot)
    changed["invoices"][0]["lines"][0]["billed_cents"] += 1
    assert product_input(snapshot) == original_capture[0]


@pytest.mark.parametrize("damage", ["mismatch", "missing", "duplicate", "boolean"])
def test_actual_a2_deadband_must_match_capture_without_row_loss(original_capture, damage):
    """what_bug_this_catches: A2 at another tolerance getting a valid same-observation score."""
    findings = deepcopy(original_capture[1])
    trace = findings[0]["trace"]
    allocation = next(step for step in trace if step.get("step") == "allocation")
    if damage == "mismatch":
        allocation["deadband_cents"] = 100
    elif damage == "missing":
        findings[0]["trace"] = [step for step in trace if step.get("step") != "allocation"]
    elif damage == "duplicate":
        trace.append(deepcopy(allocation))
    else:
        allocation["deadband_cents"] = False
    snapshot = freeze(original_capture, findings)
    outputs = diagnostic_outputs(snapshot)
    refs = {row["occurrence_id"]: None for row in snapshot.load()["rows"]}
    result = score_arm(scoring_observations(snapshot, refs), outputs["arm_outputs"]["A2"])
    assert result["status"] == "invalid_arm"
    assert len(snapshot.load()["rows"]) == len(original_capture[1])
    assert result["metrics"] is None


def test_missing_a2_and_mutated_source_never_become_successful_subsets(original_capture):
    """what_bug_this_catches: omitted candidate rows or modified typed facts being silently filled."""
    snapshot = freeze(original_capture, original_capture[1][1:])
    rows = snapshot.load()["rows"]
    scoring = scoring_observations(snapshot, {row["occurrence_id"]: None for row in rows})
    assert score_arm(scoring, diagnostic_outputs(snapshot)["arm_outputs"]["A2"])["status"] == "invalid_arm"
    documents, findings, links, strata, resolver = original_capture
    tampered = deepcopy(documents)
    tampered["invoices"][0]["lines"][0]["billed_cents"] += 1
    with pytest.raises(ValueError):
        freeze_recording(tampered, findings, links, strata, engine_version=ENGINE_VERSION,
                         policy_version=POLICY_VERSION, source_resolver=resolver)


def test_reports_retain_invalid_attempt_and_never_claim_hidden_run():
    """what_bug_this_catches: invalid output or unknown hidden cells disappearing from artifacts."""
    run = run_development([observation("a", 100, 0)], {"A2": {"a": proposal(float("nan"))}}, draws=16)
    report = development_report(run)
    parsed = json.loads(report_json(report))
    assert parsed["claim"] == "not_established"
    invalid = next(row for row in parsed["rows"] if row["slice"] == "dev" and row["arm"] == "A2")
    assert invalid["status"] == "invalid_arm" and invalid["c2_cents"] is None
    assert invalid["attempted_output"]["a"]["disputed_cents"] == {"invalid_nonfinite_float": "nan"}
    assert all(row["status"] in ("not_run", "not_run_guardrail", "not_applicable")
               for row in parsed["rows"] if row["slice"] != "dev")
    records = [json.loads(line) for line in jsonl(report).splitlines()]
    assert any(item.get("section") == "failure_registry" for item in records)
    assert any(item.get("section") == "retained_run" for item in records)
    assert all(row["c2_cents"] is None for row in not_run_report()["rows"])
    with pytest.raises(PermissionError):
        run_confirmatory()


def test_sizing_nonfinite_is_explicit_and_no_campaign_is_authorized():
    """what_bug_this_catches: zero mean/bool/nonfinite controls creating a finite success size."""
    assert n_req([1, 2, 3])["value"] == 16
    for values in ([0, 0], [True, 2], [1, float("nan")]):
        requirement = n_req(values)
        assert requirement["value"] is None
        json.dumps(requirement, allow_nan=False)
    policy = analytic_policy([0, 0], [1, 2], [-1, -2], [-1, -2])
    assert policy["status"] == "stop_admission_nonfinite"
    assert policy["hidden_generation_authorized"] is False
