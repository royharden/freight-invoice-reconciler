"""Fail-closed binding between consumed documents and archived raw source."""

import re

from .normalize import normalize, validate_payload
from .registry import SourceResolver


def _same(left, right) -> bool:
    """Python's True == 1 is unsuitable for provenance comparisons."""
    if type(left) is not type(right):
        return False
    if type(left) is dict:
        return left.keys() == right.keys() and all(_same(left[k], right[k]) for k in left)
    if type(left) is list:
        return len(left) == len(right) and all(_same(a, b) for a, b in zip(left, right))
    return left == right


def verify_document(document: dict, resolver: SourceResolver) -> list[dict]:
    """Bind all facts using a complete dotted-leaf map or a native JSON object."""
    if type(document) is not dict or not isinstance(resolver, SourceResolver):
        raise ValueError("document_and_resolver_required")
    fields = document.get("field_values")
    if type(fields) is not dict or not fields:
        raise ValueError("field_values_required")
    declared_pointers = []

    def strip(value, depth=0):
        if depth > 40:
            raise ValueError("document_depth_limit")
        if type(value) is dict:
            result = {}
            for key, child in value.items():
                if type(key) is not str or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", key):
                    raise ValueError("ambiguous_document_key")
                if key == "field_values":
                    if depth != 0:
                        raise ValueError("nested_field_values_refused")
                elif key == "source_sha256":
                    if depth != 0 or type(child) is not str or not re.fullmatch(r"[0-9a-f]{64}", child):
                        raise ValueError("invalid_source_metadata")
                elif key == "evidence_pointers":
                    if type(child) is not list:
                        raise ValueError("invalid_evidence_metadata")
                    declared_pointers.extend(child)
                else:
                    result[key] = strip(child, depth + 1)
            return result
        if type(value) is list:
            return [strip(child, depth + 1) for child in value]
        if type(value) not in (str, int, bool, type(None)):
            raise ValueError("non_wire_value")
        return value

    payload = strip(document)
    validate_payload(payload)
    if not payload:
        raise ValueError("empty_document")
    pointers = []
    record_identities = set()
    record_pointer_count = 0

    def verify_field(field, path=None):
        nonlocal record_pointer_count
        if type(field) is not dict or set(field) != {"raw_quote", "typed_value", "normalizer_id", "method", "pointer"}:
            raise ValueError("invalid_field_value")
        if (type(field["method"]) is not str
                or field["method"] not in {"freightrec-invoice-v1", "native-field-v1", "native-json-v1",
                                           "native-json-record-v1", "native-csv-record-v1"}):
            raise ValueError("unknown_extraction_method")
        pointer = field["pointer"]
        if type(pointer) is not dict:
            raise ValueError("invalid_pointer_shape")
        canonical_pointer = resolver.canonical_pointer(pointer)
        if resolver.resolve(canonical_pointer) != field["raw_quote"]:
            raise ValueError("raw_quote_mismatch")
        if "record_format" in canonical_pointer:
            if (path != canonical_pointer["field"]
                    or field["normalizer_id"] != canonical_pointer["normalizer_id"]
                    or field["method"] != f"native-{canonical_pointer['record_format']}-record-v1"):
                raise ValueError("record_field_conversion_changed")
            record_identities.add((canonical_pointer["source_sha256"], canonical_pointer["parser_profile"],
                                   canonical_pointer["record_index"], canonical_pointer["record_key"],
                                   canonical_pointer["key_field"]))
            record_pointer_count += 1
        elif field["method"] in {"native-json-record-v1", "native-csv-record-v1"}:
            raise ValueError("record_field_pointer_required")
        if ("source_sha256" in document
                and pointer["source_sha256"] != document["source_sha256"]):
            raise ValueError("source_metadata_mismatch")
        value = normalize(field["raw_quote"], field["normalizer_id"])
        if not _same(value, field["typed_value"]):
            raise ValueError("normalized_value_mismatch")
        if canonical_pointer not in pointers:
            pointers.append(canonical_pointer)
        return value

    if "$document" in fields:
        if set(fields) != {"$document"}:
            raise ValueError("mixed_document_binding")
        field = fields["$document"]
        if (type(field) is not dict or field.get("normalizer_id") != "json-document-v1"
                or field.get("method") != "native-json-v1"):
            raise ValueError("invalid_document_binding")
        if not _same(verify_field(field), payload):
            raise ValueError("document_payload_mismatch")
        pointer = pointers[0]
        page = resolver.page_text(pointer["source_sha256"], pointer["parser_profile"], pointer["page_index"])
        if (pointer["parser_profile"] != "native-json-v1" or pointer["page_index"] != 0
                or pointer["start"] != 0 or pointer["end"] != len(page)):
            raise ValueError("whole_native_json_source_required")
    else:
        leaves = {}

        def walk(value, path):
            if type(value) in (dict, list):
                if not value:
                    raise ValueError("empty_container_requires_document_binding")
                items = value.items() if type(value) is dict else enumerate(value)
                for key, child in items:
                    walk(child, f"{path}.{key}" if path else str(key))
            else:
                leaves[path] = value

        walk(payload, "")
        if set(fields) != set(leaves):
            raise ValueError("incomplete_field_values")
        for path, underlying in leaves.items():
            field = fields[path]
            if type(field) is dict and field.get("normalizer_id") == "json-document-v1":
                raise ValueError("document_normalizer_requires_root_binding")
            if not _same(verify_field(field, path), underlying):
                raise ValueError("underlying_value_mismatch")
        if record_pointer_count and (len(record_identities) != 1 or record_pointer_count != len(fields)):
            raise ValueError("mixed_record_bindings")
        if record_pointer_count and set(fields) != set(resolver.record_fields(pointers[0])):
            raise ValueError("incomplete_original_record")
    for pointer in declared_pointers:
        if type(pointer) is not dict or not any(_same(pointer, p) for p in pointers):
            raise ValueError("unbound_evidence_pointer")
    return pointers
