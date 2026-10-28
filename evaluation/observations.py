"""One recorded extraction/link snapshot for all non-model diagnostic arms.

This is builder tooling, not a source authenticator, oracle or campaign runner.
The caller captures facts only after original-source verification and records the
actual shared link outcomes. No function here can authorize a manual link.
"""

from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
from importlib.metadata import PackageNotFoundError, version
import json
from pathlib import Path
import platform
import sys

from freightrec.link import normalize_reference

from .arms import a0, a1
from .components import connected_components
from .metrics import cents

ADAPTER_VERSION = "freightrec-observation-v1"
ORIGINAL_BUNDLE_VERSION = "freightrec-observation-v2-originals"
_V1_KEYS = {"adapter_version", "source_documents", "engine_version", "policy_version",
            "tolerance_cents", "rows", "contracts", "fuel_index", "recorded_findings", "a2_attempt"}
_V2_KEYS = _V1_KEYS | {"original_bundle", "links", "strata", "near_duplicate_ids", "runtime_edition"}
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


def _require_json_observation_sources(documents):
    """Keep the original v1 recording boundary JSON-only.

    Declining the complete recording is safer than giving a baseline parsed PDF
    facts while presenting those facts as replayable original JSON. Descriptor
    validation stays in the same canonical codec as CLI hydration.
    """
    if not isinstance(documents, dict):
        raise ValueError("complete original-source document collections required")
    invoices = documents.get("invoices")
    if not isinstance(invoices, list):
        raise ValueError("complete original-source document collections required")

    def pdf_pointer(value):
        if isinstance(value, dict):
            pointers = value.get("evidence_pointers", [])
            fields = value.get("field_values", {})
            candidates = list(pointers) if isinstance(pointers, list) else []
            if isinstance(fields, dict):
                candidates += [field.get("pointer") for field in fields.values()
                               if isinstance(field, dict)]
            if any(isinstance(pointer, dict) and
                   isinstance(pointer.get("parser_profile"), str) and
                   pointer["parser_profile"].startswith("pdfplumber-")
                   for pointer in candidates):
                return True
            return any(pdf_pointer(child) for key, child in value.items()
                       if key not in ("evidence_pointers", "field_values"))
        if isinstance(value, list):
            return any(pdf_pointer(child) for child in value)
        return False

    for invoice in invoices:
        if not isinstance(invoice, dict):
            continue  # The original recording shape/verifier rejects this.
        if invoice.get("media_type") == "application/pdf" or "data_base64" in invoice:
            from freightrec.bundles import decode_pdf_descriptor
            decode_pdf_descriptor(invoice)
            raise ValueError("unsupported_source: original PDF observation snapshots are not supported")
        if pdf_pointer(invoice):
            raise ValueError("unsupported_source: PDF-derived invoice observations require original PDF bytes")


@dataclass(frozen=True)
class FrozenObservations:
    """Immutable JSON edition; each consumer receives its own parsed copy."""

    canonical_json: str
    sha256: str

    def load(self):
        if sha256(self.canonical_json.encode("utf-8")).hexdigest() != self.sha256:
            raise ValueError("frozen observation edition changed")
        def pairs(items):
            result = {}
            for key, item in items:
                if key in result:
                    raise ValueError("duplicate frozen observation key")
                result[key] = item
            return result

        def constant(_):
            raise ValueError("nonfinite frozen observation number")

        value = json.loads(self.canonical_json, object_pairs_hook=pairs, parse_constant=constant)
        if type(value) is not dict:
            raise ValueError("frozen observation object required")
        if value.get("adapter_version") == ADAPTER_VERSION:
            if set(value) != _V1_KEYS:
                raise ValueError("unexpected v1 observation fields")
            _require_json_observation_sources(value.get("source_documents"))
            return value
        if value.get("adapter_version") == ORIGINAL_BUNDLE_VERSION:
            return _validate_original_recording(value)
        raise ValueError("unsupported observation adapter edition")


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


def _recording_payload(documents, findings, links, strata, *, engine_version,
                       policy_version, source_resolver, tolerance_cents=0,
                       near_duplicate_ids=None, allow_original_pdf=False):
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
    if not allow_original_pdf:
        _require_json_observation_sources(documents)
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
    return payload


def _freeze(payload):
    encoded = _json(payload)
    return FrozenObservations(encoded, sha256(encoded.encode("utf-8")).hexdigest())


def freeze_recording(documents, findings, links, strata, *, engine_version,
                     policy_version, source_resolver, tolerance_cents=0,
                     near_duplicate_ids=None):
    """Unchanged JSON-only v1 capture; PDF injection remains unsupported."""
    return _freeze(_recording_payload(
        documents, findings, links, strata, engine_version=engine_version,
        policy_version=policy_version, source_resolver=source_resolver,
        tolerance_cents=tolerance_cents, near_duplicate_ids=near_duplicate_ids))


