"""Exact byte and Unicode-codepoint provenance; no fuzzy source alignment."""

from .registry import RecordFieldPointer, SourceResolver, SpanPointer
from .verify import verify_document

__all__ = ["SourceResolver", "SpanPointer", "RecordFieldPointer", "verify_document"]
