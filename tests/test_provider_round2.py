"""Builder-owned port regressions; no live provider or quality evaluation."""

from copy import deepcopy
import builtins
import os
import socket

import pytest

from freightrec.providers.base import Limits, live_disabled
from freightrec.providers.contract_anthropic import extract as anthropic_extract
from freightrec.providers.contract_openai_compatible import extract as openai_extract
from freightrec.providers.mock import MockExtractionPort
from freightrec.sources import SourceResolver
from freightrec.sources.normalize import normalize


def candidate_case():
    resolver = SourceResolver()
    sha = resolver.register_text(b"125.00")
    candidate = {
        "candidate_id": "builder-amount-1", "carrier": "BUILDER-CARRIER",
        "field": "billed_cents", "typed_value": 12500,
        "raw_quote": "125.00", "normalizer_id": "usd-cents-v1",
        "pointer": resolver.pointer(sha, 0, 0, 6).to_dict(),
    }
    document = {"carrier": "BUILDER-CARRIER", "link_status": "unique_exact",
                "text": "125.00", "candidates": [candidate]}
    schema = {"fields": {"billed_cents": "integer"}, "required": ["billed_cents"]}

    def verify(item):
        quote = resolver.resolve(item["pointer"])
        typed = normalize(quote, item["normalizer_id"])
        return quote == item["raw_quote"] and type(typed) is type(item["typed_value"]) and typed == item["typed_value"]

    return document, schema, verify


def test_mock_selects_original_verified_quote_and_typed_value():
    """what_bug_this_catches: supplied values must not replace verified code candidates."""
    document, schema, verify = candidate_case()
    result = MockExtractionPort({"billed_cents": "builder-amount-1"}, verify).extract(
        document, schema, "builder-request", Limits())
    assert result.status == "ok"
    assert result.fields == {"billed_cents": 12500}
    assert result.pointers["billed_cents"] == document["candidates"][0]["pointer"]
    assert result.origin == "mock" and result.usage is None


@pytest.mark.parametrize("mutation", ["typed", "quote", "pointer", "normalizer"])
def test_mock_refuses_source_or_normalization_mutation(mutation):
    """what_bug_this_catches: a valid-looking pointer cannot prove an altered amount."""
    document, schema, verify = candidate_case()
    candidate = document["candidates"][0]
    if mutation == "typed":
        candidate["typed_value"] = 99999
    elif mutation == "quote":
        candidate["raw_quote"] = "999.99"
    elif mutation == "pointer":
        candidate["pointer"]["quote_sha256"] = "0" * 64
    else:
        candidate["normalizer_id"] = "unsupported-builder-normalizer"
    candidate["verified"] = True  # A data flag must not override code verification.
    result = MockExtractionPort({"billed_cents": "builder-amount-1"}, verify).extract(
        document, schema, "builder-request", Limits())
    assert result.status == "abstained" and result.fields == {} and result.pointers == {}


@pytest.mark.parametrize("case", ["other_carrier", "unresolved", "bool_integer", "duplicate_id",
                                  "unknown_selection", "missing_required", "invalid_schema", "unhashable_id"])
def test_mock_refuses_ambiguous_or_malformed_selection(case):
    """what_bug_this_catches: malformed/cross-carrier selection must abstain, not escape or fill fields."""
    document, schema, verify = candidate_case()
    selections = {"billed_cents": "builder-amount-1"}
    if case == "other_carrier":
        document["candidates"][0]["carrier"] = "OTHER-BUILDER"
    elif case == "unresolved":
        document["link_status"] = "similar"
    elif case == "bool_integer":
        document["candidates"][0]["typed_value"] = True
    elif case == "duplicate_id":
        document["candidates"].append(deepcopy(document["candidates"][0]))
    elif case == "unknown_selection":
        selections["billed_cents"] = "not-generated"
    elif case == "missing_required":
        selections = {}
    elif case == "invalid_schema":
        schema["fields"]["billed_cents"] = ["integer"]
    else:
        document["candidates"][0]["candidate_id"] = []
    result = MockExtractionPort(selections, verify).extract(document, schema, "builder-request", Limits())
    assert result.status == "abstained" and result.fields == {} and result.errors


@pytest.mark.parametrize("document,schema,selections", [(None, {}, {}), ({}, None, {}), ({}, {}, []),
                                                      ({"text": []}, {}, {"x": []})])
def test_mock_bad_outer_shapes_are_structured_abstentions(document, schema, selections):
    """what_bug_this_catches: unsafe .get/hash lookup errors formerly escaped on malformed shapes."""
    result = MockExtractionPort(selections, lambda _: True).extract(document, schema, "builder-request", Limits())
    assert result.status == "abstained" and result.fields == {}


@pytest.mark.parametrize("limits", [Limits(max_candidates=1), Limits(max_fields=1), Limits(max_slice_characters=1)])
def test_mock_limits_refuse_before_partial_fields(limits):
    """what_bug_this_catches: bounded extraction cannot return a partial success after exceeding limits."""
    document, schema, verify = candidate_case()
    if limits.max_candidates == 1:
        extra = deepcopy(document["candidates"][0])
        extra["candidate_id"] = "builder-extra"
        document["candidates"].append(extra)
    selections = {"billed_cents": "builder-amount-1"}
    if limits.max_fields == 1:
        selections["other"] = "builder-extra"
    result = MockExtractionPort(selections, verify).extract(document, schema, "builder-request", limits)
    assert result.status == "abstained" and result.fields == {}


def test_live_contracts_refuse_before_environment_import_or_socket_access(monkeypatch):
    """what_bug_this_catches: a live flag must not probe credentials, SDKs or networking before refusal."""
    def forbidden(*args, **kwargs):
        raise AssertionError("live effect attempted")

    class ForbiddenEnvironment:
        __getitem__ = get = __contains__ = __iter__ = forbidden

    original_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name.split(".")[0] in {"openai", "anthropic", "httpx", "requests", "urllib", "socket"}:
            forbidden()
        return original_import(name, *args, **kwargs)

    with monkeypatch.context() as guard:
        guard.setattr(os, "environ", ForbiddenEnvironment())
        guard.setattr(os, "getenv", forbidden)
        guard.setattr(socket, "socket", forbidden)
        guard.setattr(builtins, "__import__", guarded_import)
        results = [live_disabled(), anthropic_extract(live=True), openai_extract(live=True)]
    assert all(result.status == "live_not_enabled" and result.origin == "disabled" for result in results)
