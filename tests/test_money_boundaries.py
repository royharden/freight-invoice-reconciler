"""Builder regressions only: monetary coercion and final-rounding defects."""
from decimal import Decimal, localcontext
import pytest
from freightrec.money import cents, decimal_string, rounded_cents


@pytest.mark.parametrize("value", [True, False, 1.0, None, "100", -1])
def test_cents_rejects_coercion(value):
    """what_bug_this_catches: bool/float/null silently becoming known dollars."""
    with pytest.raises(ValueError):
        cents(value)


@pytest.mark.parametrize("value", [True, 1, 1.5, None, "NaN", "Infinity", "-1", "1e2", " 1"])
def test_rates_require_finite_decimal_strings(value):
    with pytest.raises(ValueError):
        decimal_string(value)


@pytest.mark.parametrize("raw,expected", [("0.0049", 0), ("0.005", 1), ("9.995", 1000)])
def test_final_rounding_half_up(raw, expected):
    """what_bug_this_catches: banker rounding at a half cent."""
    assert rounded_cents(Decimal(raw)) == expected


def test_large_rounding_independent_of_ambient_precision():
    value = Decimal("123456789012345678901234567890.005")
    with localcontext() as context:
        context.prec = 3
        assert rounded_cents(value) == 12345678901234567890123456789001
    assert cents(0) == 0
