"""Exact byte and Unicode-codepoint provenance; no fuzzy source alignment."""

from .registry import SourceResolver, SpanPointer
from .verify import verify_document

__all__ = ["SourceResolver", "SpanPointer", "verify_document"]
