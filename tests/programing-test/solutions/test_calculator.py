"""Unit tests for Calculator class using pytest.

Covers: basic arithmetic, edge cases, type validation,
floating-point precision, and large numbers.
"""

import pytest


class Calculator:
    """Simple calculator with basic arithmetic operations."""

    def add(self, a, b):
        return a + b

    def subtract(self, a, b):
        return a - b

    def multiply(self, a, b):
        return a * b

    def divide(self, a, b):
        if b == 0:
            raise ValueError("Cannot divide by zero")
        return a / b


@pytest.fixture
def calc():
    """Provide a Calculator instance for each test."""
    return Calculator()


# --- Addition ---

class TestAdd:
    @pytest.mark.parametrize("a, b, expected", [
        (2, 3, 5),
        (0, 0, 0),
        (-1, -1, -2),
        (-5, 10, 5),
        (1.5, 2.5, 4.0),
        (100, 200, 300),
    ])
    def test_add(self, calc, a, b, expected):
        assert calc.add(a, b) == expected

    def test_add_identity(self, calc):
        """Adding zero returns the original value."""
        assert calc.add(42, 0) == 42
        assert calc.add(0, 42) == 42

    def test_add_commutative(self, calc):
        """Addition is commutative."""
        assert calc.add(3, 7) == calc.add(7, 3)


# --- Subtraction ---

class TestSubtract:
    @pytest.mark.parametrize("a, b, expected", [
        (5, 3, 2),
        (0, 0, 0),
        (-1, -1, 0),
        (3, 5, -2),
        (10, 4, 6),
        (1.5, 0.5, 1.0),
    ])
    def test_subtract(self, calc, a, b, expected):
        assert calc.subtract(a, b) == expected

    def test_subtract_identity(self, calc):
        """Subtracting zero returns the original value."""
        assert calc.subtract(42, 0) == 42

    def test_subtract_self(self, calc):
        """Subtracting a number from itself returns zero."""
        assert calc.subtract(99, 99) == 0


# --- Multiplication ---

class TestMultiply:
    @pytest.mark.parametrize("a, b, expected", [
        (3, 4, 12),
        (0, 5, 0),
        (-2, 3, -6),
        (-3, -3, 9),
        (2.5, 4, 10.0),
        (100, 0, 0),
    ])
    def test_multiply(self, calc, a, b, expected):
        assert calc.multiply(a, b) == expected

    def test_multiply_identity(self, calc):
        """Multiplying by one returns the original value."""
        assert calc.multiply(42, 1) == 42
        assert calc.multiply(1, 42) == 42

    def test_multiply_commutative(self, calc):
        """Multiplication is commutative."""
        assert calc.multiply(6, 7) == calc.multiply(7, 6)


# --- Division ---

class TestDivide:
    @pytest.mark.parametrize("a, b, expected", [
        (10, 2, 5.0),
        (9, 3, 3.0),
        (-6, 2, -3.0),
        (-8, -4, 2.0),
        (7, 2, 3.5),
        (0, 5, 0.0),
    ])
    def test_divide(self, calc, a, b, expected):
        assert calc.divide(a, b) == expected

    def test_divide_by_zero(self, calc):
        with pytest.raises(ValueError, match="Cannot divide by zero"):
            calc.divide(10, 0)

    def test_divide_by_zero_with_zero_numerator(self, calc):
        with pytest.raises(ValueError, match="Cannot divide by zero"):
            calc.divide(0, 0)

    def test_divide_identity(self, calc):
        """Dividing by one returns the original value."""
        assert calc.divide(42, 1) == 42.0

    def test_divide_self(self, calc):
        """Dividing a non-zero number by itself returns 1.0."""
        assert calc.divide(7, 7) == 1.0


# --- Negative number edge cases ---

class TestNegativeNumbers:
    def test_add_two_negatives(self, calc):
        assert calc.add(-10, -20) == -30

    def test_subtract_resulting_in_negative(self, calc):
        assert calc.subtract(3, 10) == -7

    def test_multiply_negatives_gives_positive(self, calc):
        assert calc.multiply(-4, -5) == 20

    def test_divide_negative_by_positive(self, calc):
        assert calc.divide(-12, 4) == -3.0

    def test_divide_positive_by_negative(self, calc):
        assert calc.divide(12, -4) == -3.0


# --- Floating-point precision ---

class TestFloatingPoint:
    def test_add_floats(self, calc):
        result = calc.add(0.1, 0.2)
        assert result == pytest.approx(0.3)

    def test_divide_floats(self, calc):
        result = calc.divide(1, 3)
        assert result == pytest.approx(0.3333, abs=1e-3)

    def test_multiply_floats(self, calc):
        result = calc.multiply(0.1, 0.1)
        assert result == pytest.approx(0.01)


# --- Large numbers ---

class TestLargeNumbers:
    def test_add_large(self, calc):
        assert calc.add(10**9, 10**9) == 2 * 10**9

    def test_multiply_large(self, calc):
        assert calc.multiply(10**6, 10**6) == 10**12

    def test_divide_large(self, calc):
        assert calc.divide(10**10, 10**5) == 10**5
