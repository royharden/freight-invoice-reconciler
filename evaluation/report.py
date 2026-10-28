"""JSON-compatible unrun templates and deterministic Markdown from retained results."""

import json
from math import isfinite

from .arms import model_arm_status

ARMS = ("A0", "A1", "A2", "A2s", "A3", "A4", "REF/O agreement", "G-agreement")
SLICES = ("dev", "H-in", "H-out")
GATE_NAMES = ("C2_vs_A0", "C2_vs_A1", "MO_vs_A0", "MO_vs_A1", "FD_vs_A0", "FD_vs_A1",
              "valid_arm", "unknown_exposure", "injection", "independent_reference",
              "custody", "disagreements", "agreement_audits", "human_spot_check")
DELTA_SPECS = (("c2_per_component_cents", "C2", 0, "upper < threshold"),
               ("mo_rate", "MO", 0, "upper < threshold"),
               ("fd_billed_rate", "FD", .001, "upper <= threshold"))
FAILURE_REGISTRY = (
    "RATE_DATE/F2", "INDEX_WEEK/F3", "FUEL_BASE/F4", "MIN_MASK/BAND_EDGE/F13",
    "FREE_TIME/INCREMENT/DST_ELAPSED/F5", "AUTH_CAP/F6/F8", "DUP_ALLOC/F7",
    "LINK_AMBIGUOUS/F9", "MISSING_FACT/F14", "SPAN_INVALID/EXTRACTION_INVALID/F10",
    "INJECTION/F11", "STALE_REVIEW", "ORACLE_DISAGREEMENT/F12", "AGREEMENT_AUDIT/F15",
    "INVALID_ARM/F16", "WRONGLY_CLEARED/F1", "PROVIDER_UNMEASURED",
)
RESULT_COLUMNS = (
    "components", "occurrences", "adjudicable_billed_cents", "oracle_overcharge_cents",
    "c2_cents", "c2_ci", "correct_proposed_cents", "fd_cents", "fd_billed_rate",
    "fd_overcharge_rate", "fd_ci", "mo_cents", "mo_rate", "mo_ci", "line_precision",
    "line_recall", "bad_clears", "abstention", "unsupported_exposure_cents",
    "raw_quote_accuracy", "typed_value_accuracy", "pointer_resolution_accuracy",
    "external_cost_cents", "original_capture_cost_cents", "wall_seconds", "review_minutes",
)


def _delta_rows(subset, comparisons=None, gates=None):
    rows = []
    for baseline in ("A0", "A1"):
        comparison = (comparisons or {}).get(baseline, {})
        for metric, gate_name, threshold, rule in DELTA_SPECS:
            estimate = comparison.get("deltas", {}).get(metric, {})
            gate = (gates or {}).get(f"{gate_name}_vs_{baseline}", {})
            rows.append({"slice": subset, "candidate": "A2", "baseline": baseline, "metric": metric,
                         "status": gate.get("status", comparison.get("status", "not_run")),
                         "observed": estimate.get("observed"),
                         "low": estimate.get("low"), "high": estimate.get("high"),
                         "interval_status": estimate.get("status", "not_measured"),
                         "threshold": threshold, "rule": rule,
                         "reason": gate.get("reason", comparison.get("status", "not_run")),
                         "limitation": estimate.get("limitation")})
    return rows


def not_run_report():
    rows = []
    model_status = model_arm_status()
    for subset in SLICES:
        for arm in ARMS:
            row = dict.fromkeys(RESULT_COLUMNS)
            row.update(slice=subset, arm=arm, status="not_run", origin="not_measured",
                       review_minutes="minutes not measured")
            if arm in model_status:
                row.update(model_status[arm])
            if arm == "G-agreement" and subset == "H-out":
                row.update(status="not_applicable", reason="H-out has no generator truth")
            rows.append(row)
    return {"status": "not_run", "claim": "not_established", "rows": rows,
            "gate_table": [{"slice": subset, "gate": gate, "status": "pending", "reason": "not_run"}
                           for subset in ("H-in", "H-out") for gate in GATE_NAMES],
            "delta_table": [row for subset in SLICES for row in _delta_rows(subset)],
            "trap_results": "not_run", "lambda_sensitivity": "not_run", "prevalence_sensitivity": "not_run",
            "goe_patterns": "not_run", "agreement_audits": "not_run", "mutants": "not_run",
            "sizing": "not_run", "failure_registry": {name: "not_run" for name in FAILURE_REGISTRY}}


