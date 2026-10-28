"""Small strict wire validators; no coercion of untrusted monetary data."""
from typing import Any

CODES = ("LH", "FS", "DETENTION", "LIFTGATE")


def mapping(value: Any, field: str = "object") -> dict:
    if type(value) is not dict:
        raise ValueError(f"{field}: expected object")
    return value


def sequence(value: Any, field: str = "list") -> list:
    if type(value) is not list:
        raise ValueError(f"{field}: expected array")
    return value


def text(value: Any, field: str = "text") -> str:
    if type(value) is not str or not value.strip():
        raise ValueError(f"{field}: expected nonempty string")
    return value


def boolean(value: Any, field: str = "boolean") -> bool:
    if type(value) is not bool:
        raise ValueError(f"{field}: expected explicit boolean")
    return value


def evidence(value: Any) -> list[dict]:
    pointers = sequence(value, "evidence_pointers")
    for pointer in pointers:
        mapping(pointer, "evidence pointer")
    return pointers
