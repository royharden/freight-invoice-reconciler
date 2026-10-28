"""Bounded lexical record parsers; offsets always address original UTF-8 text.

The supported JSON layout is an array of flat scalar objects. CSV uses an
explicit header/schema, comma delimiters and RFC4180 double-quote escaping.
Neither parser searches for a rendered value to guess its source alignment.
"""

from dataclasses import dataclass
import json
import re

from .normalize import METADATA, normalize

MAX_RECORDS = 1_000
MAX_FIELDS = 100
MAX_CELL_CODEPOINTS = 4_000


@dataclass(frozen=True)
class Cell:
    start: int
    end: int
    quote: str
    value: str | int | bool | None
    normalizer_id: str


def field_name(value: object) -> str:
    if (type(value) is not str or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]*", value)
            or value in METADATA):
        raise ValueError("invalid_record_field")
    return value


def _finish(records: list[dict[str, Cell]], key_field: str) -> list[dict[str, Cell]]:
    field_name(key_field)
    if not 0 < len(records) <= MAX_RECORDS:
        raise ValueError("record_count_limit")
    schema = set(records[0])
    keys = set()
    for record in records:
        if set(record) != schema or key_field not in record:
            raise ValueError("record_schema_mismatch")
        key = record[key_field].value
        if type(key) is not str or not key or len(key) > 500:
            raise ValueError("record_key_must_be_nonempty_string")
        if key in keys:
            raise ValueError("nonunique_record_key")
        keys.add(key)
    return records


def json_records(text: str, key_field: str) -> list[dict[str, Cell]]:
    """Parse an explicit array of flat objects, preserving each JSON token span."""
    field_name(key_field)

    def refuse_number(_):
        raise ValueError("decimal_requires_string")

    decoder = json.JSONDecoder(parse_float=refuse_number, parse_constant=refuse_number)
    size = len(text)
    cursor = 0

    def skip():
        nonlocal cursor
        while cursor < size and text[cursor] in " \t\r\n":
            cursor += 1

    def take(character):
        nonlocal cursor
        skip()
        if cursor >= size or text[cursor] != character:
            raise ValueError("invalid_json_records_layout")
        cursor += 1

    def scalar():
        nonlocal cursor
        skip()
        start = cursor
        # Containers have no scalar-field representation in this bounded layout.
        if cursor >= size or text[cursor] in "[{":
            raise ValueError("flat_json_records_required")
        try:
            value, cursor = decoder.raw_decode(text, cursor)
        except (json.JSONDecodeError, RecursionError) as exc:
            raise ValueError("invalid_json_record_scalar") from exc
        quote = text[start:cursor]
        if len(quote) > MAX_CELL_CODEPOINTS:
            raise ValueError("record_cell_limit")
        if type(value) not in (str, int, bool, type(None)):
            raise ValueError("flat_json_records_required")
        if type(value) is str:
            value.encode("utf-8", errors="strict")
        return Cell(start, cursor, quote, value, "json-scalar-v1")

    take("[")
    records = []
    skip()
    if cursor < size and text[cursor] == "]":
        raise ValueError("record_count_limit")
    while True:
        take("{")
        record = {}
        while True:
            key = scalar()
            name = field_name(key.value)
            if name in record:
                raise ValueError("duplicate_json_key")
            take(":")
            record[name] = scalar()
            if len(record) > MAX_FIELDS:
                raise ValueError("record_field_limit")
            skip()
            if cursor < size and text[cursor] == ",":
                cursor += 1
                continue
            take("}")
            break
        records.append(record)
        if len(records) > MAX_RECORDS:
            raise ValueError("record_count_limit")
        skip()
        if cursor < size and text[cursor] == ",":
            cursor += 1
            continue
        take("]")
        break
    skip()
    if cursor != size:
        raise ValueError("json_records_trailing_content")
    return _finish(records, key_field)


