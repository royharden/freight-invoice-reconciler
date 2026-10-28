"""Dedicated PDF worker: bounded data input, required own-process limits, no effects API."""

import base64
from io import BytesIO
import json
from pathlib import Path
import sys

# -I deliberately ignores editable installs and caller PYTHONPATH. Import only
# the trusted private helper adjacent to this exact checked-out worker script.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _pdf_limits import ResourceGuardError, establish_limits

MAX_REQUEST_BYTES = 10_670_000
MEMORY_BYTES = 512 * 1024 * 1024


class Refusal(Exception):
    pass


def parse_request(raw: bytes) -> tuple[bytes, dict]:
    def pairs(items):
        value = {}
        for key, item in items:
            if key in value:
                raise ValueError
            value[key] = item
        return value

    def reject_number(_):
        raise ValueError

    try:
        request = json.loads(raw.decode("ascii"), object_pairs_hook=pairs,
                             parse_float=reject_number, parse_constant=reject_number)
        keys = {"raw_pdf_b64", "max_bytes", "max_pages", "max_codepoints", "max_seconds"}
        if type(request) is not dict or set(request) != keys:
            raise ValueError
        for key, maximum in (("max_bytes", 8_000_000), ("max_pages", 100),
                             ("max_codepoints", 500_000), ("max_seconds", 30)):
            if type(request[key]) is not int or not 0 < request[key] <= maximum:
                raise ValueError
        if type(request["raw_pdf_b64"]) is not str:
            raise ValueError
        pdf = base64.b64decode(request["raw_pdf_b64"], validate=True)
        if not 0 < len(pdf) <= request["max_bytes"] or not pdf.startswith(b"%PDF-"):
            raise ValueError
        return pdf, request
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError) as exc:
        raise Refusal("pdf_worker_request_invalid") from exc


def parse_pdf(pdf: bytes, request: dict, guard: dict) -> dict:
    try:
        import pdfplumber
    except Exception as exc:
        raise Refusal("pdf_adapter_unavailable") from exc
    try:
        version = getattr(pdfplumber, "__version__", None)
        if (type(version) is not str or not 0 < len(version) <= 60
                or any(character not in "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.+-_"
                       for character in version)):
            raise Refusal("pdf_parser_version_unavailable")
        with pdfplumber.open(BytesIO(pdf)) as document:
            underlying = getattr(document, "doc", None)
            if underlying is None or not hasattr(underlying, "encryption"):
                raise Refusal("pdf_encryption_state_unavailable")
            if underlying.encryption is not None:
                raise Refusal("encrypted_pdf_refused")
            count = len(document.pages)
            if not 0 < count <= request["max_pages"]:
                raise Refusal("page_limit")
            if count != 1:
                raise Refusal("unsupported_multipage_pdf")
            text = document.pages[0].extract_text()
            if type(text) is not str or not text.strip():
                raise Refusal("pdf_native_text_required")
            if len(text) > min(request["max_codepoints"], 200_000):
                raise Refusal("page_text_limit")
        return {"status": "ok", "pages": [text],
                "parser_profile": f"pdfplumber-{version}-isolated-v2", "guard": guard}
    except Refusal:
        raise
    except MemoryError as exc:
        raise Refusal("pdf_resource_limit") from exc
    except Exception as exc:
        raise Refusal("malformed_pdf") from exc


def main() -> None:
    try:
        raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
        if not raw or len(raw) > MAX_REQUEST_BYTES:
            raise Refusal("pdf_worker_request_invalid")
        pdf, request = parse_request(raw)
        try:
            guard = establish_limits(MEMORY_BYTES, request["max_seconds"] + 1)
        except ResourceGuardError as exc:
            raise Refusal("pdf_guard_unavailable") from exc
        result = parse_pdf(pdf, request, guard)
    except Refusal as exc:
        result = {"status": "refused", "reason_code": str(exc)}
    except MemoryError:
        result = {"status": "refused", "reason_code": "pdf_resource_limit"}
    except Exception:
        result = {"status": "refused", "reason_code": "pdf_worker_request_invalid"}
    encoded = json.dumps(result, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    if len(encoded) > 1_204_096:
        encoded = b'{"status":"refused","reason_code":"page_text_limit"}'
    sys.stdout.buffer.write(encoded)
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    main()
