"""Pure batch findings; no providers, external effects, or evaluation imports."""

from collections import Counter

from ..link import link_shipment, normalize_reference
from ..link.link import resolve_target
from ..sources import verify_document
from .allocate import allocation_key, issue_time
from .findings import POLICY_VERSION, canonical, cents, classify, digest


def _pointers(value: dict) -> list[dict]:
    pointers = value.get("evidence_pointers", value.get("pointers", []))
    if isinstance(pointers, dict):
        pointers = list(pointers.values())
    return pointers if isinstance(pointers, list) and all(isinstance(p, dict) for p in pointers) else []


def _identity(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and len(value) <= 200


def _sorted(values: list[dict]) -> list[dict]:
    return sorted(values, key=canonical)


def _dependency_value(value: object, key: str = "") -> object:
    """Canonicalize facts; verified certificate identities are joined separately."""
    if isinstance(value, dict):
        return {k: _dependency_value(v, k) for k, v in value.items() if k != "field_values"}
    if isinstance(value, list):
        items = [_dependency_value(v) for v in value]
        return sorted(items, key=canonical) if key in ("lines", "evidence_pointers", "pointers") else items
    return value


def _binding_identity(document: dict) -> dict:
    """Bind each verified fact to its conversion and exact source span.

    Nest certificates at their fact paths before sorting invoice lines, so a
    matching line/certificate permutation does not retain incidental indexes.
    Whole-document pointers still bind the original JSON's exact source order.
    """
    fields = document["field_values"]

    def certificate(field):
        return {key: field[key] for key in ("pointer", "normalizer_id", "method")}

    if "$document" in fields:
        return {"$document": certificate(fields["$document"])}

    def walk(value, path="", key=""):
        if isinstance(value, dict):
            return {
                name: walk(child, f"{path}.{name}" if path else name, name)
                for name, child in value.items()
                if name not in ("field_values", "evidence_pointers", "source_sha256")
            }
        if isinstance(value, list):
            items = [walk(child, f"{path}.{index}") for index, child in enumerate(value)]
            return sorted(items, key=canonical) if key in ("lines", "pointers") else items
        return {"value": value, **certificate(fields[path])}

    return walk(document)


def reconcile_batch(
    contracts: list[dict], shipments: list[dict], invoices: list[dict],
    fuel_index: list[dict], sources=None, tolerance_cents: int = 0,
    link_resolver=None,
) -> list[dict]:
    """Allocate each entitlement once across the complete supplied invoice batch.

    Inputs must be JSON-compatible domain dictionaries. Missing sources refuse
    monetary action. SourceResolver.snapshot() binds all archived source pages.
    This function never interprets a failed engine lookup as zero entitlement.
    """
    if type(tolerance_cents) is not int or tolerance_cents not in (0, 50, 100):
        raise ValueError("tolerance_must_be_0_50_or_100_cents")
    if link_resolver is not None and not callable(link_resolver):
        raise ValueError("link_resolver_must_be_code_callback")
    from ..engine.engine import ENGINE_VERSION, price_contracts
    if not isinstance(ENGINE_VERSION, str) or not ENGINE_VERSION:
        raise ValueError("engine_version_required")

    verified, invalid = {}, {}
    for document in contracts + shipments + invoices + fuel_index:
        document_key = digest(document)
        try:
            if sources is None:
                raise ValueError("source_resolver_missing")
            verified[document_key] = verify_document(document, sources)
        except (ValueError, TypeError, KeyError) as exc:
            invalid[document_key] = "source_binding_invalid:" + str(exc)

    def dependency(document):
        document_key = digest(document)
        if document_key in verified:
            binding = {
                "verified": True,
                "pointers": _sorted(verified[document_key]),
                "certificates": _binding_identity(document),
            }
        else:
            # Invalid/missing certificates must never share a formerly valid
            # approval dependency, even when all consumed typed facts agree.
            binding = {
                "verified": False, "error": invalid[document_key],
                "certificates": document.get("field_values"),
            }
        return {"document": _dependency_value(document), "source_binding": binding}

    closure = {
        "closure_version": "freightrec-verified-bindings-v1",
        "policy": POLICY_VERSION, "engine_version": ENGINE_VERSION,
        "tolerance_cents": tolerance_cents,
        "contracts": _sorted([dependency(v) for v in contracts]),
        "shipments": _sorted([dependency(v) for v in shipments]),
        "invoices": _sorted([dependency(v) for v in invoices]),
        "fuel_index": _sorted([dependency(v) for v in fuel_index]),
        "sources": sources.snapshot() if sources is not None else None,
    }
    original_dependency_hash = digest(closure)
    rows = []
    # Preserve even malformed identities and duplicate records as findings.
    for invoice in invoices:
        lines = invoice.get("lines")
        if not isinstance(lines, list) or not lines:
            lines = [{"missing_facts": ["invoice_lines_missing"]}]
        for line in lines:
            if not isinstance(line, dict):
                line = {"invalid_line": line}
            row = {
                "carrier": invoice.get("carrier"), "invoice_id": invoice.get("invoice_id"),
                "invoice_issue_ts": invoice.get("invoice_issue_ts"),
                "line_id": line.get("line_id"), "code": line.get("code"),
                "stop_seq": line.get("stop_seq"), "line": line, "invoice": invoice,
                "billed": cents(line.get("billed_cents")), "errors": [],
            }
            row["invoice_pointers"] = verified.get(digest(invoice), [])
            row["line_pointers"] = _pointers(line) or row["invoice_pointers"]
            if digest(invoice) in invalid:
                row["errors"].append(invalid[digest(invoice)])
            if invoice.get("currency") != "USD":
                row["errors"].append("unsupported_currency")
            if line.get("currency") != "USD":
                row["errors"].append("line_currency_must_be_USD")
            total = cents(invoice.get("total_cents"))
            amounts = [cents(item.get("billed_cents")) if isinstance(item, dict) else None for item in lines]
            if total is None or any(value is None for value in amounts) or sum(value for value in amounts if value is not None) != total:
                row["errors"].append("invoice_total_mismatch")
            link = link_shipment(row["carrier"], line.get("shipment_ref", line.get("shipment_id")), shipments)
            row["auto_link"] = link
            row["link_method"] = "exact_namespaced_reference"
            row["shipment"] = link["shipment"]
            if link["shipment"] is not None:
                shipment_id = link["shipment"].get("shipment_id")
                if not _identity(shipment_id):
                    row["errors"].append("shipment_id_missing")
                else:
                    row["shipment_key"] = shipment_id
            for field in ("invoice_id", "line_id"):
                if not _identity(row[field]):
                    row["errors"].append(field + "_missing")
            if row["code"] not in ("LH", "FS", "DETENTION", "LIFTGATE"):
                row["errors"].append("charge_code_unknown")
            if type(row["stop_seq"]) is not int or row["stop_seq"] < 0:
                row["errors"].append("stop_seq_missing")
            elif row["code"] in ("LH", "FS") and row["stop_seq"] != 0:
                row["errors"].append("shipment_charge_stop_must_be_zero")
            elif row["code"] in ("DETENTION", "LIFTGATE") and row["stop_seq"] == 0:
                row["errors"].append("accessorial_stop_must_be_positive")
            if row["billed"] is None:
                row["errors"].append("billed_cents_invalid")
            try:
                issue_time(row["invoice_issue_ts"])
            except ValueError as exc:
                row["errors"].append(str(exc))
            missing = line.get("missing_facts", [])
            if not isinstance(missing, list) or not all(isinstance(x, str) for x in missing):
                row["errors"].append("missing_facts_invalid")
            else:
                row["errors"].extend(missing)
            if not row["invoice_pointers"] or not row["line_pointers"]:
                row["errors"].append("invoice_evidence_missing")
            if sources is None:
                row["errors"].append("source_resolver_missing")
            else:
                try:
                    for pointer in row["invoice_pointers"] + row["line_pointers"]:
                        sources.resolve(pointer)
                except (ValueError, TypeError, KeyError):
                    row["errors"].append("source_pointer_invalid")
            rows.append(row)
    def occurrence_identity(row):
        try:
            namespace = normalize_reference(row["carrier"])
        except ValueError:
            namespace = row["carrier"]
        return {"carrier": namespace, "invoice_id": row["invoice_id"], "line_id": row["line_id"]}
    ids = Counter(canonical(occurrence_identity(row)) for row in rows)
    # Assign IDs from original data before manual links or allocation ordering.
    # This keeps baseline and resolved contexts identical and avoids recursion.
    rows.sort(key=lambda r: canonical(r["invoice"]) + canonical(r["line"]))
    serials, applied_links = Counter(), []
    for row in rows:
        identity = occurrence_identity(row)
        identity_hash = digest(identity)
        ordinal = serials[identity_hash]
        serials[identity_hash] += 1
        row["occurrence_id"] = digest({"identity": identity, "ordinal": ordinal})
        unique = ids[canonical(identity)] == 1
        if not unique:
            row["errors"].append("occurrence_identity_ambiguous")
        row["link_context"] = None
        # Link approval is separate from money approval. A valid source-backed
        # occurrence can expose a context even when other pricing facts fail.
        if (unique and row["invoice_pointers"] and row["billed"] is not None
                and _identity(row["invoice_id"]) and _identity(row["line_id"])):
            try:
                carrier = normalize_reference(row["carrier"])
                reference = normalize_reference(row["line"].get("shipment_ref", row["line"].get("shipment_id")))
                row["link_context"] = {
                    "context_id": digest({"link_occurrence": row["occurrence_id"]}),
                    "occurrence_id": row["occurrence_id"], "carrier": carrier,
                    "reference": reference, "dependency_hash": original_dependency_hash,
                }
            except ValueError:
                pass
        if row["shipment"] is None and row["link_context"] is not None and link_resolver is not None:
            try:
                target = link_resolver(dict(row["link_context"]))
                shipment = resolve_target(row["carrier"], target, shipments, lambda value: digest(value) in verified)
                if shipment is not None:
                    row["shipment"] = shipment
                    row["shipment_key"] = shipment["shipment_id"]
                    row["link_method"] = "trusted_code_ruling"
                    applied_links.append({"context_id": row["link_context"]["context_id"], "target_shipment_id": shipment["shipment_id"]})
                elif target is not None:
                    row["errors"].append("manual_link_target_invalid")
            except (ValueError, TypeError, KeyError):
                row["errors"].append("link_resolver_refused")
        if row["shipment"] is None:
            row["errors"].append(row["auto_link"]["reason_code"])
    dependency_hash = digest({
        "original_dependency_hash": original_dependency_hash,
        "applied_links": sorted(applied_links, key=canonical),
    })
    # Invalid rows cannot displace a valid occurrence during allocation. Any
    # incomplete row in a linked group poisons that group's duplicate inference.
    def group(row):
        return (normalize_reference(row["carrier"]), row.get("shipment_key"), row["code"], row["stop_seq"])
    # A malformed charge code or stop cannot safely be assigned to a smaller
    # duplicate group. Refuse all linked charges for that shipment conservatively.
    blocked = {(normalize_reference(r["carrier"]), r["shipment_key"]) for r in rows if r.get("shipment_key") and r["errors"]}
    rows.sort(key=lambda r: (bool(r["errors"]), allocation_key(r) if not r["errors"] else canonical(r["invoice"]) + canonical(r["line"])))
    seen, engine_cache = set(), {}
    findings = []
    for row in rows:
        errors = list(row["errors"])
        entitlement, expected, duplicate = None, None, False
        pointers = row["invoice_pointers"] + row["line_pointers"]
        trace = [{"step": "link", "method": row["link_method"], "shipment_id": row.get("shipment_key")}]
        if not errors:
            key = group(row)
            if key[:2] in blocked:
                errors.append("allocation_group_incomplete")
            shipment = row["shipment"]
            if digest(shipment) in invalid:
                errors.append(invalid[digest(shipment)])
            cache_key = digest(shipment)
            if cache_key not in engine_cache:
                # The engine resolves version/basis applicability; never choose
                # the latest contract as a reconciliation fallback.
                candidates = []
                for contract in contracts:
                    try:
                        if normalize_reference(contract.get("carrier")) == key[0]:
                            candidates.append(contract)
                    except ValueError:
                        continue
                engine_errors = [invalid[digest(document)] for document in [shipment] + candidates + fuel_index if digest(document) in invalid]
                result = []
                if not engine_errors:
                    # Match the linker's explicit namespace rule while retaining
                    # the original source-bound spelling in the dependency hash.
                    normalized_contracts = [{**contract, "carrier": key[0]} for contract in candidates]
                    normalized_shipment = {**shipment, "carrier": key[0]}
                    try:
                        result = price_contracts(normalized_contracts, normalized_shipment, fuel_index)
                    except (ValueError, TypeError, KeyError, ArithmeticError) as exc:
                        engine_errors.append("engine_input_invalid:" + str(exc))
                engine_cache[cache_key] = (candidates, result, engine_errors)
            candidates, result, engine_errors = engine_cache[cache_key]
            errors.extend(engine_errors)
            for document in candidates + fuel_index:
                if digest(document) in invalid:
                    errors.append(invalid[digest(document)])
            matched = [e for e in result if e.get("code") == row["code"] and e.get("stop_seq") == row["stop_seq"]]
            if len(matched) != 1 or cents(matched[0].get("expected_cents")) is None:
                errors.append("entitlement_missing_or_ambiguous")
                for item in result:
                    errors.extend(item.get("missing_facts", []))
            else:
                entitlement = matched[0]
                pointers += verified.get(digest(shipment), []) + _pointers(entitlement)
                for contract in candidates:
                    pointers += verified.get(digest(contract), [])
                for entry in fuel_index:
                    pointers += verified.get(digest(entry), [])
                trace.extend(entitlement.get("trace", []))
                errors.extend(entitlement.get("missing_facts", []))
                if not entitlement.get("clause_id"):
                    errors.append("clause_id_missing")
                # Require invoice/line/shipment/contract provenance independently.
                if not candidates or not all(verified.get(digest(v)) for v in (row["invoice"], shipment, *candidates)):
                    errors.append("required_evidence_missing")
                if sources is None:
                    errors.append("source_resolver_missing")
                else:
                    try:
                        for pointer in pointers:
                            sources.resolve(pointer)
                    except (ValueError, TypeError, KeyError):
                        errors.append("source_pointer_invalid")
                if not errors:
                    duplicate = key in seen
                    expected = 0 if duplicate else entitlement["expected_cents"]
                    seen.add(key)
        identity = occurrence_identity(row)
        occurrence_id = row["occurrence_id"]
        verdict, disputed = classify(row["billed"], expected, tolerance_cents)
        reason = errors[0] if errors else ("duplicate_charge" if duplicate else "priced_entitlement")
        trace.append({"step": "allocation", "duplicate": duplicate, "expected_cents": expected, "deadband_cents": tolerance_cents, "no_undercharge_netting": True})
        findings.append({
            "finding_id": digest({"occurrence_id": occurrence_id, "policy": POLICY_VERSION}),
            "occurrence_id": occurrence_id, "occurrence": identity,
            "link_context": row["link_context"],
            "dependency_hash": dependency_hash, "billed_cents": row["billed"],
            "expected_cents": expected, "disputed_cents": disputed,
            "verdict": verdict, "reason_code": reason, "trace": trace,
            "clause_id": entitlement.get("clause_id") if entitlement else None,
            "evidence_pointers": pointers, "missing_facts": sorted(set(errors)),
            "owner_to_ask": "source_owner" if errors else None,
        })
    return sorted(findings, key=lambda finding: finding["occurrence_id"])