def csv_cells(text: str) -> list[list[tuple[int, int, str]]]:
    """Tokenize exact CSV lexemes, retaining escaped quotes and line endings."""
    rows = []
    row = []
    cursor = 0
    size = len(text)
    while cursor < size:
        start = cursor
        if text[cursor] == '"':
            cursor += 1
            while True:
                if cursor >= size:
                    raise ValueError("unterminated_csv_quote")
                if text[cursor] != '"':
                    cursor += 1
                    continue
                if cursor + 1 < size and text[cursor + 1] == '"':
                    cursor += 2
                    continue
                cursor += 1
                break
            if cursor < size and text[cursor] not in ",\r\n":
                raise ValueError("csv_content_after_quote")
        else:
            while cursor < size and text[cursor] not in ",\r\n":
                if text[cursor] == '"':
                    raise ValueError("quote_inside_unquoted_csv_cell")
                cursor += 1
        quote = text[start:cursor]
        if not quote or len(quote) > MAX_CELL_CODEPOINTS:
            raise ValueError("empty_or_oversize_csv_cell")
        row.append((start, cursor, quote))
        if len(row) > MAX_FIELDS:
            raise ValueError("record_field_limit")
        if cursor == size:
            rows.append(row)
            break
        separator = text[cursor]
        cursor += 1
        if separator == ",":
            if cursor == size:
                raise ValueError("empty_csv_cell")
            continue
        if separator == "\r":
            if cursor >= size or text[cursor] != "\n":
                raise ValueError("csv_lone_carriage_return")
            cursor += 1
        rows.append(row)
        row = []
        if len(rows) > MAX_RECORDS + 1:
            raise ValueError("record_count_limit")
    if not 2 <= len(rows) <= MAX_RECORDS + 1:
        raise ValueError("csv_header_and_records_required")
    return rows


def decode_csv_cell(quote: str) -> str:
    """Decode one already-bounded CSV lexeme, checking escaping independently."""
    if not quote or len(quote) > MAX_CELL_CODEPOINTS:
        raise ValueError("empty_or_oversize_csv_cell")
    if quote.startswith('"'):
        if not quote.endswith('"') or len(quote) < 2:
            raise ValueError("invalid_csv_cell")
        inner = quote[1:-1]
        cursor = 0
        decoded = []
        while cursor < len(inner):
            if inner[cursor] == '"':
                if cursor + 1 >= len(inner) or inner[cursor + 1] != '"':
                    raise ValueError("invalid_csv_escape")
                cursor += 1
            decoded.append(inner[cursor])
            cursor += 1
        return "".join(decoded)
    if any(character in quote for character in ',"\r\n'):
        raise ValueError("invalid_csv_cell")
    return quote


def csv_records(text: str, key_field: str, normalizers: dict[str, str]) -> list[dict[str, Cell]]:
    """Require explicit converters for every uniquely named CSV column."""
    field_name(key_field)
    if type(normalizers) is not dict:
        raise ValueError("csv_normalizers_required")
    rows = csv_cells(text)
    headers = [field_name(decode_csv_cell(cell[2])) for cell in rows[0]]
    if len(set(headers)) != len(headers):
        raise ValueError("duplicate_csv_header")
    if set(normalizers) != set(headers):
        raise ValueError("csv_normalizer_schema_mismatch")
    records = []
    for row in rows[1:]:
        if len(row) != len(headers):
            raise ValueError("csv_record_width_mismatch")
        record = {}
        for name, (start, end, quote) in zip(headers, row):
            converter = normalizers[name]
            if (type(converter) is not str or converter.startswith("csv-cell:")
                    or converter in {"json-document-v1", "json-scalar-v1"}):
                raise ValueError("invalid_csv_normalizer")
            normalizer_id = "csv-cell:" + converter
            record[name] = Cell(start, end, quote, normalize(quote, normalizer_id), normalizer_id)
        records.append(record)
    return _finish(records, key_field)
