"""Builder diagnostic orchestration. No hidden-set opening or benchmark dispatcher."""

from .bootstrap import paired_bootstrap, raw_bootstrap
from .gates import evaluate_slice
from .metrics import score_arm


def run_development(observations, arm_outputs, *, tolerance_cents=0, seed=130827, draws=10_000):
    """Score external builder/public-dev records. Caller must retain actual inputs.

    Never generate data or labels here. The result is diagnostic even when source
    rows contain reference amounts. A3/A4 are not accepted as measured model arms.
    """
    if not isinstance(arm_outputs, dict) or not set(arm_outputs).issubset({"A0", "A1", "A2", "A2s"}):
        raise ValueError("only non-model development arm outputs accepted")
    scores = {arm: score_arm(observations, outputs, tolerance_cents) for arm, outputs in arm_outputs.items()}
    raw_intervals = {arm: raw_bootstrap(score, seed=seed, draws=draws)
                     if score["status"] == "valid" else
                     {"status": "blocked_invalid_arm", "errors": score["errors"]}
                     for arm, score in scores.items()}
    comparisons = {}
    for baseline in ("A0", "A1"):
        invalid = {arm: scores[arm]["errors"] for arm in ("A2", baseline)
                   if arm in scores and scores[arm]["status"] != "valid"}
        missing = [arm for arm in ("A2", baseline) if arm not in scores]
        if invalid or missing:
            comparisons[baseline] = {"status": "blocked_invalid_arm" if invalid else "not_run",
                                     "invalid_arms": invalid, "missing_arms": missing}
        else:
            comparisons[baseline] = paired_bootstrap(scores["A2"], scores[baseline], seed=seed, draws=draws)
    gates = evaluate_slice(scores["A2"], comparisons) if "A2" in scores else None
    return {"status": "development_diagnostic", "claim": "not_established", "scores": scores,
            "raw_intervals": raw_intervals, "comparisons": comparisons, "diagnostic_gates": gates,
            "bootstrap_protocol": {"seed": seed, "draws": draws, "confidence": .95,
                                   "unit": "connected_component", "mixture": "fixed_strata"},
            "confirmatory_scoring": "pending_actual_independent_prerequisites",
            "review_minutes": "minutes not measured"}


def run_confirmatory(*args, **kwargs):
    raise PermissionError("PENDING: actual H/O/J, human audit, admission, freeze, custody and campaign authority required")
