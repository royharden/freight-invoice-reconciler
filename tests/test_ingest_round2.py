"""Builder-owned ingestion regressions; these are not independent/gold data.

what_bug_this_catches: known-layout acceptance must preserve original evidence;
malformed facts and native PDF failure paths must never yield an invoice.
"""

from hashlib import md5
import struct

import pytest

from freightrec.ingest import extract
from freightrec.ingest import pdftext
from freightrec.sources import SourceResolver, verify_document


INVOICE = "\n".join([
    "FREIGHTREC INVOICE V1",
    "Carrier: BUILDER-CARRIER",
    "Invoice: BUILDER-INVOICE",
    "Issued: 2026-01-07T12:00:00+00:00",
    "Currency: USD",
    "Total: 123.45",
    "Lines:",
    "L1|SHIP-1|LINEHAUL|0|USD|100.00",
    "L2|SHIP-1|DETENTION|1|USD|23.45",
])


def _native(text=INVOICE, **overrides):
    return extract({"text": text, "media_type": "text/plain",
                    "template_id": "freightrec-invoice-v1", **overrides})


def _rc4(key, value):
    """Tiny original PDF R2 fixture writer only; not a product crypto API."""
    state = list(range(256))
    j = 0
    for i in range(256):
        j = (j + state[i] + key[i % len(key)]) % 256
        state[i], state[j] = state[j], state[i]
    i = j = 0
    out = bytearray()
    for byte in value:
        i = (i + 1) % 256
        j = (j + state[i]) % 256
        state[i], state[j] = state[j], state[i]
        out.append(byte ^ state[(state[i] + state[j]) % 256])
    return bytes(out)


def _pdf(page_texts, *, encrypted=False):
    """Create original small PDFs, including a raster-only page and empty-password R2.

    No downloaded PDFs, document library, accounts or secret material is used.
    Empty PDF passwords exercise encryption refusal, not real credential access.
    """
    padding = bytes.fromhex(
        "28bf4e5e4e758a4164004e56fffa01082e2e00b6d0683e802f0ca9fe6453697a")
    file_id = md5(b"freightrec-builder-original-pdf").digest()
    owner = _rc4(md5(padding).digest()[:5], padding)
    file_key = md5(padding + owner + struct.pack("<i", -4) + file_id).digest()[:5]
    user = _rc4(file_key, padding)

    def stream(number, content, attributes=b""):
        if encrypted:
            key = md5(file_key + number.to_bytes(3, "little") + b"\0\0").digest()[:10]
            content = _rc4(key, content)
        return (b"<< /Length " + str(len(content)).encode() + attributes
                + b" >>\nstream\n" + content + b"\nendstream")

    page_ids = [5 + 2 * index for index in range(len(page_texts))]
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        (b"<< /Type /Pages /Count " + str(len(page_texts)).encode()
         + b" /Kids [" + b" ".join(f"{n} 0 R".encode() for n in page_ids) + b"] >>"),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        stream(4, b"\x00", b" /Type /XObject /Subtype /Image /Width 1 /Height 1"
               b" /ColorSpace /DeviceGray /BitsPerComponent 8"),
    ]
    for number, text in zip(page_ids, page_texts):
        if text is None:
            content = b"q 10 0 0 10 40 40 cm /Im1 Do Q"
        else:
            commands = [b"BT /F1 10 Tf 40 760 Td 12 TL"]
            for line in text.splitlines():
                escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
                commands.append(b"(" + escaped.encode("ascii") + b") Tj T*")
            commands.append(b"ET")
            content = b"\n".join(commands)
        objects.extend([
            (b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792]"
             b" /Resources << /Font << /F1 3 0 R >> /XObject << /Im1 4 0 R >> >>"
             b" /Contents " + str(number + 1).encode() + b" 0 R >>"),
            stream(number + 1, content),
        ])
    encryption_id = None
    if encrypted:
        encryption_id = len(objects) + 1
        objects.append(b"<< /Filter /Standard /V 1 /R 2 /Length 40 /O <"
                       + owner.hex().encode() + b"> /U <" + user.hex().encode()
                       + b"> /P -4 >>")
    output = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
    offsets = [0]
    for number, value in enumerate(objects, 1):
        offsets.append(len(output))
        output.extend(f"{number} 0 obj\n".encode() + value + b"\nendobj\n")
    xref = len(output)
    output.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        output.extend(f"{offset:010d} 00000 n \n".encode())
    trailer = f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R".encode()
    if encryption_id:
        trailer += (f" /Encrypt {encryption_id} 0 R /ID [<".encode()
                    + file_id.hex().encode() + b"><" + file_id.hex().encode() + b">]")
    output.extend(trailer + f" >>\nstartxref\n{xref}\n%%EOF\n".encode())
    return bytes(output)


