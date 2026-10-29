"""Local review attribution; no identity authentication or sending authority."""
from .log import DecisionLog, ReviewError

__all__ = ["DecisionLog", "ReviewError"]
