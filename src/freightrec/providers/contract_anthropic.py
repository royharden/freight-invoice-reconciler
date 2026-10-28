"""Contract placeholder only. No SDK, credential lookup or transport."""

from .base import live_disabled


def extract(*args, **kwargs):
    return live_disabled()
