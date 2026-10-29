"""Builder-owned provenance regressions; no independent labels or corpus.

what_bug_this_catches: an evidence pointer must prove the original source fact,
not merely resolve some text while mutable derived values or records drift.
"""

from copy import deepcopy
from hashlib import sha256
from pathlib import Path

import pytest

import freightrec.sources.registry as source_module
from freightrec.sources import SourceResolver, verify_document


def test_import_is_from_this_worktree():
    """what_bug_this_catches: a shared interpreter importing another lane's source."""
    expected = Path(__file__).resolve().parents[1] / "src" / "freightrec" / "sources" / "registry.py"
    assert Path(source_module.__file__).resolve() == expected


def test_unicode_codepoints_and_exact_crlf_bytes():
    """what_bug_this_catches: UTF-16/byte offsets or newline normalization drift."""
    resolver = SourceResolver()
    text = "A😀é\r\nB"
    raw = text.encode("utf-8")
    source = resolver.register_text(raw)
    pointer = resolver.pointer(source, 0, 1, 3)
    assert resolver.resolve(pointer) == "😀é"
    assert source == sha256(raw).hexdigest()
    assert resolver.resolve(resolver.pointer(source, 0, 3, 5)) == "\r\n"
    lf_source = resolver.register_text(text.replace("\r\n", "\n").encode("utf-8"))
    assert lf_source != source
    assert resolver.resolve(pointer) == "😀é"


@pytest.mark.parametrize("change", ["quote", "page", "bytes", "start", "bool_offset"])
def test_span_mutation_refuses(change):
    """what_bug_this_catches: changed bytes/page/span surviving a formerly valid pointer."""
    resolver = SourceResolver()
    source = resolver.register_text(b"original quote")
    pointer = resolver.pointer(source, 0, 0, 8).to_dict()
    if change == "quote":
        pointer["quote_sha256"] = "0" * 64
    elif change == "page":
        resolver._pages[(source, "native-text-v1")] = ("tampered quote",)
    elif change == "bytes":
        resolver._raw[source] = b"modified bytes"
    elif change == "start":
        pointer["start"] = 1
    else:
        pointer["start"] = False
    with pytest.raises(ValueError):
        resolver.resolve(pointer)


def test_native_edition_cannot_be_replaced_or_fabricated():
    """what_bug_this_catches: archived page replacement behind approved native hashes."""
    resolver = SourceResolver()
    resolver.register_text(b"original")
    with pytest.raises(ValueError, match="native_source_text_mismatch"):
        resolver.register_pages(b"original", ["invented"], "native-text-v1")
    resolver.register_pages(b"%PDF-builder", ["parser edition"], "builder-parser-v1")
    with pytest.raises(ValueError, match="parser_edition_changed"):
        resolver.register_pages(b"%PDF-builder", ["changed edition"], "builder-parser-v1")


def test_whole_original_registration_and_independent_typed_copy():
    """what_bug_this_catches: nested payload mutation also mutating its proof copy."""
    resolver = SourceResolver()
    raw = '{"id":"BUILDER-1","amount":100,"nested":{"known":true},"note":"😀"}'.encode("utf-8")
    document = resolver.register_document(raw)
    assert verify_document(document, resolver) == document["evidence_pointers"]
    assert resolver.resolve(document["evidence_pointers"][0]) == raw.decode("utf-8")
    document["nested"]["known"] = False
    with pytest.raises(ValueError, match="document_payload_mismatch"):
        verify_document(document, resolver)


@pytest.mark.parametrize("change", ["value", "bool_type", "typed_value", "quote", "missing_certificate", "normalizer", "extra_pointer"])
def test_whole_document_mutation_refuses(change):
    """what_bug_this_catches: arbitrary valid pointers standing in for bound typed facts."""
    resolver = SourceResolver()
    document = resolver.register_document(b'{"id":"BUILDER-1","amount":1}')
    field = document["field_values"]["$document"]
    if change == "value":
        document["amount"] = 2
    elif change == "bool_type":
        document["amount"] = True
    elif change == "typed_value":
        field["typed_value"]["amount"] = 2
    elif change == "quote":
        field["raw_quote"] = '{"id":"BUILDER-1","amount":2}'
    elif change == "missing_certificate":
        document.pop("field_values")
    elif change == "normalizer":
        field["normalizer_id"] = "string-v1"
    else:
        other = resolver.register_text(b"unrelated")
        document["evidence_pointers"].append(resolver.pointer(other, 0, 0, 9).to_dict())
    with pytest.raises(ValueError):
        verify_document(document, resolver)


@pytest.mark.parametrize("raw", [b'{"id":"a","id":"b"}', b'{"amount":1.0}', b'{"amount":NaN}', b'{"field_values":{}}'])
def test_whole_document_ambiguous_or_nonwire_source_refuses(raw):
    """what_bug_this_catches: duplicate keys, monetary floats or source metadata hidden by parsing."""
    with pytest.raises(ValueError):
        SourceResolver().register_document(raw)


