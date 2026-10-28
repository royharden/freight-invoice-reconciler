"""Original bundle codec. PDF facts come only from the guarded ingest adapter."""

import base64
import binascii
from hashlib import sha256

from .sources import SourceResolver, verify_document


MAX_PDF_BYTES = 8_000_000
MAX_PDF_BASE64 = ((MAX_PDF_BYTES + 2) // 3) * 4
PDF_DESCRIPTOR_KEYS = {"media_type", "template_id", "data_base64"}


def decode_pdf_descriptor(value):
    """Return exact original bytes after strict, bounded canonical-base64 checks."""
    if type(value) is not dict or set(value) != PDF_DESCRIPTOR_KEYS:
        raise ValueError("pdf_descriptor_exact_fields_required")
    if value["media_type"] != "application/pdf" or value["template_id"] != "freightrec-invoice-v1":
        raise ValueError("pdf_descriptor_media_or_template_invalid")
    encoded = value["data_base64"]
    if type(encoded) is not str or not 0 < len(encoded) <= MAX_PDF_BASE64:
        raise ValueError("pdf_descriptor_encoded_size_or_type_invalid")
    if len(encoded) % 4:
        raise ValueError("pdf_descriptor_base64_noncanonical")
    padding = len(encoded) - len(encoded.rstrip("="))
    if padding > 2 or (len(encoded) // 4) * 3 - padding > MAX_PDF_BYTES:
        raise ValueError("pdf_descriptor_decoded_size_invalid")
    try:
        raw = base64.b64decode(encoded.encode("ascii"), validate=True)
    except (UnicodeError, binascii.Error, ValueError) as exc:
        raise ValueError("pdf_descriptor_base64_invalid") from exc
    if not 0 < len(raw) <= MAX_PDF_BYTES:
        raise ValueError("pdf_descriptor_decoded_size_invalid")
    if base64.b64encode(raw).decode("ascii") != encoded:
        raise ValueError("pdf_descriptor_base64_noncanonical")
    return raw


def hydrate_original_bundle(bundle):
    """Retain one resolver for original JSON and guarded original PDF invoices.

    This codec supplies no admission or human authority. The CLI separately
    enforces its builder-only gate and 20MB outer-file limit before hydration.
    """
    names = ("contracts", "shipments", "invoices", "fuel_index")
    if type(bundle) is not dict or set(bundle) - {"data_origin", "tolerance_cents", *names}:
        raise ValueError("unsupported construction bundle fields")
    if any(type(bundle.get(name)) is not list for name in names):
        raise ValueError("original source collections must be lists")
    resolver = SourceResolver()
    documents = {}
    for name in names:
        documents[name] = []
        for original in bundle[name]:
            if type(original) is str:
                document = resolver.register_document(original.encode("utf-8"))
            elif name == "invoices" and type(original) is dict:
                raw = decode_pdf_descriptor(original)
                # The fixed adapter owns worker isolation, 5s default, resource
                # guards and parser profile. No caller limits/path/hook exists.
                from .ingest import extract
                result = extract({"raw_bytes": raw, "media_type": "application/pdf",
                                  "template_id": "freightrec-invoice-v1", "resolver": resolver})
                if result.get("status") != "ok" or type(result.get("invoice")) is not dict:
                    raise ValueError("pdf_ingest_refused:" + str(result.get("reason_code", "unknown")))
                document = result["invoice"]
                digest = sha256(raw).hexdigest()
                if (result.get("resolver") is not resolver or result.get("source_sha256") != digest
                        or document.get("source_sha256") != digest):
                    raise ValueError("pdf_original_binding_invalid")
                verify_document(document, resolver)
            else:
                raise ValueError(f"{name}: original JSON string or invoice PDF descriptor required")
            documents[name].append(document)
    return resolver, documents
