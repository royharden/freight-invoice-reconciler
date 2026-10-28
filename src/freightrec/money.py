"""Strict USD wire values and deterministic final-charge rounding."""

from decimal import Decimal, DecimalException, ROUND_HALF_UP, localcontext
import re


_DECIMAL_LITERAL = re.compile(r"[0-9]+(?:\.[0-9]+)?\Z")


def cents(value: object) -> int:
    """Accept only a nonnegative built-in integer, never bool or a coercion."""
    if type(value) is not int or value < 0:
        raise ValueError("money must be nonnegative integer cents")
    return value


def decimal_string(value: object) -> Decimal:
    """Parse an unsigned, finite decimal string; reject floats and exponents."""
    if type(value) is not str or _DECIMAL_LITERAL.fullmatch(value) is None:
        raise ValueError("rate must be an unsigned decimal string")
    try:
        result = Decimal(value)
    except DecimalException as exc:
        raise ValueError("invalid decimal rate") from exc
    if not result.is_finite() or result < 0:
        raise ValueError("rate must be finite and nonnegative")
    return result


def rounded_cents(dollars: Decimal) -> int:
    """Round one final nonnegative Decimal dollar amount to cents, half up."""
    if type(dollars) is not Decimal or not dollars.is_finite() or dollars < 0:
        raise ValueError("amount must be a finite nonnegative Decimal")
    try:
        # Preserve all significant digits regardless of the caller's context.
        parts = dollars.as_tuple()
        with localcontext() as context:
            context.prec = max(28, len(parts.digits) + max(0, parts.exponent) + 4)
            return int((dollars * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    except (DecimalException, ValueError, OverflowError) as exc:
        raise ValueError("amount cannot be represented as cents") from exc
