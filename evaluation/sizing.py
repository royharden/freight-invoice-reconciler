"""Pre-hidden analytic sizing and source-only precision simulation.

Never call on hidden outcomes. Defaults are a declared builder protocol proposal,
not a dev freeze receipt. J must freeze seeds/mixture before hidden generation.
The simulation resamples paired whole components and uses ratio-of-sums widths.
"""

from math import ceil, isfinite
from random import Random
from statistics import mean, median, stdev

from .bootstrap import deltas, interval, paired_components

SIZING_SEED = 130828
SIZES = (300, 400, 600, 800)
SIMULATIONS = 1000


def _finite_number(value):
    return type(value) is int or (type(value) is float and isfinite(value))


def n_req(values):
    """JSON-safe requirement: a null value always carries its nonfinite reason.

    Infinity is a design result for a zero mean, never a JSON numeric literal.
    Insufficient/invalid inputs are separately not identifiable, not finite zero.
    """
    if len(values) < 2:
        return {"status": "not_identifiable", "value": None, "reason": "fewer_than_two_components"}
    if any(not _finite_number(value) for value in values):
        return {"status": "not_identifiable", "value": None, "reason": "nonfinite_or_invalid_input"}
    try:
        average = mean(values)
        if average == 0:
            return {"status": "infinite", "value": None, "reason": "zero_mean"}
        required = ceil((1.96 * stdev(values) / (.25 * abs(average))) ** 2)
    except (OverflowError, ValueError, ZeroDivisionError):
        return {"status": "infinite", "value": None, "reason": "numeric_overflow"}
    return {"status": "finite", "value": required, "reason": None}


def _maximum_requirement(minimum, *requirements):
    nonfinite = [item for item in requirements if item["status"] != "finite"]
    if nonfinite:
        status = "infinite" if any(item["status"] == "infinite" for item in nonfinite) else "not_identifiable"
        return {"status": status, "value": None, "reason": "nonfinite_source_requirement"}
    return {"status": "finite", "value": max(minimum, *(item["value"] for item in requirements)),
            "reason": None}


def analytic_policy(pilot_a1_c2, private_hdev_a1_c2, public_deltas, h_public_deltas):
    """External private-H-dev aggregates are inputs; this tool authors no H data."""
    requirements = {"g_in": n_req(pilot_a1_c2), "g_out": n_req(private_hdev_a1_c2)}
    base = {"g_in": requirements["g_in"]["value"], "g_out": requirements["g_out"]["value"],
            "requirements": requirements, "hidden_generation_authorized": False}
    if any(item["status"] != "finite" for item in requirements.values()):
        return dict(base, status="stop_admission_nonfinite")
    if not public_deltas or not h_public_deltas:
        return dict(base, status="stop_negative_dev", reason="missing_development_deltas")
    if any(not _finite_number(value)
           for values in (public_deltas, h_public_deltas) for value in values):
        return dict(base, status="stop_invalid_dev_inputs")
    requirements.update(public_delta=n_req(public_deltas), h_public_delta=n_req(h_public_deltas))
    if mean(public_deltas) >= 0 or mean(h_public_deltas) >= 0:
        return dict(base, status="stop_negative_dev", reason="nonnegative_development_mean")
    requirements["q"] = _maximum_requirement(0, requirements["public_delta"], requirements["h_public_delta"])
    required_in = _maximum_requirement(160, requirements["g_in"], requirements["q"])
    required_out = _maximum_requirement(300, requirements["g_out"], requirements["q"])
    return {**base, "status": "design_only", "q": requirements["q"]["value"],
            "h_in_required_uncapped": required_in["value"], "h_in_requirement": required_in,
            "h_in_selected": 400 if required_in["value"] is None else min(400, required_in["value"]),
            "h_out_analytic_target": required_out["value"], "h_out_analytic_requirement": required_out,
            "precision_limited_before_generation": required_in["value"] is None or required_in["value"] > 400,
            "hidden_generation_authorized": False}