def _runtime_edition():
    """Local runtime closure, not package installation or historical attestation."""
    import freightrec
    packages = ("pdfplumber", "pdfminer-six", "pypdfium2", "pillow", "charset-normalizer",
                "cryptography", "cffi", "pycparser", "tzdata")
    try:
        dependencies = {name: version(name) for name in packages}
    except PackageNotFoundError as exc:
        raise ValueError("observation runtime dependency unavailable") from exc
    package_root = Path(freightrec.__file__).resolve().parent
    source = {"freightrec/" + str(path.relative_to(package_root)).replace("\\", "/"):
              sha256(path.read_bytes()).hexdigest() for path in sorted(package_root.rglob("*.py"))}
    for name in ("observations.py", "arms.py", "components.py", "metrics.py"):
        path = Path(__file__).resolve().with_name(name)
        source["evaluation/" + name] = sha256(path.read_bytes()).hexdigest()
    return {"python": list(sys.version_info[:3]), "implementation": platform.python_implementation(),
            "platform": sys.platform, "dependencies": dependencies, "implementation_sha256": source}


def _current_versions(engine_version, policy_version):
    from freightrec.engine.engine import ENGINE_VERSION
    from freightrec.reconcile.findings import POLICY_VERSION
    if engine_version != ENGINE_VERSION or policy_version != POLICY_VERSION:
        raise ValueError("observation engine/policy edition changed")


def _original_bundle_envelope(bundle, tolerance):
    """Validate retained metadata too: hydration returns only source documents."""
    if type(bundle) is not dict:
        raise ValueError("exact original bundle required")
    if set(bundle) - {"contracts", "shipments", "invoices", "fuel_index",
                      "data_origin", "tolerance_cents"}:
        raise ValueError("unexpected original bundle fields")
    # Preserve the codec's optional marker, but never allow ignored metadata
    # to carry labels/derived answers into the exact-original replay payload.
    if "data_origin" in bundle and (type(bundle["data_origin"]) is not str or
                                    bundle["data_origin"] != "builder_non_independent"):
        raise ValueError("original bundle data_origin must be builder_non_independent")
    recorded = bundle.get("tolerance_cents", 0)
    if type(tolerance) is not int or tolerance not in (0, 50, 100) or type(recorded) is not int or recorded != tolerance:
        raise ValueError("original bundle and recording tolerance differ")


def freeze_original_bundle_recording(original_bundle, documents, findings, links, strata, *,
                                     engine_version, policy_version, source_resolver,
                                     tolerance_cents=0, near_duplicate_ids=None):
    """Opt-in v2: retain exact originals and verify the entire recorded source edition."""
    from freightrec.bundles import hydrate_original_bundle
    if source_resolver is None:
        raise ValueError("current original source resolver required")
    _current_versions(engine_version, policy_version)
    _original_bundle_envelope(original_bundle, tolerance_cents)
    originals = deepcopy(original_bundle)
    # No new source registry or reconstructed JSON: rehydrate exact originals
    # into the actual retained resolver and compare every binding/typed field.
    resolver, fresh = hydrate_original_bundle(originals, resolver=source_resolver)
    if resolver is not source_resolver or _json(fresh) != _json(documents):
        raise ValueError("recorded original source edition differs")
    payload = _recording_payload(
        fresh, findings, links, strata, engine_version=engine_version, policy_version=policy_version,
        source_resolver=resolver, tolerance_cents=tolerance_cents,
        near_duplicate_ids=near_duplicate_ids, allow_original_pdf=True)
    payload.update(adapter_version=ORIGINAL_BUNDLE_VERSION, original_bundle=originals,
                   links=deepcopy(links), strata=deepcopy(strata),
                   near_duplicate_ids={} if near_duplicate_ids is None else deepcopy(near_duplicate_ids),
                   runtime_edition=_runtime_edition())
    return _freeze(payload)


def _validate_original_recording(value):
    """Single strict v2 boundary used by every loading consumer."""
    from freightrec.bundles import hydrate_original_bundle
    if set(value) != _V2_KEYS:
        raise ValueError("unexpected original observation fields")
    _current_versions(value["engine_version"], value["policy_version"])
    _original_bundle_envelope(value["original_bundle"], value["tolerance_cents"])
    if _json(value["runtime_edition"]) != _json(_runtime_edition()):
        raise ValueError("observation runtime/dependency edition changed")
    # Worker unavailable/timeout/protocol refusal propagates without a fallback.
    resolver, documents = hydrate_original_bundle(value["original_bundle"])
    if _json(documents) != _json(value["source_documents"]):
        raise ValueError("recorded original source edition differs")
    expected = _recording_payload(
        documents, value["recorded_findings"], value["links"], value["strata"],
        engine_version=value["engine_version"], policy_version=value["policy_version"],
        source_resolver=resolver, tolerance_cents=value["tolerance_cents"],
        near_duplicate_ids=value["near_duplicate_ids"], allow_original_pdf=True)
    expected["adapter_version"] = ORIGINAL_BUNDLE_VERSION
    for key in _V1_KEYS:
        if _json(value[key]) != _json(expected[key]):
            raise ValueError("recorded observation derivation differs:" + key)
    return value


def product_input(snapshot):
    """Facts only for replay; persisted link authority still belongs to DecisionLog."""
    value = snapshot.load()
    if value["adapter_version"] == ORIGINAL_BUNDLE_VERSION:
        return deepcopy(value["original_bundle"])
    documents = value["source_documents"]
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
