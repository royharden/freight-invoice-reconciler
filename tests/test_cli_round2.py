"""Builder-only CLI regressions; human labels below are unit branch attribution.

No fixture represents an observed human, independent reference or benchmark.
"""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from freightrec import cli


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def bundle():
    return json.loads((ROOT / "fixtures/builder/simple-shipment.json").read_text(encoding="utf-8"))


def write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def unresolved(bundle):
    value = deepcopy(bundle)
    invoice = json.loads(value["invoices"][0])
    for line in invoice["lines"]:
        line["shipment_ref"] = "BUILDER-MANUAL-REFERENCE"
    value["invoices"] = [json.dumps(invoice)]
    return value


def run(command, tmp_path, bundle, tag, *, state=None, **options):
    source = write(tmp_path / f"input-{tag}.json", bundle)
    target = tmp_path / f"output-{tag}.json"
    args = [command, "--builder-only", "--input", str(source), "--out", str(target)]
    if state is not None:
        args += ["--state", str(state)]
    for key, value in options.items():
        args += ["--" + key.replace("_", "-"), str(value)]
    status = cli.main(args)
    return status, target


def results(tmp_path, bundle, tag, state=None):
    status, path = run("reconcile", tmp_path, bundle, tag, state=state)
    assert status == 0
    return json.loads(path.read_text(encoding="utf-8"))["findings"]


def select_lh(findings):
    return next(f for f in findings if f["occurrence"]["line_id"] == "BUILDER-LH")


def prepare_link(tmp_path, bundle, tag, state, occurrence):
    status, output = run("prepare-link", tmp_path, bundle, tag, state=state, occurrence_id=occurrence)
    assert status == 0
    return json.loads(output.read_text())["binding"]


def link_intent(binding, request, *, action="link", actor="agent_provisional"):
    intent = dict(binding, request_id=request, action=action,
                  actor_id="builder-unit-branch", actor_kind=actor,
                  note="Attribution-only builder unit vector; not a human session.")
    if action == "link":
        intent["target_shipment_id"] = "BUILDER-SHIPMENT-1"
    return intent


def seeded_link(tmp_path, bundle):
    """Explicit attribution-only branch setup, never independence evidence."""
    value = unresolved(bundle)
    state = tmp_path / "state.sqlite"
    finding = select_lh(results(tmp_path, value, "seed", state))
    binding = prepare_link(tmp_path, value, "seed-prepare", state, finding["occurrence_id"])
    event = write(tmp_path / "seed-event.json", link_intent(binding, "unit-human-link", actor="human"))
    code, _ = run("link", tmp_path, value, "seed-link", state=state,
                  occurrence_id=finding["occurrence_id"], event=event)
    assert code == 0
    linked = select_lh(results(tmp_path, value, "seed-resolved", state))
    assert linked["disputed_cents"] > 0 and not linked["missing_facts"]
    return value, state, linked, binding


