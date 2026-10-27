"""The explicit freightrec-invoice-v1 grammar is the entire accepted layout."""

import re

from freightrec.sources import SourceResolver, verify_document

from .normalize import normalize
from .pdftext import extract_pdf_pages


TEMPLATE_ID = "freightrec-invoice-v1"
MAX_LINES = 1_000


def extract(document_slice: dict) -> dict:
    """Extract bounded text/PDF input; invalid input never yields an invoice.

    The caller retains the supplied resolver (or the returned resolver) for
    evidence resolution. All spans refer to unmodified archived page text.
    """
    fields: dict = {}
    pointers: list[dict] = []
    source_hash = None
    resolver = document_slice.get("resolver") if isinstance(document_slice, dict) else None
    if resolver is None:
        resolver = SourceResolver()
    if not isinstance(resolver, SourceResolver):
        return {"status": "refused", "reason_code": "invalid_source_resolver",
                "fields": {}, "pointers": [], "invoice": None,
                "source_sha256": None, "missing_facts": ["source_resolver"]}
    try:
        if not isinstance(document_slice, dict):
            raise ValueError("document_slice_required")
        if document_slice.get("template_id") != TEMPLATE_ID:
            raise ValueError("unknown_layout")
        raw = document_slice.get("raw_bytes")
        if raw is None:
            text = document_slice.get("text")
            if not isinstance(text, str):
                raise ValueError("source_bytes_required")
            raw = text.encode("utf-8")
        if not isinstance(raw, bytes) or not 0 < len(raw) <= resolver.max_bytes:
            raise ValueError("source_byte_limit")
        media_type = document_slice.get("media_type")
        if media_type == "text/plain":
            profile = "native-text-v1"
            source_hash = resolver.register_text(raw, profile)
        elif media_type == "application/pdf":
            pages, profile = extract_pdf_pages(raw, max_bytes=resolver.max_bytes,
                                                max_pages=resolver.max_pages)
            source_hash = resolver.register_pages(raw, pages, profile)
            # v1 has no continuation-page grammar: never concatenate pages.
            if len(pages) != 1:
                raise ValueError("unknown_layout")
        else:
            raise ValueError("unsupported_media_type")
        text = resolver.page_text(source_hash, profile, 0)
        lines = text.splitlines(keepends=True)
        if not 8 <= len(lines) <= MAX_LINES + 7:
            raise ValueError("invoice_line_limit")
        positioned = []
        offset = 0
        for line in lines:
            # Strip only grammar line delimiters, preserving offsets in archive.
            body = line[:-2] if line.endswith("\r\n") else line[:-1] if line.endswith("\n") else line
            if "\r" in body or "\n" in body:
                raise ValueError("unknown_layout")
            positioned.append((body, offset))
            offset += len(line)
        if positioned[0][0] != "FREIGHTREC INVOICE V1" or positioned[6][0] != "Lines:":
            raise ValueError("unknown_layout")

        def capture(path: str, raw_quote: str, normalizer_id: str, start: int):
            value = normalize(raw_quote, normalizer_id)
            pointer = resolver.pointer(source_hash, 0, start, start + len(raw_quote), profile).to_dict()
            if resolver.resolve(pointer) != raw_quote:
                raise ValueError("span_invalid")
            # Deterministic normalization is separately retained from the quote.
            fields[path] = {"raw_quote": raw_quote, "typed_value": value,
                            "normalizer_id": normalizer_id, "method": TEMPLATE_ID,
                            "pointer": pointer}
            pointers.append(pointer)
            return value

        def header(index: int, label: str, path: str, normalizer_id: str):
            body, base = positioned[index]
            prefix = label + ": "
            if not body.startswith(prefix):
                raise ValueError("unknown_layout")
            quote = body[len(prefix):]
            return capture(path, quote, normalizer_id, base + len(prefix))

        carrier = header(1, "Carrier", "carrier", "identifier-v1")
        invoice_id = header(2, "Invoice", "invoice_id", "identifier-v1")
        issued = header(3, "Issued", "invoice_issue_ts", "iso-offset-v1")
        if positioned[4][0] != "Currency: USD":
            raise ValueError("unsupported_currency")
        capture("currency", "USD", "identifier-v1", positioned[4][1] + len("Currency: "))
        total = header(5, "Total", "total_cents", "usd-cents-v1")
        invoice_lines = []
        line_ids = set()
        for index, (body, base) in enumerate(positioned[7:]):
            # ID|shipment-reference|code-or-known-description|stop-seq|USD|dollars
            match = re.fullmatch(r"([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|(USD)\|([^|]+)", body)
            if match is None:
                raise ValueError("unknown_layout")
            path = f"lines.{index}"

            def cell(group: int, name: str, normalizer_id: str):
                return capture(f"{path}.{name}", match.group(group), normalizer_id,
                               base + match.start(group))

            line_id = cell(1, "line_id", "identifier-v1")
            if line_id in line_ids:
                raise ValueError("duplicate_line_id")
            line_ids.add(line_id)
            shipment_ref = cell(2, "shipment_ref", "identifier-v1")
            code = cell(3, "code", "charge-code-v1")
            stop_seq = cell(4, "stop_seq", "nonnegative-int-v1")
            if ((code in {"LH", "FS"} and stop_seq != 0)
                    or (code in {"DETENTION", "LIFTGATE"} and stop_seq <= 0)):
                raise ValueError("charge_stop_seq_mismatch")
            currency = cell(5, "currency", "identifier-v1")
            cents = cell(6, "billed_cents", "usd-cents-v1")
            invoice_lines.append({"line_id": line_id, "shipment_ref": shipment_ref,
                                  "code": code, "stop_seq": stop_seq, "currency": currency,
                                  "billed_cents": cents,
                                  "evidence_pointers": [fields[key]["pointer"]
                                                        for key in fields if key.startswith(path + ".")]})
        if sum(line["billed_cents"] for line in invoice_lines) != total:
            raise ValueError("invoice_total_mismatch")
        invoice = {"carrier": carrier, "invoice_id": invoice_id,
                   "invoice_issue_ts": issued, "currency": "USD",
                   "total_cents": total, "lines": invoice_lines,
                   "evidence_pointers": pointers.copy(), "source_sha256": source_hash,
                   "field_values": fields}
        verify_document(invoice, resolver)
        return {"status": "ok", "reason_code": "template_extracted",
                "fields": fields, "pointers": pointers, "invoice": invoice,
                "source_sha256": source_hash, "missing_facts": [], "resolver": resolver}
    except (ValueError, UnicodeError, OverflowError) as exc:
        return {"status": "refused", "reason_code": str(exc), "fields": fields,
                "pointers": pointers, "invoice": None, "source_sha256": source_hash,
                "missing_facts": [str(exc)], "resolver": resolver}