def _analytic_requirement(target):
    """Accept a finite number or an explicit n_req-style nonfinite record."""
    if isinstance(target, dict):
        if (target.get("status") in ("infinite", "not_identifiable") and target.get("value") is None
                and isinstance(target.get("reason"), str) and target["reason"]):
            return {"status": target["status"], "value": None, "reason": target["reason"]}
        if target.get("status") != "finite":
            raise ValueError("explicit finite or nonfinite analytic requirement required")
        target = target.get("value")
    if not _finite_number(target) or target < 0:
        raise ValueError("finite nonnegative analytic target or explicit nonfinite requirement required")
    return {"status": "finite", "value": target, "reason": None}


def _allocation(groups, size):
    total = sum(len(group) for group in groups.values())
    counts = {stratum: size * len(group) // total for stratum, group in groups.items()}
    # Largest remainder allocation, deterministic tie break, fixes mixture each resample.
    remaining = size - sum(counts.values())
    order = sorted(groups, key=lambda name: (-(size * len(groups[name]) % total), name))
    for name in order[:remaining]:
        counts[name] += 1
    return counts


def simulate_precision(candidate, baselines, analytic_target, *, seed=SIZING_SEED,
                       simulations=SIMULATIONS, inner_draws=10_000):
    """Nested bootstrap design simulation on H's 80 PUBLIC dev components only.

    1000 outer simulations per N; each predicted 95% interval uses 10,000
    paired inner draws. Expensive by design; this construction run never executes
    it. All per-simulation widths and degenerate states are retained.
    """
    if set(baselines) != {"A0", "A1"}:
        raise ValueError("both A0 and A1 are required")
    if len(candidate.get("components") or []) != 80:
        raise ValueError("exactly 80 H-authored public dev components required")
    if type(simulations) is not int or simulations < 2 or type(inner_draws) is not int or inner_draws < 2:
        raise ValueError("simulation and inner draw counts must be >=2")
    target = _analytic_requirement(analytic_target)
    groups_by_arm = {arm: paired_components(candidate, baseline) for arm, baseline in baselines.items()}
    a2_zero_fd = candidate["metrics"]["fd_cents"] == 0
    rng = Random(seed)
    table = []
    for size in SIZES:
        arm_results = {}
        for arm, groups in groups_by_arm.items():
            counts = _allocation(groups, size)
            widths = {"mo_rate": [], "fd_billed_rate": []}
            failures = {key: [] for key in widths}
            for simulation in range(simulations):
                sample_groups = {name: [rng.choice(group) for _ in range(counts[name])]
                                 for name, group in groups.items()}
                observed = deltas([pair for group in sample_groups.values() for pair in group])
                draws = {key: [] for key in widths}
                for _ in range(inner_draws):
                    sample = [rng.choice(group) for group in sample_groups.values() for _ in range(len(group))]
                    result = deltas(sample)
                    for key in draws:
                        draws[key].append(result[key])
                for key, values in draws.items():
                    estimate = interval(values, observed[key])
                    if estimate["status"] == "estimated":
                        widths[key].append((estimate["high"]-estimate["low"])/2)
                    else:
                        widths[key].append(None)
                        failures[key].append({"simulation": simulation, "status": estimate["status"]})
            medians = {key: median(values) if all(value is not None for value in values) else None
                       for key, values in widths.items()}
            arm_results[arm] = {"median_half_width": medians, "all_half_widths": widths,
                                "unidentified": failures}
        mo_ok = all(row["median_half_width"]["mo_rate"] is not None and
                    row["median_half_width"]["mo_rate"] <= .02 for row in arm_results.values())
        fd_ok = a2_zero_fd or all(row["median_half_width"]["fd_billed_rate"] is not None and
                                 row["median_half_width"]["fd_billed_rate"] <= .0005
                                 for row in arm_results.values())
        table.append({"n": size, "arms": arm_results,
                      "qualifies": target["status"] == "finite" and size >= target["value"] and mo_ok and fd_ok})
    selected = next((row["n"] for row in table if row["qualifies"]), 800)
    return {"status": "design_only", "seed": seed, "simulations": simulations, "inner_draws": inner_draws,
            "analytic_target": target["value"], "analytic_requirement": target, "h_out_selected": selected,
            "precision_limited": not any(row["qualifies"] for row in table),
            "earlier_400_component_warning": target["value"] is None or target["value"] > 400,
            "fd_sizing_evidence": "none_observed_zero_branch" if a2_zero_fd else "widths_required",
            "table": table, "hidden_generation_authorized": False}
