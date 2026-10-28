"""Provider-neutral selection contract; code owns amounts and verdicts."""

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class Limits:
    max_candidates: int = 200
    max_fields: int = 30
    max_slice_characters: int = 100_000

    def __post_init__(self) -> None:
        for value in (self.max_candidates, self.max_fields, self.max_slice_characters):
            if type(value) is not int or value <= 0:
                raise ValueError("limits must be positive integers")


@dataclass(frozen=True)
class ExtractionResult:
    fields: dict[str, Any] = field(default_factory=dict)
    pointers: dict[str, Any] = field(default_factory=dict)
    origin: str = "mock"
    usage: dict[str, int] | None = None
    status: str = "abstained"
    errors: tuple[str, ...] = ()


class ExtractionPort(Protocol):
    def extract(self, document_slice: dict, schema: dict, request_id: str,
                limits: Limits) -> ExtractionResult: ...


def live_disabled() -> ExtractionResult:
    """Refuse unconditionally; never inspect environment, keys, SDKs or network."""
    return ExtractionResult(origin="disabled", status="live_not_enabled",
                            errors=("live transport is not implemented or authorized",))
