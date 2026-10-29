"""No similarity score can authorize a shipment link."""

import re


def normalize_reference(value: object) -> str:
    """ASCII case fold; remove only ASCII spaces, hyphens and underscores.

    Other punctuation and non-ASCII identifiers refuse rather than silently
    collapsing look-alikes. The same rule is applied inside each carrier scope.
    """
    if not isinstance(value, str) or not value or len(value) > 200:
        raise ValueError("invalid_reference")
    if not re.fullmatch(r"[A-Za-z0-9 _-]+", value):
        raise ValueError("invalid_reference")
    result = re.sub(r"[ _-]", "", value).upper()
    if not result:
        raise ValueError("invalid_reference")
    return result


def link_shipment(carrier: object, reference: object, shipments: list[dict]) -> dict:
    """Return a unique exact match or an explicit, non-monetary refusal."""
    try:
        namespace = normalize_reference(carrier)
        wanted = normalize_reference(reference)
    except ValueError:
        return {"status": "cannot_determine", "reason_code": "invalid_reference", "shipment": None}
    matches = []
    for shipment in shipments:
        try:
            if normalize_reference(shipment.get("carrier")) != namespace:
                continue
            candidate = shipment.get("reference", shipment.get("shipment_id"))
            if normalize_reference(candidate) == wanted:
                matches.append(shipment)
        except ValueError:
            continue
    if len(matches) != 1:
        return {"status": "cannot_determine", "reason_code": "link_ambiguous" if matches else "link_missing", "shipment": None}
    # The allocator groups by stable shipment identity. A reference may be
    # unique while its shipment ID aliases another record in this namespace.
    shipment_id = matches[0].get("shipment_id")
    if not isinstance(shipment_id, str) or not shipment_id.strip():
        return {"status": "cannot_determine", "reason_code": "shipment_id_missing", "shipment": None}
    aliases = []
    for shipment in shipments:
        try:
            if normalize_reference(shipment.get("carrier")) == namespace and shipment.get("shipment_id") == shipment_id:
                aliases.append(shipment)
        except ValueError:
            continue
    if len(aliases) != 1:
        return {"status": "cannot_determine", "reason_code": "shipment_identity_ambiguous", "shipment": None}
    return {"status": "linked", "reason_code": "exact_namespaced_reference", "shipment": matches[0]}


def resolve_target(carrier: str, target: object, shipments: list[dict], verify) -> dict | None:
    """Validate a trusted callback's target against the original source batch.

    A callback cannot introduce a new shipment, cross a namespace, or collapse
    duplicate stable identities. `verify` is local source-verification code.
    """
    if not isinstance(target, str) or not target.strip() or len(target) > 200:
        return None
    namespace = normalize_reference(carrier)
    matches = []
    for shipment in shipments:
        try:
            if (normalize_reference(shipment.get("carrier")) == namespace
                    and shipment.get("shipment_id") == target):
                matches.append(shipment)
        except ValueError:
            continue
    if len(matches) != 1 or not verify(matches[0]):
        return None
    return matches[0]
