"""Deterministic quote-to-wire conversions without importing ingestion."""

from datetime import date, datetime
from decimal import Decimal
import json
import re


METADATA = frozenset({"evidence_pointers", "field_values", "source_sha256"})


def validate_payload(value, depth: int = 0) -> None:
    """Bound JSON values and reserve provenance names rather than hide facts."""
    if depth > 40:
        raise ValueError("document_depth_limit")
    if type(value) is dict:
        for key, child in value.items():
            if (type(key) is not str or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", key)
                    or key in METADATA):
                raise ValueError("ambiguous_document_key")
            validate_payload(child, depth + 1)
    elif type(value) is list:
        for child in value:
            validate_payload(child, depth + 1)
    elif type(value) is str:
        value.encode("utf-8", errors="strict")
    elif type(value) not in (str, int, bool, type(None)):
        raise ValueError("non_wire_value")


def parse_document(raw: str) -> dict:
    def object_pairs(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate_json_key")
            result[key] = value
        return result

    def refuse_number(_):
        raise ValueError("decimal_requires_string")

    try:
        value = json.loads(raw, object_pairs_hook=object_pairs,
                           parse_float=refuse_number, parse_constant=refuse_number)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("invalid_json_document") from exc
    if type(value) is not dict or not value:
        raise ValueError("document_object_required")
    validate_payload(value)
    return value


def normalize(raw: str, normalizer_id: str):
    if type(raw) is not str or not raw or type(normalizer_id) is not str:
        raise ValueError("invalid_field_text")
    if normalizer_id == "json-document-v1":
        return parse_document(raw)
    if normalizer_id == "json-scalar-v1":
        if len(raw) > 4_000:
            raise ValueError("record_cell_limit")

        def refuse_number(_):
            raise ValueError("decimal_requires_string")

        try:
            value = json.loads(raw, parse_float=refuse_number, parse_constant=refuse_number)
        except (json.JSONDecodeError, RecursionError) as exc:
            raise ValueError("invalid_json_scalar") from exc
        if type(value) not in (str, int, bool, type(None)):
            raise ValueError("json_scalar_required")
        if type(value) is str:
            value.encode("utf-8", errors="strict")
        return value
    if normalizer_id.startswith("csv-cell:"):
        from .records import decode_csv_cell

        converter = normalizer_id[len("csv-cell:"):]
        if not converter or converter.startswith("csv-cell:") or converter in {"json-document-v1", "json-scalar-v1"}:
            raise ValueError("invalid_csv_normalizer")
        return normalize(decode_csv_cell(raw), converter)
    if len(raw) > 500:
        raise ValueError("invalid_field_text")
    if normalizer_id == "string-v1":
        return raw
    if normalizer_id == "identifier-v1":
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _./-]{0,99}", raw):
            raise ValueError("invalid_identifier")
        return raw
    if normalizer_id == "decimal-string-v1":
        if not re.fullmatch(r"-?(?:0|[1-9][0-9]*)(?:\.[0-9]+)?", raw):
            raise ValueError("invalid_decimal_string")
        return raw
    if normalizer_id == "usd-cents-v1":
        if not re.fullmatch(r"(?:0|[1-9][0-9]{0,10})\.[0-9]{2}", raw):
            raise ValueError("invalid_usd_amount")
        return int(Decimal(raw) * 100)
    if normalizer_id in {"positive-int-v1", "nonnegative-int-v1", "int-v1"}:
        patterns = {"positive-int-v1": r"[1-9][0-9]{0,17}",
                    "nonnegative-int-v1": r"(?:0|[1-9][0-9]{0,17})",
                    "int-v1": r"-?(?:0|[1-9][0-9]{0,17})"}
        if not re.fullmatch(patterns[normalizer_id], raw):
            raise ValueError("invalid_integer")
        return int(raw)
    if normalizer_id == "bool-v1":
        if raw not in {"true", "false"}:
            raise ValueError("invalid_boolean")
        return raw == "true"
    if normalizer_id == "null-v1":
        if raw != "null":
            raise ValueError("invalid_null")
        return None
    if normalizer_id == "iso-date-v1":
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", raw):
            raise ValueError("invalid_date")
        date.fromisoformat(raw)
        return raw
    if normalizer_id == "iso-offset-v1":
        if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:Z|[+-][0-9]{2}:[0-9]{2})", raw):
            raise ValueError("explicit_offset_required")
        value = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if value.utcoffset() is None:
            raise ValueError("explicit_offset_required")
        return raw
    if normalizer_id == "charge-code-v1":
        values = {"LH": "LH", "LINEHAUL": "LH", "FS": "FS", "FUEL": "FS",
                  "DETENTION": "DETENTION", "LIFTGATE": "LIFTGATE"}
        try:
            return values[raw.upper()]
        except KeyError as exc:
            raise ValueError("unknown_charge_description") from exc
    raise ValueError("unknown_normalizer")
