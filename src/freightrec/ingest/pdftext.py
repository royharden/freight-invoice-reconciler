"""Optional pdfplumber source adapter; runtime compatibility is unverified.

No OCR, rendering, scripts or network. Elapsed checks are cooperative: they do
not interrupt a parser blocked inside open/page discovery/text extraction.
"""

from io import BytesIO
from time import monotonic


class _PdfRefusal(ValueError):
    """Distinguish bounded adapter reasons from arbitrary parser exceptions."""


def extract_pdf_pages(raw_bytes: bytes, *, max_bytes: int = 8_000_000,
                      max_pages: int = 100, max_codepoints: int = 500_000,
                      max_seconds: int = 5) -> tuple[list[str], str]:
    if any(type(limit) is not int or limit <= 0
           for limit in (max_bytes, max_pages, max_codepoints, max_seconds)):
        raise ValueError("invalid_pdf_limits")
    if not isinstance(raw_bytes, bytes) or not 0 < len(raw_bytes) <= max_bytes:
        raise ValueError("source_byte_limit")
    if not raw_bytes.startswith(b"%PDF-"):
        raise ValueError("invalid_pdf_header")
    # Source only: no dependency is installed or qualified by this adapter.
    try:
        import pdfplumber
    except Exception as exc:
        raise ValueError("pdf_adapter_unavailable") from exc
    started = monotonic()
    try:
        version = getattr(pdfplumber, "__version__", None)
        if (type(version) is not str or not 0 < len(version) <= 60
                or any(char not in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.+-_"
                       for char in version)):
            raise _PdfRefusal("pdf_parser_version_unavailable")
        with pdfplumber.open(BytesIO(raw_bytes)) as document:
            if monotonic() - started > max_seconds:
                raise _PdfRefusal("pdf_elapsed_limit")
            # pdfplumber exposes the underlying PDFMiner document. Fail closed
            # if that compatibility seam does not expose encryption state.
            pdf_document = getattr(document, "doc", None)
            if pdf_document is None or not hasattr(pdf_document, "encryption"):
                raise _PdfRefusal("pdf_encryption_state_unavailable")
            if pdf_document.encryption is not None:
                raise _PdfRefusal("encrypted_pdf_refused")
            page_count = len(document.pages)
            if not 0 < page_count <= max_pages:
                raise _PdfRefusal("page_limit")
            # The invoice grammar has no continuation-page layout. Refuse it
            # here before extracting any unsupported page's text.
            if page_count != 1:
                raise _PdfRefusal("unsupported_multipage_pdf")
            if monotonic() - started > max_seconds:
                raise _PdfRefusal("pdf_elapsed_limit")
            text = document.pages[0].extract_text()
            if monotonic() - started > max_seconds:
                raise _PdfRefusal("pdf_elapsed_limit")
            if not isinstance(text, str) or not text.strip():
                raise _PdfRefusal("pdf_native_text_required")
            if len(text) > min(max_codepoints, 200_000):
                raise _PdfRefusal("page_text_limit")
        if monotonic() - started > max_seconds:
            raise _PdfRefusal("pdf_elapsed_limit")
        return [text], f"pdfplumber-{version}-plain-v1"
    except _PdfRefusal as exc:
        raise ValueError(str(exc)) from exc
    except Exception as exc:
        raise ValueError("malformed_pdf") from exc
