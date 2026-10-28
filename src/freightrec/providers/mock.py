"""Select only preverified candidates from one carrier's source slice."""

from collections.abc import Callable

from .base import ExtractionResult, Limits


class MockExtractionPort:
    def __init__(self, selections: dict[str, str], verify_candidate: Callable[[dict], bool]):
        # Verifier is CODE supplied by caller: it must resolve original pointer,
        # quote hash and typed-value normalization, never trust a candidate flag.
        # Preserve malformed input for a structured abstention in extract.
        self.selections = dict(selections) if isinstance(selections, dict) else selections
        self.verify_candidate = verify_candidate

    def extract(self, document_slice: dict, schema: dict, request_id: str,
                limits: Limits) -> ExtractionResult:
        def refused(reason: str) -> ExtractionResult:
            return ExtractionResult(errors=(reason,))

        if not isinstance(request_id, str) or not request_id.strip():
            return refused("missing request_id")
        if not isinstance(document_slice, dict) or not isinstance(schema, dict):
            return refused("invalid document slice/schema")
        if not isinstance(self.selections, dict):
            return refused("invalid selections")
        if not isinstance(limits, Limits) or not callable(self.verify_candidate):
            return refused("invalid limits/verifier")
        carrier = document_slice.get("carrier")
        candidates = document_slice.get("candidates")
        allowed = schema.get("fields")
        required = schema.get("required", [])
        if (not isinstance(carrier, str) or not carrier.strip() or
                document_slice.get("link_status") != "unique_exact"):
            return refused("carrier or exact linkage unresolved")
        if not isinstance(candidates, list) or not isinstance(allowed, dict):
            return refused("invalid candidates/schema")
        types = {"string": str, "integer": int, "boolean": bool}
        if any(not isinstance(name, str) or not name.strip() or
               not isinstance(kind, str) or kind not in types
               for name, kind in allowed.items()):
            return refused("invalid schema fields")
        if not isinstance(required, list) or any(
                not isinstance(name, str) or name not in allowed for name in required):
            return refused("invalid required fields")
        if any(not isinstance(name, str) or not name.strip() or
               not isinstance(cid, str) or not cid.strip()
               for name, cid in self.selections.items()):
            return refused("invalid selections")
        if len(candidates) > limits.max_candidates or len(self.selections) > limits.max_fields:
            return refused("selection limit exceeded")
        text = document_slice.get("text", "")
        if not isinstance(text, str):
            return refused("invalid slice text")
        if len(text) > limits.max_slice_characters:
            return refused("slice limit exceeded")
        index = {}
        for candidate in candidates:
            if not isinstance(candidate, dict):
                return refused("malformed candidate")
            cid = candidate.get("candidate_id")
            if not isinstance(cid, str) or not cid.strip() or cid in index:
                return refused("invalid or duplicate candidate ID")
            if candidate.get("carrier") != carrier:
                return refused("cross-carrier candidate")
            index[cid] = candidate
        fields, pointers = {}, {}
        for name, cid in self.selections.items():
            candidate = index.get(cid)
            expected_type = types.get(allowed.get(name))
            if candidate is None or expected_type is None or candidate.get("field") != name:
                return refused("selection not in schema/candidate set")
            value = candidate.get("typed_value")
            if type(value) is not expected_type or candidate.get("pointer") is None:
                return refused("invalid candidate type/pointer")
            try:
                verified = self.verify_candidate(candidate)
            except (ValueError, KeyError, TypeError):
                return refused("candidate verification failed")
            if verified is not True:
                return refused("candidate source or normalization unverified")
            fields[name], pointers[name] = value, candidate["pointer"]
        if any(name not in fields for name in required):
            return refused("required field not selected")
        return ExtractionResult(fields=fields, pointers=pointers, status="ok")
