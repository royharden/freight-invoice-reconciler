"""Paired whole-component, fixed-stratum bootstrap. No linewise resampling."""

from collections import defaultdict
from random import Random

from .metrics import summarize

DEFAULT_SEED = 130827
DEFAULT_DRAWS = 10_000
RAW_METRICS = ("c2_cents", "fd_cents", "fd_billed_rate", "fd_overcharge_rate",
               "mo_cents", "mo_rate")


def interval(values, observed):
    if not values or any(value is None for value in values):
        return {"status": "not_identifiable", "observed": observed, "low": None, "high": None}
    ordered = sorted(values)
    if ordered[0] == ordered[-1]:
        return {"status": "degenerate", "observed": observed, "low": None, "high": None,
                "limitation": "Identical resamples supply no inferential interval."}
    def quantile(p):
        at = (len(ordered)-1)*p
        lo = int(at)
        hi = min(lo+1, len(ordered)-1)
        return ordered[lo] + (ordered[hi]-ordered[lo])*(at-lo)
    return {"status": "estimated", "observed": observed, "low": quantile(.025), "high": quantile(.975)}


def paired_components(candidate, baseline):
    if candidate.get("status") != "valid" or baseline.get("status") != "valid":
        raise ValueError("invalid arms cannot enter confirmatory bootstrap")
    if (candidate["observation_hash"] != baseline["observation_hash"] or
            candidate["tolerance_cents"] != baseline["tolerance_cents"]):
        raise ValueError("arms must share frozen observations and tolerance")
    left = {row["component_id"]: row for row in candidate["components"]}
    right = {row["component_id"]: row for row in baseline["components"]}
    if set(left) != set(right) or not left:
        raise ValueError("paired component identities must match")
    groups = defaultdict(list)
    for cid in sorted(left):
        if left[cid]["stratum"] != right[cid]["stratum"]:
            raise ValueError("paired component strata mismatch")
        groups[left[cid]["stratum"]].append((left[cid], right[cid]))
    return dict(groups)


def deltas(pairs):
    left, right = summarize([p[0] for p in pairs]), summarize([p[1] for p in pairs])
    return {"c2_per_component_cents": (left["c2_cents"]-right["c2_cents"])/len(pairs),
            "mo_rate": None if left["mo_rate"] is None or right["mo_rate"] is None
            else left["mo_rate"]-right["mo_rate"],
            "fd_billed_rate": None if left["fd_billed_rate"] is None or right["fd_billed_rate"] is None
            else left["fd_billed_rate"]-right["fd_billed_rate"]}


def paired_bootstrap(candidate, baseline, *, seed=DEFAULT_SEED, draws=DEFAULT_DRAWS):
    if type(draws) is not int or draws < 2:
        raise ValueError("at least two bootstrap draws required")
    groups = paired_components(candidate, baseline)
    rng = Random(seed)
    observed = deltas([pair for group in groups.values() for pair in group])
    distribution = {key: [] for key in observed}
    for _ in range(draws):
        sample = [rng.choice(group) for group in groups.values() for _ in range(len(group))]
        for key, value in deltas(sample).items():
            distribution[key].append(value)
    return {"seed": seed, "draws": draws, "confidence": .95, "unit": "connected_component",
            "stratum_counts": {key: len(value) for key, value in groups.items()},
            "deltas": {key: interval(values, observed[key]) for key, values in distribution.items()}}


def raw_bootstrap(arm, *, seed=DEFAULT_SEED, draws=DEFAULT_DRAWS):
    """Raw dollar/rate intervals, using the same fixed whole-component mixture.

    Totals are corpus-scale sums; rates are ratios of the resampled sums. Unknown
    references remain outside the adjudicable denominators exactly as scored.
    Invalid arms have no valid-subset estimate and must not enter this function.
    """
    if type(draws) is not int or draws < 2:
        raise ValueError("at least two bootstrap draws required")
    # Pairing an arm with itself reuses identity/stratum checks, not delta values.
    groups = {name: [pair[0] for pair in pairs]
              for name, pairs in paired_components(arm, arm).items()}
    observed = summarize([row for group in groups.values() for row in group])
    distribution = {key: [] for key in RAW_METRICS}
    rng = Random(seed)
    for _ in range(draws):
        sample = [rng.choice(group) for group in groups.values() for _ in range(len(group))]
        totals = summarize(sample)
        for key in distribution:
            distribution[key].append(totals[key])
    return {"seed": seed, "draws": draws, "confidence": .95, "unit": "connected_component",
            "stratum_counts": {key: len(value) for key, value in groups.items()},
            "estimates": {key: interval(values, observed[key]) for key, values in distribution.items()}}
