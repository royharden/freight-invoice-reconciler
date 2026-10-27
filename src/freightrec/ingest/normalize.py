"""Compatibility entry point; canonical normalizers have no PDF dependency."""

from freightrec.sources.normalize import normalize

__all__ = ["normalize"]
