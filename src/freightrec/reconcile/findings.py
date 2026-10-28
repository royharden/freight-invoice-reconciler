"""Stable finding encoding and full-overage deadband semantics."""

import hashlib
import json

POLICY_VERSION = "freightrec-reconcile-v3-evidence-order"


def canonical(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def digest(value: object) -> str:
    return hashlib.sha256(canonical(value).encode("utf-8")).hexdigest()


def cents(value: object) -> int | None:
    return value if type(value) is int and value >= 0 else None


def classify(billed: int | None, expected: int | None, tolerance: int) -> tuple[str, int | None]:
    if billed is None or expected is None:
        return "cannot_determine", None
    delta = billed - expected
    if expected == 0:
        return "unsupported", delta if delta > tolerance else 0
    if delta > tolerance:
        return "overcharge", delta
    if -delta > tolerance:
        return "undercharge", 0
    return "justified", 0
