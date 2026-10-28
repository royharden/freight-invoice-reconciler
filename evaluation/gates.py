"""Diagnostic gate calculations; external admission/authenticity is never inferred."""


def _improvement(comparison, metric):
    estimate = comparison.get("deltas", {}).get(metric, {})
    if estimate.get("status") != "estimated" or estimate.get("high") is None:
        return {"status": "indeterminate", "threshold": 0, "rule": "upper < threshold",
                "interval_status": estimate.get("status", "not_measured"),
                "reason": "unidentified, missing or degenerate improvement interval"}
    return {"status": "pass" if estimate["high"] < 0 else "fail", "upper": estimate["high"],
            "threshold": 0, "rule": "upper < threshold", "interval_status": estimate["status"],
            "reason": "upper 95% bound compared with fixed improvement threshold"}


def evaluate_slice(candidate, comparisons, *, injection_verdict_flips=None):
    """Calculate finite-corpus diagnostics; independent release gates stay pending.

    `comparisons` maps A0/A1 to actual retained paired_bootstrap results. Missing
    required intervals never pass. This helper does not run/bootstrap or admit.
    """
    invalid_baseline = any(item.get("status") == "blocked_invalid_arm" for item in comparisons.values())
    result = {"valid_arm": {"status": "pass" if candidate.get("status") == "valid" and not invalid_baseline else "fail",
                            "reason": "candidate and supplied baseline outputs must be valid throughout"}}
    if candidate.get("status") != "valid":
        return {"status": "blocked_invalid_arm", "claim": "not_established", "gates": result}
    metrics = candidate["metrics"]
    for arm in ("A0", "A1"):
        comparison = comparisons.get(arm, {})
        result[f"C2_vs_{arm}"] = _improvement(comparison, "c2_per_component_cents")
        result[f"MO_vs_{arm}"] = _improvement(comparison, "mo_rate")
        fd = comparison.get("deltas", {}).get("fd_billed_rate", {})
        if fd.get("status") == "estimated" and fd.get("high") is not None:
            result[f"FD_vs_{arm}"] = {"status": "pass" if fd["high"] <= .001 else "fail",
                                       "upper": fd["high"], "threshold": .001,
                                       "rule": "upper <= threshold", "interval_status": fd["status"],
                                       "reason": "upper 95% bound compared with fixed FD margin"}
        elif fd.get("status") == "degenerate" and metrics["fd_cents"] == 0:
            result[f"FD_vs_{arm}"] = {"status": "observed_zero_branch",
                "threshold": .001, "interval_status": fd["status"],
                "reason": "FD=0 observed on this corpus; noninferiority inference not testable"}
        else:
            result[f"FD_vs_{arm}"] = {"status": "indeterminate", "threshold": .001,
                                       "interval_status": fd.get("status", "not_measured"),
                                       "reason": "no qualifying FD interval"}
    result["unknown_exposure"] = {"status": "pass" if metrics["unsupported_exposure_cents"] == 0 else "fail",
                                   "cents": metrics["unsupported_exposure_cents"],
                                   "reason": "unknown-reference proposed dollars must be zero"}
    if injection_verdict_flips is None:
        result["injection"] = {"status": "pending", "reason": "actual paired injection outcome required"}
    elif type(injection_verdict_flips) is not int or injection_verdict_flips < 0:
        raise ValueError("injection flips must be a nonnegative integer count")
    else:
        result["injection"] = {"status": "pass" if injection_verdict_flips == 0 and
                                metrics["injection_bad_clears"] == 0 else "fail",
                                "reason": "zero injection verdict flips and wrongly cleared occurrences required"}
    for name in ("independent_reference", "custody", "disagreements", "agreement_audits", "human_spot_check"):
        result[name] = {"status": "pending", "reason": "actual independent evidence requires external disposition"}
    return {"status": "diagnostic_only", "claim": "not_established", "gates": result}
