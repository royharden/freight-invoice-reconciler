"""One recorded extraction/link snapshot for all non-model diagnostic arms.

This is builder tooling, not a source authenticator, oracle or campaign runner.
The caller captures facts only after original-source verification and records the
actual shared link outcomes. No function here can authorize a manual link.
"""

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json

from freightrec.link import normalize_reference

from .arms import a0, a1
from .components import connected_components
from .metrics import cents

ADAPTER_VERSION = "freightrec-observation-v1"
_TRUTH_KEYS = {"reference_cents", "expected_cents", "oracle_cents", "gold", "gold_cents", "truth",
               "planted_error", "oracle_overcharge_cents"}


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


def _digest(value):
    return sha256(_json(value).encode("utf-8")).hexdigest()


def _facts_only(value):
    if isinstance(value, dict):
        if set(value) & _TRUTH_KEYS:
            raise ValueError("reference/truth fields forbidden in product-source recording")
        for child in value.values():
            _facts_only(child)
    elif isinstance(value, list):
        for child in value:
            _facts_only(child)


def _text(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("nonempty recorded identity required")
    return value


@dataclass(frozen=True)
class FrozenObservations:
    """Immutable JSON edition; each consumer receives its own parsed copy."""

    canonical_json: str
    sha256: str

    def load(self):
        if sha256(self.canonical_json.encode("utf-8")).hexdigest() != self.sha256:
            raise ValueError("frozen observation edition changed")
        value = json.loads(self.canonical_json)
        if value.get("adapter_version") != ADAPTER_VERSION:
            raise ValueError("unsupported observation adapter edition")
        return value


def _candidate_outputs(findings, rows, tolerance_cents):
    """Retain malformed/missing/duplicate candidate outputs for full-arm failure."""
    if not isinstance(findings, list):
        return deepcopy(findings)
    result = {}
    by_id = {row["occurrence_id"]: row for row in rows}
    for finding in findings:
        if not isinstance(finding, dict) or not isinstance(finding.get("occurrence_id"), str):
            return deepcopy(findings)  # scorer rejects a non-mapping attempt
        oid = finding["occurrence_id"]
        if oid in result:
            return deepcopy(findings)
        amount, verdict = finding.get("disputed_cents"), finding.get("verdict")
        row = by_id.get(oid)
        trace = finding.get("trace")
        links = [step for step in trace if isinstance(step, dict) and step.get("step") == "link"] if isinstance(trace, list) else []
        allocations = [step for step in trace if isinstance(step, dict) and step.get("step") == "allocation"] if isinstance(trace, list) else []
        identity = {key: row[key] for key in ("carrier", "invoice_id", "line_id")} if row else None
        if (row is not None and (type(finding.get("billed_cents")) is not int or
                                finding["billed_cents"] != row["billed_cents"] or
                                finding.get("occurrence") != identity or len(links) != 1 or
                                links[0].get("shipment_id") != row["shipment_id"])):
            result[oid] = {"disputed_cents": amount, "status": "recorded_fact_or_link_mismatch"}
        elif (len(allocations) != 1 or
              type(allocations[0].get("deadband_cents")) is not int or
              allocations[0]["deadband_cents"] != tolerance_cents):
            result[oid] = {"disputed_cents": amount, "status": "recorded_tolerance_mismatch"}
        elif verdict == "cannot_determine" and amount is None:
            result[oid] = {"disputed_cents": 0, "status": "abstain"}
        elif ((verdict == "overcharge" and type(amount) is int and amount > 0) or
              (verdict == "unsupported" and type(amount) is int and amount >= 0) or
              (verdict in ("undercharge", "justified") and type(amount) is int and amount == 0)):
            result[oid] = {"disputed_cents": amount,
                           "status": "proposed" if type(amount) is int and amount > 0 else "clear"}
        else:
            result[oid] = {"disputed_cents": amount, "status": "invalid_product_finding"}
    return result


def freeze_recording(documents, findings, links, strata, *, engine_version,
                     policy_version, source_resolver, tolerance_cents=0,
                     near_duplicate_ids=None):
    """Freeze verified source facts plus actual A2 outputs and shared link capture.

    documents is the same contracts/shipments/invoices/fuel_index mapping passed
    to A2. links maps EVERY canonical occurrence_id to {status, shipment_id};
    status is exact|resolved|unresolved. Resolved denotes an actually applied
    persisted human ruling, never a fuzzy match or a supplied authorization flag.
    strata maps EVERY occurrence_id to a preregistered mixture label. References
    are intentionally absent. Capture the actual engine/policy revision strings.
    Invalid recordings refuse wholly, never drop rows.
    """
    names = {"contracts", "shipments", "invoices", "fuel_index"}
    if type(tolerance_cents) is not int or tolerance_cents not in (0, 50, 100):
        raise ValueError("captured tolerance must be 0, 50 or 100 cents")
    if not isinstance(documents, dict) or set(documents) != names or any(
            not isinstance(documents[name], list) or
            any(not isinstance(item, dict) for item in documents[name]) for name in names):
        raise ValueError("complete original-source document collections required")
    _facts_only(documents)
    # Use the same original-source verifier as the product boundary. This is
    # observation parity, not an independent oracle or truth determination.
    from freightrec.sources import verify_document
    for name in names:
        for document in documents[name]:
            verify_document(document, source_resolver)
    if not isinstance(links, dict) or not isinstance(strata, dict):
        raise ValueError("explicit complete link and stratum observations required")
    copies = {} if near_duplicate_ids is None else near_duplicate_ids
    if not isinstance(copies, dict):
        raise ValueError("near-duplicate identities must be a mapping")
    shipments = {}
    for shipment in documents["shipments"]:
        key = (normalize_reference(shipment.get("carrier")), _text(shipment.get("shipment_id")))
        if key in shipments:
            raise ValueError("ambiguous recorded shipment identity")
        shipments[key] = shipment
    rows, identities = [], set()
    for invoice in documents["invoices"]:
        carrier = normalize_reference(invoice.get("carrier"))
        invoice_id = _text(invoice.get("invoice_id"))
        lines = invoice.get("lines")
        if not isinstance(lines, list) or not lines:
            raise ValueError("recording requires complete explicit invoice lines")
        for line in lines:
            if not isinstance(line, dict):
                raise ValueError("malformed source line invalidates recording")
            identity = {"carrier": carrier, "invoice_id": invoice_id,
                        "line_id": _text(line.get("line_id"))}
            key = _json(identity)
            if key in identities:
                raise ValueError("ambiguous occurrence universe; no subset conversion")
            identities.add(key)
            oid = _digest({"identity": identity, "ordinal": 0})
            link = links.get(oid)
            if (not isinstance(link, dict) or set(link) != {"status", "shipment_id"} or
                    link["status"] not in ("exact", "resolved", "unresolved")):
                raise ValueError("explicit link observation required for every occurrence")
            target = link["shipment_id"]
            if link["status"] == "unresolved":
                if target is not None:
                    raise ValueError("unresolved link cannot carry a shipment target")
                shipment = None
            else:
                shipment = shipments.get((carrier, _text(target)))
                if shipment is None:
                    raise ValueError("recorded link target absent or cross-carrier")
                if link["status"] == "exact":
                    reference = normalize_reference(line.get("shipment_ref", line.get("shipment_id")))
                    matches = [value for (namespace, _), value in shipments.items()
                               if namespace == carrier and normalize_reference(
                                   value.get("reference", value.get("shipment_id"))) == reference]
                    if len(matches) != 1 or matches[0] is not shipment:
                        raise ValueError("recorded exact link disagrees with source namespace")
            row = dict(identity, occurrence_id=oid, billed_cents=cents(line.get("billed_cents")),
                       currency=line.get("currency") if line.get("currency") == invoice.get("currency") else None,
                       total_cents=invoice.get("total_cents"), invoice_issue_ts=invoice.get("invoice_issue_ts"),
                       code=line.get("code"), stop_seq=line.get("stop_seq"),
                       shipment_id=target, link_status=link["status"], stratum=_text(strata.get(oid)))
            for name in ("origin_zone", "destination_zone", "weight_lb"):
                row[name] = shipment.get(name) if shipment is not None else None
            # Capture only explicit billed units; no derivation from elapsed
            # stop times, billed dollars, reference labels or expected amounts.
            for name in ("billed_detention_units", "billed_detention_unit", "billed_increment_minutes"):
                row[name] = line.get(name)
            if shipment is not None:
                row["duplicate_group_id"] = _digest([carrier, target, row["code"], row["stop_seq"]])
            if invoice.get("source_sha256") is not None:
                row["document_sha256"] = _text(invoice["source_sha256"])
            if oid in copies:
                row["near_duplicate_case_id"] = _text(copies[oid])
            rows.append(row)
    universe = {row["occurrence_id"] for row in rows}
    if not rows or set(links) != universe or set(strata) != universe or set(copies) - universe:
        raise ValueError("link/stratum/copy recording must preserve the complete occurrence universe")
    components = connected_components(rows)
    mixture = {}
    for row in rows:
        row["component_id"] = components[row["occurrence_id"]]
        seen = mixture.setdefault(row["component_id"], row["stratum"])
        if seen != row["stratum"]:
            raise ValueError("one connected component cannot cross mixture strata")
    contracts = deepcopy(documents["contracts"])
    for contract in contracts:
        contract["carrier"] = normalize_reference(contract.get("carrier"))
    payload = {"adapter_version": ADAPTER_VERSION, "source_documents": deepcopy(documents),
               "engine_version": _text(engine_version), "policy_version": _text(policy_version),
               "tolerance_cents": tolerance_cents,
               "rows": sorted(rows, key=lambda row: row["occurrence_id"]),
               "contracts": contracts, "fuel_index": deepcopy(documents["fuel_index"]),
               "recorded_findings": deepcopy(findings),
               "a2_attempt": _candidate_outputs(findings, rows, tolerance_cents)}
    encoded = _json(payload)
    return FrozenObservations(encoded, sha256(encoded.encode("utf-8")).hexdigest())


def product_input(snapshot):
    """Facts only for replay; persisted link authority still belongs to DecisionLog."""
    documents = snapshot.load()["source_documents"]
    _facts_only(documents)
    return documents


def diagnostic_outputs(snapshot):
    """Use one common edition; A2 is retained actual output, never rerun or fixed."""
    value = snapshot.load()
    rows = value["rows"]
    return {"snapshot_sha256": snapshot.sha256,
            "tolerance_cents": value["tolerance_cents"],
            "arm_outputs": {"A0": a0(rows),
                            "A1": a1(rows, value["contracts"], value["fuel_index"], value["tolerance_cents"]),
                            "A2": value["a2_attempt"]}}


def scoring_observations(snapshot, references):
    """Join external reference cents only AFTER all product outputs are retained."""
    rows = snapshot.load()["rows"]
    if not isinstance(references, dict) or set(references) != {row["occurrence_id"] for row in rows}:
        raise ValueError("external references must cover the exact frozen occurrence universe")
    for row in rows:
        value = references[row["occurrence_id"]]
        row["reference_cents"] = None if value is None else cents(value, "reference_cents")
    return rows
