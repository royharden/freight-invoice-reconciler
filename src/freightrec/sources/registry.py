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

    def resolve(self, pointer: SpanPointer | dict) -> str:
        if isinstance(pointer, dict):
            try:
                pointer = SpanPointer(**pointer)
            except TypeError as exc:
                raise ValueError("invalid_pointer_shape") from exc
        if not isinstance(pointer, SpanPointer):
            raise ValueError("invalid_pointer_shape")
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
        return quote

    def snapshot(self) -> list[dict]:
        """Stable dependency material, including each archived parser edition."""
        return [
            {"source_sha256": source_hash, "parser_profile": profile,
             "page_text_sha256": [digest(page) for page in pages]}
            for (source_hash, profile), pages in sorted(self._pages.items())
        ]
