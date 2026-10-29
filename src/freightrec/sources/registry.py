"""In-memory, immutable source archives and verified half-open text spans."""

from dataclasses import asdict, dataclass
from hashlib import sha256
import re


def digest(text: str) -> str:
    return sha256(text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SpanPointer:
    source_sha256: str
    parser_profile: str
    page_text_sha256: str
    page_index: int
    start: int
    end: int
    quote_sha256: str

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class RecordFieldPointer(SpanPointer):
    record_format: str
    record_index: int
    record_key: str
    key_field: str
    field: str
    normalizer_id: str


class SourceResolver:
    """Archive original bytes separately from exact parser page-text editions.

    Registering the same bytes/profile with changed text refuses rather than
    silently replacing the edition referenced by earlier approvals.
    """

    def __init__(self, *, max_bytes: int = 8_000_000, max_pages: int = 100,
                 max_page_codepoints: int = 200_000):
        self.max_bytes = max_bytes
        self.max_pages = max_pages
        self.max_page_codepoints = max_page_codepoints
        self._raw: dict[str, bytes] = {}
        self._pages: dict[tuple[str, str], tuple[str, ...]] = {}
        self._tables: dict[tuple[str, str], tuple[dict, tuple[dict, ...]]] = {}

    def register_text(self, raw_bytes: bytes,
                      parser_profile: str = "native-text-v1") -> str:
        if not isinstance(raw_bytes, bytes) or not 0 < len(raw_bytes) <= self.max_bytes:
            raise ValueError("source_byte_limit")
        # Preserve CR/LF and every codepoint: never normalize before archiving.
        try:
            text = raw_bytes.decode("utf-8", errors="strict")
        except UnicodeError as exc:
            raise ValueError("invalid_utf8") from exc
        return self.register_pages(raw_bytes, [text], parser_profile)

    def register_document(self, raw_bytes: bytes) -> dict:
        """Bind an original native JSON object, never inferred PDF facts.

        This records source/value agreement, not truth or adjudication. Decimal
        quantities must be strings; floats, duplicate keys and metadata refuse.
        """
        from .normalize import normalize

        if type(raw_bytes) is not bytes or not 0 < len(raw_bytes) <= self.max_bytes:
            raise ValueError("source_byte_limit")
        try:
            raw_quote = raw_bytes.decode("utf-8", errors="strict")
        except UnicodeError as exc:
            raise ValueError("invalid_utf8") from exc
        if len(raw_quote) > self.max_page_codepoints:
            raise ValueError("page_text_limit")
        payload = normalize(raw_quote, "json-document-v1")
        # Independently parse so mutation cannot alter both comparisons at once.
        typed_value = normalize(raw_quote, "json-document-v1")
        profile = "native-json-v1"
        source_hash = self.register_text(raw_bytes, profile)
        pointer = self.pointer(source_hash, 0, 0, len(raw_quote), profile).to_dict()
        return {**payload, "source_sha256": source_hash,
                "evidence_pointers": [pointer],
                "field_values": {"$document": {
                    "raw_quote": raw_quote, "typed_value": typed_value,
                    "normalizer_id": "json-document-v1", "method": profile,
                    "pointer": pointer}}}

    def register_json_records(self, raw_bytes: bytes, key_field: str) -> list[dict]:
        """Bind flat scalar objects in an original JSON array to exact tokens."""
        return self._register_records(raw_bytes, "json", key_field, None)

    def register_csv_records(self, raw_bytes: bytes, key_field: str,
                             normalizers: dict[str, str]) -> list[dict]:
        """Bind CSV records using an explicit converter for every header."""
        return self._register_records(raw_bytes, "csv", key_field, normalizers)

    def _register_records(self, raw_bytes, record_format, key_field, normalizers):
        import json
        from .records import csv_records, json_records

        if type(raw_bytes) is not bytes or not 0 < len(raw_bytes) <= self.max_bytes:
            raise ValueError("source_byte_limit")
        try:
            text = raw_bytes.decode("utf-8", errors="strict")
        except UnicodeError as exc:
            raise ValueError("invalid_utf8") from exc
        if len(text) > self.max_page_codepoints:
            raise ValueError("page_text_limit")
        records = (json_records(text, key_field) if record_format == "json"
                   else csv_records(text, key_field, normalizers))
        schema = {"record_format": record_format, "key_field": key_field,
                  "normalizers": dict(normalizers) if normalizers is not None else None}
        schema_hash = digest(json.dumps(schema, sort_keys=True, separators=(",", ":")))
        profile = f"native-{record_format}-records-v1-{schema_hash}"
        source_hash = self.register_text(raw_bytes, profile)
        table_key = (source_hash, profile)
        expected_records = []
        documents = []
        for index, record in enumerate(records):
            record_key = record[key_field].value
            fields, pointers = {}, []
            for name, cell in record.items():
                span = self.pointer(source_hash, 0, cell.start, cell.end, profile)
                pointer = RecordFieldPointer(
                    **span.to_dict(), record_format=record_format, record_index=index,
                    record_key=record_key, key_field=key_field, field=name,
                    normalizer_id=cell.normalizer_id,
                ).to_dict()
                pointers.append(pointer)
                fields[name] = {"raw_quote": cell.quote, "typed_value": cell.value,
                                "normalizer_id": cell.normalizer_id,
                                "method": f"native-{record_format}-record-v1", "pointer": pointer}
            expected_records.append({name: dict(field["pointer"]) for name, field in fields.items()})
            documents.append({**{name: cell.value for name, cell in record.items()},
                              "source_sha256": source_hash, "evidence_pointers": pointers,
                              "field_values": fields})
        edition = (schema, tuple(expected_records))
        if table_key in self._tables and self._tables[table_key] != edition:
            raise ValueError("record_edition_changed")
        self._tables[table_key] = edition
        return documents

    def register_pages(self, raw_bytes: bytes, pages: list[str],
                       parser_profile: str) -> str:
        if not isinstance(raw_bytes, bytes) or not 0 < len(raw_bytes) <= self.max_bytes:
            raise ValueError("source_byte_limit")
        if not isinstance(parser_profile, str) or not parser_profile or len(parser_profile) > 100:
            raise ValueError("parser_profile_required")
        if not isinstance(pages, list) or not 0 < len(pages) <= self.max_pages:
            raise ValueError("page_limit")
        if any(not isinstance(page, str) or len(page) > self.max_page_codepoints for page in pages):
            raise ValueError("page_text_limit")
        if parser_profile in {"native-text-v1", "native-json-v1"}:
            try:
                native_text = raw_bytes.decode("utf-8", errors="strict")
            except UnicodeError as exc:
                raise ValueError("invalid_utf8") from exc
            if pages != [native_text]:
                raise ValueError("native_source_text_mismatch")
        # Encode now to reject lone surrogates before creating pointers.
        for page in pages:
            digest(page)
        source_hash = sha256(raw_bytes).hexdigest()
        key = (source_hash, parser_profile)
        edition = tuple(pages)
        if key in self._pages and self._pages[key] != edition:
            raise ValueError("parser_edition_changed")
        self._raw[source_hash] = raw_bytes
        self._pages[key] = edition
        return source_hash

    def page_text(self, source_sha256: str, parser_profile: str, page_index: int) -> str:
        if (type(source_sha256) is not str or not re.fullmatch(r"[0-9a-f]{64}", source_sha256)
                or type(parser_profile) is not str or not 0 < len(parser_profile) <= 100):
            raise ValueError("invalid_source_identity")
        if type(page_index) is not int or page_index < 0:
            raise ValueError("invalid_page_index")
        try:
            return self._pages[(source_sha256, parser_profile)][page_index]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("source_edition_unavailable") from exc

    def pointer(self, source_sha256: str, page_index: int, start: int, end: int,
                parser_profile: str = "native-text-v1") -> SpanPointer:
        page = self.page_text(source_sha256, parser_profile, page_index)
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(page):
            raise ValueError("invalid_span")
        return SpanPointer(source_sha256, parser_profile, digest(page), page_index,
                           start, end, digest(page[start:end]))

    def canonical_pointer(self, pointer: SpanPointer | dict) -> dict:
        if isinstance(pointer, dict):
            try:
                pointer_type = RecordFieldPointer if "record_format" in pointer else SpanPointer
                pointer = pointer_type(**pointer)
            except TypeError as exc:
                raise ValueError("invalid_pointer_shape") from exc
        if not isinstance(pointer, SpanPointer):
            raise ValueError("invalid_pointer_shape")
        return pointer.to_dict()

    def record_fields(self, pointer: RecordFieldPointer | dict) -> tuple[str, ...]:
        """Return the full immutable field schema for a verified record pointer."""
        canonical = self.canonical_pointer(pointer)
        if "record_format" not in canonical:
            raise ValueError("record_field_pointer_required")
        self.resolve(canonical)
        _, records = self._tables[(canonical["source_sha256"], canonical["parser_profile"])]
        return tuple(records[canonical["record_index"]])

    def resolve(self, pointer: SpanPointer | dict) -> str:
        canonical = self.canonical_pointer(pointer)
        pointer_type = RecordFieldPointer if "record_format" in canonical else SpanPointer
        pointer = pointer_type(**canonical)
        if any(type(value) is not str or not re.fullmatch(r"[0-9a-f]{64}", value)
               for value in (pointer.source_sha256, pointer.page_text_sha256,
                             pointer.quote_sha256)):
            raise ValueError("invalid_pointer_digest")
        page = self.page_text(pointer.source_sha256, pointer.parser_profile, pointer.page_index)
        raw = self._raw.get(pointer.source_sha256)
        if raw is None or sha256(raw).hexdigest() != pointer.source_sha256:
            raise ValueError("source_bytes_changed")
        if digest(page) != pointer.page_text_sha256:
            raise ValueError("page_text_changed")
        if type(pointer.start) is not int or type(pointer.end) is not int:
            raise ValueError("invalid_span")
        if not 0 <= pointer.start < pointer.end <= len(page):
            raise ValueError("invalid_span")
        quote = page[pointer.start:pointer.end]
        if digest(quote) != pointer.quote_sha256:
            raise ValueError("quote_changed")
        if ((pointer.source_sha256, pointer.parser_profile) in self._tables
                and not isinstance(pointer, RecordFieldPointer)):
            raise ValueError("record_field_pointer_required")
        if isinstance(pointer, RecordFieldPointer):
            if type(pointer.record_index) is not int or pointer.record_index < 0:
                raise ValueError("invalid_record_index")
            if (type(pointer.record_key) is not str or not pointer.record_key
                    or type(pointer.field) is not str or type(pointer.key_field) is not str
                    or type(pointer.normalizer_id) is not str):
                raise ValueError("invalid_record_identity")
            try:
                schema, records = self._tables[(pointer.source_sha256, pointer.parser_profile)]
                expected = records[pointer.record_index][pointer.field]
            except (KeyError, IndexError, TypeError) as exc:
                raise ValueError("record_edition_unavailable") from exc
            if (pointer.record_format != schema["record_format"]
                    or pointer.key_field != schema["key_field"] or canonical != expected):
                raise ValueError("record_field_binding_changed")
        return quote

    def snapshot(self) -> list[dict]:
        """Stable dependency material, including each archived parser edition."""
        return [
            {"source_sha256": source_hash, "parser_profile": profile,
             "page_text_sha256": [digest(page) for page in pages]}
            for (source_hash, profile), pages in sorted(self._pages.items())
        ]