def test_status_and_live_refuse_before_input_reads(tmp_path, monkeypatch, capsys):
    """what_bug_this_catches: live/admission requests must not reach source reads."""
    monkeypatch.setattr(cli, "_read", lambda *_: pytest.fail("input read before refusal"))
    assert cli.main(["status"]) == 0
    assert json.loads(capsys.readouterr().out)["A4"] == "not_run_guardrail"
    assert cli.main(["reconcile", "--live", "--input", "absent", "--out", str(tmp_path / "x")]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "live_not_enabled"
    assert cli.main(["reconcile", "--input", "absent", "--out", str(tmp_path / "x")]) == 2
    assert json.loads(capsys.readouterr().out)["status"] == "admission_pending"


def test_original_builder_reconcile_report_and_no_overwrite(tmp_path, bundle):
    """what_bug_this_catches: accepted source seams must produce actual findings/report."""
    findings = results(tmp_path, bundle, "base")
    assert len(findings) == 3
    assert all(f["disputed_cents"] > 0 and not f["missing_facts"] for f in findings)
    code, report = run("report", tmp_path, bundle, "report")
    assert code == 0 and "DRAFT, NOT SENT" in report.read_text()
    assert "http://" not in report.read_text() and "https://" not in report.read_text()
    code, _ = run("report", tmp_path, bundle, "report")
    assert code == 2


def test_provisional_link_does_not_resolve_and_exact_link_wins(tmp_path, bundle):
    """what_bug_this_catches: recorded provisional targets must not gain authority."""
    value = unresolved(bundle)
    state = tmp_path / "provisional.sqlite"
    finding = select_lh(results(tmp_path, value, "unresolved", state))
    binding = prepare_link(tmp_path, value, "prepare", state, finding["occurrence_id"])
    event = write(tmp_path / "intent.json", link_intent(binding, "provisional"))
    code, _ = run("link", tmp_path, value, "provisional", state=state,
                  occurrence_id=finding["occurrence_id"], event=event)
    assert code == 0
    assert select_lh(results(tmp_path, value, "still-unknown", state))["expected_cents"] is None
    exact = select_lh(results(tmp_path, bundle, "exact", state))
    code, _ = run("prepare-link", tmp_path, bundle, "no-override", state=state,
                  occurrence_id=exact["occurrence_id"])
    assert code == 2


@pytest.mark.parametrize("interruption", ["absent", "invalid_json", "exact", "baseline_failure"])
def test_observed_context_break_never_revives_old_link(tmp_path, bundle, monkeypatch, interruption):
    """what_bug_this_catches: A→absent/invalid/exact→A must not resurrect old rulings."""
    value, state, linked, old_binding = seeded_link(tmp_path, bundle)
    if interruption == "absent":
        empty = deepcopy(value)
        empty["invoices"] = []
        assert results(tmp_path, empty, "empty", state) == []
    elif interruption == "invalid_json":
        source = tmp_path / "invalid.json"
        source.write_text("{", encoding="utf-8")
        assert cli.main(["reconcile", "--builder-only", "--input", str(source), "--state", str(state),
                         "--out", str(tmp_path / "refused.json")]) == 2
    elif interruption == "exact":
        assert select_lh(results(tmp_path, bundle, "exact-break", state))["expected_cents"] is not None
    else:
        with monkeypatch.context() as patch:
            def invalid_baseline(*args, **kwargs):
                raise ValueError("builder baseline validation control")
            patch.setattr(cli, "_reconcile", invalid_baseline)
            code, _ = run("reconcile", tmp_path, value, "baseline-break", state=state)
            assert code == 2
    assert select_lh(results(tmp_path, value, "returned", state))["expected_cents"] is None
    stale = write(tmp_path / "stale-link.json", link_intent(old_binding, "stale-after-break", actor="human"))
    code, _ = run("link", tmp_path, value, "stale-refused", state=state,
                  occurrence_id=linked["occurrence_id"], event=stale)
    assert code == 2


def test_final_only_registration_stable_then_unlink_revokes_draft(tmp_path, bundle):
    """what_bug_this_catches: baseline registration must not churn final approval revisions.

    Human-labelled intents exercise local unit branches only, not observed human evidence.
    """
    value, state, finding, _ = seeded_link(tmp_path, bundle)
    bindings = []
    for tag in ("review-prepare-1", "review-prepare-2"):
        code, output = run("prepare-review", tmp_path, value, tag, state=state,
                           finding_id=finding["finding_id"])
        assert code == 0
        bindings.append(json.loads(output.read_text()))
    assert bindings[0] == bindings[1]
    decision = dict(bindings[1], request_id="unit-human-dispute", action="dispute",
                    actor_id="builder-unit-branch", actor_kind="human",
                    approved_cents=finding["disputed_cents"], note="Attribution-only unit branch.")
    event = write(tmp_path / "review-intent.json", decision)
    code, _ = run("review", tmp_path, value, "review", state=state,
                  finding_id=finding["finding_id"], event=event)
    assert code == 0
    code, drafts = run("draft", tmp_path, value, "drafts", state=state, finding_id=finding["finding_id"])
    assert code == 0
    files = list(drafts.glob("*.html"))
    assert len(files) == 1 and "DRAFT, NOT SENT" in files[0].read_text()
    assert "minutes not measured" in files[0].read_text()
    binding = prepare_link(tmp_path, value, "unlink-prepare", state, finding["occurrence_id"])
    event = write(tmp_path / "unlink.json", link_intent(binding, "unlink", action="unlink"))
    code, _ = run("link", tmp_path, value, "unlink", state=state,
                  occurrence_id=finding["occurrence_id"], event=event)
    assert code == 0
    code, _ = run("draft", tmp_path, value, "stale-draft", state=state, finding_id=finding["finding_id"])
    assert code == 2


def test_stale_review_binding_is_not_repaired(tmp_path, bundle):
    """what_bug_this_catches: refreshing facts must not rewrite a submitted old intent."""
    state = tmp_path / "review.sqlite"
    finding = select_lh(results(tmp_path, bundle, "first", state))
    code, output = run("prepare-review", tmp_path, bundle, "prepare-old", state=state,
                       finding_id=finding["finding_id"])
    assert code == 0
    event = dict(json.loads(output.read_text()), request_id="stale-review", action="escalate",
                 actor_id="builder-test", actor_kind="agent_provisional")
    changed = deepcopy(bundle)
    invoice = json.loads(changed["invoices"][0])
    invoice["lines"][0]["billed_cents"] += 100
    invoice["total_cents"] += 100
    changed["invoices"] = [json.dumps(invoice)]
    code, _ = run("review", tmp_path, changed, "stale-review", state=state,
                  finding_id=finding["finding_id"], event=write(tmp_path / "old-event.json", event))
    assert code == 2


def test_scripted_dispute_cannot_authorize_inert_draft(tmp_path, bundle):
    """what_bug_this_catches: CLI must preserve agent attribution through draft checks."""
    state = tmp_path / "scripted.sqlite"
    finding = select_lh(results(tmp_path, bundle, "scripted-first", state))
    code, output = run("prepare-review", tmp_path, bundle, "scripted-prepare", state=state,
                       finding_id=finding["finding_id"])
    assert code == 0
    event = dict(json.loads(output.read_text()), request_id="scripted-dispute", action="dispute",
                 actor_id="builder-script", actor_kind="agent_provisional",
                 approved_cents=finding["disputed_cents"])
    code, receipt = run("review", tmp_path, bundle, "scripted-review", state=state,
                        finding_id=finding["finding_id"], event=write(tmp_path / "scripted-event.json", event))
    assert code == 0
    assert json.loads(receipt.read_text())["actor_kind"] == "agent_provisional"
    code, drafts = run("draft", tmp_path, bundle, "scripted-draft", state=state,
                       finding_id=finding["finding_id"])
    assert code == 2 and not drafts.exists()