@pytest.mark.parametrize("newline", ["\n", "\r\n"])
def test_native_template_values_remain_bound_to_exact_original(newline):
    """what_bug_this_catches: newline or alias normalization must not move quotes."""
    raw = INVOICE.replace("\n", newline).encode("utf-8")
    result = _native(raw_bytes=raw)
    assert result["status"] == "ok"
    invoice = result["invoice"]
    assert invoice["total_cents"] == 12345
    assert [line["code"] for line in invoice["lines"]] == ["LH", "DETENTION"]
    resolver = result["resolver"]
    assert verify_document(invoice, resolver)
    for field in result["fields"].values():
        assert resolver.resolve(field["pointer"]) == field["raw_quote"]


@pytest.mark.parametrize("text", [
    INVOICE.replace("Total: 123.45", "Total: 123.46"),
    INVOICE.replace("Currency: USD", "Currency: EUR"),
    INVOICE.replace("|USD|23.45", "|EUR|23.45"),
    INVOICE.replace("12:00:00+00:00", "12:00:00"),
    INVOICE.replace("2026-01-07", "2026-02-30"),
    INVOICE.replace("FREIGHTREC INVOICE V1", "OTHER LAYOUT"),
    INVOICE.replace("|LINEHAUL|", "|UNKNOWN|"),
    INVOICE.replace("LINEHAUL|0", "LINEHAUL|1"),
    INVOICE.replace("DETENTION|1", "DETENTION|0"),
    INVOICE.replace("L2|SHIP", "L1|SHIP"),
    INVOICE.replace("|100.00", "|100.001"),
    INVOICE.replace("|100.00", "|-100.00"),
])
def test_invalid_template_facts_do_not_yield_partial_invoice(text):
    """what_bug_this_catches: partial field success must never become accepted input."""
    result = _native(text)
    assert result["status"] == "refused"
    assert result["invoice"] is None
    assert result["missing_facts"]


def test_source_layout_and_size_are_explicit():
    """what_bug_this_catches: caller format hints cannot bypass source bounds/layout."""
    assert _native(template_id="unseen-layout")["reason_code"] == "unknown_layout"
    assert _native(resolver=SourceResolver(max_bytes=32))["reason_code"] == "source_byte_limit"
    header = INVOICE.split("Lines:\n")[0] + "Lines:\n"
    too_many = header + "\n".join(f"L{i}|SHIP-1|LH|0|USD|1.00" for i in range(1001))
    assert _native(too_many)["reason_code"] == "invoice_line_limit"


def test_pdf_native_text_adapter_extracts_real_builder_pdf():
    """what_bug_this_catches: optional-parser wiring must parse actual native text."""
    pytest.importorskip("pdfplumber", reason="authorized pdfplumber dependency unavailable")
    raw = _pdf([INVOICE])
    pages, profile = pdftext.extract_pdf_pages(raw)
    assert profile.startswith("pdfplumber-")
    assert pages == [INVOICE]
    result = extract({"raw_bytes": raw, "media_type": "application/pdf",
                      "template_id": "freightrec-invoice-v1"})
    assert result["status"] == "ok"
    assert result["invoice"]["total_cents"] == 12345
    assert verify_document(result["invoice"], result["resolver"])


@pytest.mark.parametrize(("raw", "reason"), [
    (_pdf([None]), "pdf_native_text_required"),
    (_pdf([INVOICE, INVOICE]), "unsupported_multipage_pdf"),
    (_pdf([INVOICE], encrypted=True), "encrypted_pdf_refused"),
    (b"%PDF-1.4\nmalformed-builder-document", "malformed_pdf"),
])
def test_pdf_refuses_original_raster_multipage_encrypted_and_malformed(raw, reason):
    """what_bug_this_catches: unsupported PDFs must refuse through the real parser."""
    pytest.importorskip("pdfplumber", reason="authorized pdfplumber dependency unavailable")
    with pytest.raises(ValueError, match=f"^{reason}$"):
        pdftext.extract_pdf_pages(raw)


def test_pdf_enforces_size_text_and_cooperative_elapsed_limits(monkeypatch):
    """what_bug_this_catches: adapter limits must be enforced, not merely documented."""
    raw = _pdf([INVOICE])
    with pytest.raises(ValueError, match="^source_byte_limit$"):
        pdftext.extract_pdf_pages(raw, max_bytes=32)
    with pytest.raises(ValueError, match="^invalid_pdf_header$"):
        pdftext.extract_pdf_pages(b"not-a-pdf")
    pytest.importorskip("pdfplumber", reason="authorized pdfplumber dependency unavailable")
    with pytest.raises(ValueError, match="^page_text_limit$"):
        pdftext.extract_pdf_pages(raw, max_codepoints=10)
    clock = iter([0, 6])
    monkeypatch.setattr(pdftext, "monotonic", lambda: next(clock))
    with pytest.raises(ValueError, match="^pdf_elapsed_limit$"):
        pdftext.extract_pdf_pages(raw, max_seconds=5)
