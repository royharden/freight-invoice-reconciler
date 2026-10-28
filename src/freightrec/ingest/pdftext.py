"""Bounded PDF text adapter source. No OCR, rendering, scripts or network."""

from io import BytesIO
from time import monotonic


def extract_pdf_pages(raw_bytes: bytes, *, max_bytes: int = 8_000_000,
                      max_pages: int = 100, max_codepoints: int = 500_000,
                      max_seconds: int = 5) -> tuple[list[str], str]:
    if not isinstance(raw_bytes, bytes) or not 0 < len(raw_bytes) <= max_bytes:
        raise ValueError("source_byte_limit")
    if not raw_bytes.startswith(b"%PDF-"):
        raise ValueError("invalid_pdf_header")
    # Optional adapter: installing/qualifying pypdf is a later activation step.
    try:
        from pypdf import PdfReader
        from pypdf import __version__
    except ImportError as exc:
        raise ValueError("pdf_adapter_unavailable") from exc
    started = monotonic()
    try:
        reader = PdfReader(BytesIO(raw_bytes), strict=True)
        if reader.is_encrypted:
            raise ValueError("encrypted_pdf_refused")
        if not 0 < len(reader.pages) <= max_pages:
            raise ValueError("page_limit")
        pages = []
        total = 0
        for page in reader.pages:
            if monotonic() - started > max_seconds:
                raise ValueError("pdf_elapsed_limit")
            text = page.extract_text()
            if not isinstance(text, str) or not text.strip():
                raise ValueError("pdf_native_text_required")
            total += len(text)
            if total > max_codepoints or len(text) > 200_000:
                raise ValueError("page_text_limit")
            pages.append(text)
        if monotonic() - started > max_seconds:
            raise ValueError("pdf_elapsed_limit")
        return pages, f"pypdf-{__version__}-plain-v1"
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("malformed_pdf") from exc