def test_json_record_lexemes_are_structural_not_substring_matches():
    """what_bug_this_catches: equal values in different records collapsing to one span."""
    resolver = SourceResolver()
    raw = '[{"id":"A","note":"é\\n😀","amount":100},{"id":"B","note":"é\\n😀","amount":100}]'.encode("utf-8")
    first, second = resolver.register_json_records(raw, "id")
    for document in (first, second):
        assert verify_document(document, resolver)
        field = document["field_values"]["note"]
        assert field["typed_value"] == "é\n😀"
        assert resolver.resolve(field["pointer"]) == '"é\\n😀"'
    assert first["field_values"]["amount"]["pointer"]["start"] != second["field_values"]["amount"]["pointer"]["start"]
    assert first["field_values"]["amount"]["pointer"]["record_key"] == "A"


CSV_SCHEMA = {"id": "identifier-v1", "note": "string-v1", "amount": "usd-cents-v1"}


def test_csv_quoted_comma_escaped_quote_and_crlf_are_exact():
    """what_bug_this_catches: guessed CSV offsets or decoding that loses original quoting."""
    resolver = SourceResolver()
    raw = 'id,note,amount\r\nA,"café, ""quoted""\r\n😀",12.34\r\n'.encode("utf-8")
    document, = resolver.register_csv_records(raw, "id", CSV_SCHEMA)
    assert document["note"] == 'café, "quoted"\r\n😀'
    assert document["amount"] == 1234
    field = document["field_values"]["note"]
    assert resolver.resolve(field["pointer"]) == '"café, ""quoted""\r\n😀"'
    assert field["raw_quote"] == resolver.resolve(field["pointer"])
    assert verify_document(document, resolver)


@pytest.mark.parametrize("format_name", ["json", "csv"])
@pytest.mark.parametrize("change", ["key", "index", "field", "normalizer", "drop_field", "drop_record_metadata", "mix_record"])
def test_record_association_or_conversion_mutation_refuses(format_name, change):
    """what_bug_this_catches: valid equal quotes being reassigned to another field/record/schema."""
    resolver = SourceResolver()
    if format_name == "json":
        documents = resolver.register_json_records(b'[{"id":"A","note":"same","amount":100},{"id":"B","note":"same","amount":100}]', "id")
    else:
        documents = resolver.register_csv_records(b"id,note,amount\nA,same,1.00\nB,same,1.00\n", "id", CSV_SCHEMA)
    document = deepcopy(documents[0])
    field = document["field_values"]["amount"]
    if change == "key":
        field["pointer"]["record_key"] = "B"
    elif change == "index":
        field["pointer"]["record_index"] = 1
    elif change == "field":
        field["pointer"]["field"] = "note"
    elif change == "normalizer":
        field["normalizer_id"] = "string-v1"
        field["pointer"]["normalizer_id"] = "string-v1"
    elif change == "drop_field":
        document.pop("note")
        removed = document["field_values"].pop("note")["pointer"]
        document["evidence_pointers"].remove(removed)
    elif change == "drop_record_metadata":
        keep = {"source_sha256", "parser_profile", "page_text_sha256", "page_index", "start", "end", "quote_sha256"}
        field["pointer"] = {key: value for key, value in field["pointer"].items() if key in keep}
        field["method"] = "native-field-v1"
    else:
        document["field_values"]["amount"] = deepcopy(documents[1]["field_values"]["amount"])
        document["evidence_pointers"] = []
    with pytest.raises(ValueError):
        verify_document(document, resolver)


@pytest.mark.parametrize("raw", [b'[{"id":"A","amount":1,"amount":2}]', b'[{"id":"A"},{"id":"A"}]', b'[{"id":"A","amount":1.5}]', b'[{"id":"A","nested":{}}]'])
def test_json_records_ambiguous_or_unsupported_layout_refuses(raw):
    """what_bug_this_catches: duplicate keys/records, binary money or implicit nested flattening."""
    with pytest.raises(ValueError):
        SourceResolver().register_json_records(raw, "id")


@pytest.mark.parametrize("raw", [b"id,note,amount,amount\nA,x,1.00,1.00\n", b"id,note,amount\nA,x,1.00\nA,y,2.00\n", b"id,note,amount\nA,,1.00\n", b'id,note,amount\nA,"unterminated,1.00\n'])
def test_csv_ambiguous_records_and_alignment_refuse(raw):
    """what_bug_this_catches: duplicate headers/keys and permissive malformed CSV alignment."""
    with pytest.raises(ValueError):
        SourceResolver().register_csv_records(raw, "id", CSV_SCHEMA)


def test_csv_conversion_policy_gets_distinct_immutable_edition():
    """what_bug_this_catches: changed normalization reusing an older source edition/approval."""
    resolver = SourceResolver()
    raw = b"id,note,amount\nA,x,1.00\n"
    cents, = resolver.register_csv_records(raw, "id", CSV_SCHEMA)
    strings, = resolver.register_csv_records(raw, "id", {**CSV_SCHEMA, "amount": "string-v1"})
    assert cents["amount"] == 100
    assert strings["amount"] == "1.00"
    assert cents["source_sha256"] == strings["source_sha256"]
    assert cents["field_values"]["amount"]["pointer"]["parser_profile"] != strings["field_values"]["amount"]["pointer"]["parser_profile"]
    assert verify_document(cents, resolver)
    assert verify_document(strings, resolver)