def _retained(value):
    """Archive nonfinite invalid outputs explicitly, without changing their score.

    `run_development` retains the original attempted output. A NaN/Infinity in an
    invalid attempt is represented here by a tagged object, never a JSON number.
    Other non-JSON objects still fail strict serialization rather than vanish.
    """
    if type(value) is float and not isfinite(value):
        return {"invalid_nonfinite_float": str(value)}
    if isinstance(value, dict):
        return {key: _retained(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_retained(item) for item in value]
    return value


def development_report(run, *, sizing=None):
    """Adapt a retained run_development result to measured diagnostic report rows.

    This never runs a scorer/bootstrap, manufactures ancillary measurements, or
    opens/adopts held-out data. H-in/H-out and independent prerequisites remain
    pending even if a dev interval passes its numerical diagnostic threshold.
    """
    if run.get("status") != "development_diagnostic":
        raise ValueError("a retained run_development diagnostic result is required")
    report = not_run_report()
    report.update(status="development_diagnostic", claim="not_established",
                  confirmatory_scoring="pending_actual_independent_prerequisites",
                  retained_run=_retained(run),
                  invalid_attempt_encoding="nonfinite floats use invalid_nonfinite_float tagged objects")
    scores = run["scores"]
    intervals = run.get("raw_intervals", {})
    for row in report["rows"]:
        if row["slice"] != "dev" or row["arm"] not in scores:
            continue
        arm = row["arm"]
        score = scores[arm]
        row.update(status="measured_diagnostic" if score["status"] == "valid" else "invalid_arm",
                   origin="non_model_development", external_cost_cents=0,
                   review_minutes="minutes not measured")
        if score["status"] != "valid":
            row.update(errors=score["errors"], attempted_output=_retained(score["attempted_output"]))
            continue
        metrics = score["metrics"]
        estimates = intervals.get(arm, {}).get("estimates", {})
        row.update(components=len(score["components"]), occurrences=len(score["lines"]),
                   adjudicable_billed_cents=metrics["billed_cents"],
                   abstention=metrics["abstained"], c2_ci=estimates.get("c2_cents"),
                   fd_ci={"cents": estimates.get("fd_cents"),
                          "billed_rate": estimates.get("fd_billed_rate"),
                          "overcharge_rate": estimates.get("fd_overcharge_rate")},
                   mo_ci={"cents": estimates.get("mo_cents"), "rate": estimates.get("mo_rate")})
        for name in ("oracle_overcharge_cents", "c2_cents", "correct_proposed_cents", "fd_cents",
                     "fd_billed_rate", "fd_overcharge_rate", "mo_cents", "mo_rate", "line_precision",
                     "line_recall", "bad_clears", "unsupported_exposure_cents"):
            row[name] = metrics[name]
    gates = (run.get("diagnostic_gates") or {}).get("gates", {})
    for name in GATE_NAMES:
        detail = gates.get(name, {"status": "pending", "reason": "development arm or interval not measured"})
        report["gate_table"].append({"slice": "dev", "gate": name, **detail})
    report["delta_table"] = (_delta_rows("dev", run.get("comparisons"), gates) +
                             [row for row in report["delta_table"] if row["slice"] != "dev"])
    for name in ("trap_results", "prevalence_sensitivity", "goe_patterns", "agreement_audits", "mutants"):
        report[name] = "not_measured"
    report["lambda_sensitivity"] = {arm: score["metrics"]["sensitivity_cents"]
                                     if score["status"] == "valid" else {"status": "invalid_arm"}
                                     for arm, score in scores.items()}
    report["sizing"] = "not_measured" if sizing is None else sizing
    report["failure_registry"] = {name: "not_measured" for name in FAILURE_REGISTRY}
    invalid = {arm: {"errors": score["errors"], "attempted_output": _retained(score["attempted_output"])}
               for arm, score in scores.items() if score["status"] != "valid"}
    if invalid:
        report["failure_registry"]["INVALID_ARM/F16"] = {"status": "observed", "arms": invalid}
    return report


def _cell(value):
    if value is None:
        return "not_measured"
    return str(value).replace("|", "\\|").replace("\n", " ").replace("\r", " ")


def markdown(report):
    """Renders supplied retained results; this function manufactures no scores."""
    columns = ("slice", "arm", "origin", "status") + RESULT_COLUMNS
    lines = ["# Freight reconciliation evaluation", "", f"Claim: {_cell(report['claim'])}", "",
             "Dev is diagnostic, not a confirmatory claim. Identified dollars are not cash recovered.", "",
             "| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    for row in report["rows"]:
        lines.append("| " + " | ".join(_cell(row.get(key)) for key in columns) + " |")
    delta_columns = ("slice", "candidate", "baseline", "metric", "status", "observed", "low", "high",
                     "interval_status", "threshold", "rule", "reason", "limitation")
    lines.extend(["", "## Paired deltas", "", "| " + " | ".join(delta_columns) + " |",
                  "| " + " | ".join("---" for _ in delta_columns) + " |"])
    for delta in report.get("delta_table", []):
        lines.append("| " + " | ".join(_cell(delta.get(key)) for key in delta_columns) + " |")
    gate_columns = ("slice", "gate", "status", "upper", "threshold", "interval_status", "reason")
    lines.extend(["", "## Gates", "", "| " + " | ".join(gate_columns) + " |",
                  "| " + " | ".join("---" for _ in gate_columns) + " |"])
    for gate in report["gate_table"]:
        lines.append("| " + " | ".join(_cell(gate.get(key)) for key in gate_columns) + " |")
    for name in ("trap_results", "lambda_sensitivity", "prevalence_sensitivity", "goe_patterns",
                 "agreement_audits", "mutants", "sizing", "failure_registry"):
        lines.extend(["", f"## {name}", "", "```json",
                      json.dumps(report.get(name), sort_keys=True, indent=2, allow_nan=False), "```"])
    return "\n".join(lines) + "\n"


def jsonl(report):
    """Lossless report sections plus arm rows, distinguished by record_kind."""
    records = [{"record_kind": "arm_result", "row": row} for row in report["rows"]]
    records.extend({"record_kind": "report_section", "section": name, "value": report[name]}
                   for name in sorted(report) if name != "rows")
    return "".join(json.dumps(record, sort_keys=True, allow_nan=False) + "\n" for record in records)


def report_json(report):
    """Complete strict JSON companion, including failures, deltas, sizing and gates."""
    return json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + "\n"
