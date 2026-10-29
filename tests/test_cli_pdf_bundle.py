"""Original builder PDF input controls, not independent/reference data."""

import base64
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest

from freightrec import bundles, cli
from freightrec.review.log import DecisionLog
from freightrec.sources import verify_document
from scripts.make_builder_pdf import original_pdf, TEXT


ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def pdf_bundle():
    return json.loads((ROOT / "fixtures/builder/native-pdf-bundle.json").read_text(encoding="utf-8"))


def save(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def invoke(tmp_path, value, name, state=None):
    source = save(tmp_path / (name + "-input.json"), value)
    output = tmp_path / (name + "-findings.json")
    args = ["reconcile", "--builder-only", "--input", str(source), "--out", str(output)]
    if state is not None:
        args += ["--state", str(state)]
    return cli.main(args), output


def test_original_pdf_to_findings_resolves_raw_sha_and_exact_quotes(tmp_path, pdf_bundle):
    """what_bug_this_catches: derived invoice JSON must never replace original PDF proof."""
    raw = (ROOT / "fixtures/builder/native-invoice-v1.pdf").read_bytes()
    assert bundles.decode_pdf_descriptor(pdf_bundle["invoices"][0]) == raw
    resolver, documents = cli._hydrate(pdf_bundle)
    invoice = documents["invoices"][0]
    digest = sha256(raw).hexdigest()
    assert invoice["source_sha256"] == digest
    assert verify_document(invoice, resolver)
    for field in invoice["field_values"].values():
        pointer = field["pointer"]
        assert pointer["source_sha256"] == digest
        assert pointer["parser_profile"].endswith("-isolated-v2")
        assert pointer["page_index"] == 0
        assert resolver.resolve(pointer) == field["raw_quote"]
    amount = invoice["field_values"]["lines.0.billed_cents"]
    assert amount["typed_value"] == 140000 and amount["raw_quote"] == "1400.00"
    code, output = invoke(tmp_path, pdf_bundle, "native")
    assert code == 0
    findings = json.loads(output.read_text(encoding="utf-8"))["findings"]
    assert len(findings) == 3 and all(not row["missing_facts"] for row in findings)
    for row in findings:
        pdf_pointers = [p for p in row["evidence_pointers"] if p["source_sha256"] == digest]
        assert pdf_pointers
        assert all(resolver.resolve(pointer) for pointer in pdf_pointers)


@pytest.mark.parametrize("damage", [
    "missing", "extra", "caller_proof", "media", "template", "bytes", "empty",
    "whitespace", "alphabet", "unicode", "padding_bits", "padding_missing", "padding_extra",
])
def test_strict_pdf_descriptor_refuses_before_parser(pdf_bundle, monkeypatch, damage):
    """what_bug_this_catches: descriptor smuggling and noncanonical bytes cannot reach parsing."""
    value = deepcopy(pdf_bundle)
    descriptor = value["invoices"][0]
    if damage == "missing":
        descriptor.pop("template_id")
    elif damage == "extra":
        descriptor["path"] = "caller-selected-hook"
    elif damage == "caller_proof":
        descriptor["field_values"] = {"verified": True}
    elif damage == "media":
        descriptor["media_type"] = "text/plain"
    elif damage == "template":
        descriptor["template_id"] = "unrecognized"
    else:
        descriptor["data_base64"] = {
            "bytes": b"JVBERg==", "empty": "", "whitespace": "Zg==\n",
            "alphabet": "@@@@", "unicode": "\u03bb\u03bb==", "padding_bits": "Zh==",
            "padding_missing": "Zg", "padding_extra": "Zg===",
        }[damage]
    import freightrec.ingest
    monkeypatch.setattr(freightrec.ingest, "extract", lambda *_: pytest.fail("invalid descriptor parsed"))
    with pytest.raises(ValueError):
        cli._hydrate(value)


@pytest.mark.parametrize("limit", ["encoded", "decoded"])
def test_real_eight_megabyte_bounds_refuse_before_decode(pdf_bundle, monkeypatch, limit):
    """what_bug_this_catches: size checks must precede allocation/parsing, with real limits."""
    value = deepcopy(pdf_bundle["invoices"][0])
    # Exactly the largest encoded length but no padding represents 8,000,001
    # decoded bytes. No max limit or worker timeout is patched for this test.
    value["data_base64"] = "A" * (bundles.MAX_PDF_BASE64 + (4 if limit == "encoded" else 0))
    monkeypatch.setattr(bundles.base64, "b64decode", lambda *_args, **_kw: pytest.fail("oversize decoded"))
    with pytest.raises(ValueError, match="size"):
        bundles.decode_pdf_descriptor(value)


@pytest.mark.parametrize("collection", ["contracts", "shipments", "fuel_index"])
def test_pdf_descriptor_is_invoice_only(pdf_bundle, collection):
    """what_bug_this_catches: rates/facts cannot gain a new unreviewed PDF input path."""
    value = deepcopy(pdf_bundle)
    value[collection] = [value["invoices"][0]]
    with pytest.raises(ValueError):
        cli._hydrate(value)


@pytest.mark.parametrize("damage", ["base64", "header", "layout"])
def test_pdf_hydration_refusal_retires_exact_contexts(tmp_path, pdf_bundle, damage):
    """what_bug_this_catches: failed PDF hydration cannot revive old link context revisions."""
    state = tmp_path / "pdf-state.sqlite"
    code, first = invoke(tmp_path, pdf_bundle, "initial", state)
    assert code == 0
    context = json.loads(first.read_text(encoding="utf-8"))["findings"][0]["link_context"]
    log = DecisionLog(state)
    before = log.register_link_context(context)
    bad = deepcopy(pdf_bundle)
    if damage == "base64":
        bad["invoices"][0]["data_base64"] = "not-base64"
    else:
        raw = b"not a PDF" if damage == "header" else original_pdf(TEXT.replace("INVOICE V1", "INVOICE V9"))
        bad["invoices"][0]["data_base64"] = base64.b64encode(raw).decode("ascii")
    code, output = invoke(tmp_path, bad, "invalid", state)
    assert code == 2 and not output.exists()
    code, _ = invoke(tmp_path, pdf_bundle, "restored", state)
    assert code == 0
    after = log.register_link_context(context)
    assert after["context_revision"] > before["context_revision"]


def test_changed_original_pdf_does_not_resolve_old_pointer(pdf_bundle):
    """what_bug_this_catches: an unchanged quote in new raw bytes is still a different source."""
    old_resolver, old_docs = cli._hydrate(pdf_bundle)
    old_pointer = old_docs["invoices"][0]["evidence_pointers"][0]
    value = deepcopy(pdf_bundle)
    value["invoices"][0]["data_base64"] = base64.b64encode(
        original_pdf(TEXT.replace("12:00:00", "12:01:00"))).decode("ascii")
    new_resolver, new_docs = cli._hydrate(value)
    assert new_docs["invoices"][0]["source_sha256"] != old_docs["invoices"][0]["source_sha256"]
    assert old_resolver.resolve(old_pointer)
    with pytest.raises(ValueError):
        new_resolver.resolve(old_pointer)


def test_old_json_bundle_compatibility_and_stateless_pdf_refusal(tmp_path, pdf_bundle):
    """what_bug_this_catches: adding PDF must preserve JSON while refusing stateless bad inputs."""
    old = json.loads((ROOT / "fixtures/builder/simple-shipment.json").read_text(encoding="utf-8"))
    resolver, documents = cli._hydrate(old)
    assert all(verify_document(doc, resolver) for values in documents.values() for doc in values)
    bad = deepcopy(pdf_bundle)
    bad["invoices"] = [7]
    code, output = invoke(tmp_path, bad, "stateless")
    assert code == 2 and not output.exists() and not list(tmp_path.glob("*.sqlite"))
