"""Shared runtime semantics used by both execution engines.

These helpers mirror the tree-walking interpreter exactly so that compiled
programs observe the same coercion, comparison, and arithmetic rules.
"""

from __future__ import annotations

from typing import Any

from .values import display, iterate, type_name

MAX_EXPONENT = 1_000_000
MAX_BITS = 8_000_000


def is_truthy(value: Any) -> bool:
    if value is None or value is False:
        return False
    if isinstance(value, (int, float)) and value == 0:
        return False
    if isinstance(value, (str, list, dict, range)) and len(value) == 0:
        return False
    return True


def is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def loose_eq(left: Any, right: Any) -> bool:
    if isinstance(left, bool) != isinstance(right, bool):
        return False
    return left == right


def apply_binary(op: str, left: Any, right: Any) -> Any:
    if op == "+":
        if isinstance(left, str) and isinstance(right, str):
            return left + right
        if isinstance(left, list) and isinstance(right, list):
            return left + right
        if is_number(left) and is_number(right):
            return left + right
        raise TypeError("+ inahitaji namba, maneno, au orodha zote mbili")
    if op == "-":
        if is_number(left) and is_number(right):
            return left - right
        raise TypeError("- inahitaji namba zote mbili")
    if op == "*":
        if is_number(left) and is_number(right):
            return left * right
        if isinstance(left, str) and is_number(right):
            return left * int(right)
        if is_number(left) and isinstance(right, str):
            return right * int(left)
        if isinstance(left, list) and is_number(right):
            return left * int(right)
        raise TypeError("* inahitaji namba zote mbili, au maneno/orodha na namba")
    if op == "/":
        if is_number(left) and is_number(right):
            return left / right
        raise TypeError("/ inahitaji namba zote mbili")
    if op == "//":
        if is_number(left) and is_number(right):
            return left // right
        raise TypeError("// inahitaji namba zote mbili")
    if op == "%":
        if is_number(left) and is_number(right):
            return left % right
        raise TypeError("% inahitaji namba zote mbili")
    if op == "**":
        if is_number(left) and is_number(right):
            return left ** right
        raise TypeError("** inahitaji namba zote mbili")
    raise TypeError("operesheni isiyojulikana: " + op)


def compare(op: str, left: Any, right: Any) -> Any:
    if op == "iko":
        if isinstance(right, str):
            return isinstance(left, str) and left in right
        try:
            return left in iterate(right)
        except TypeError:
            return False
    if op == "ni":
        return type(left) is type(right) and left == right
    if op == "==":
        return loose_eq(left, right)
    if op == "!=":
        return not loose_eq(left, right)
    if op == "<":
        return left < right
    if op == "<=":
        return left <= right
    if op == ">":
        return left > right
    if op == ">=":
        return left >= right
    raise ValueError("Linganisho lisilojulikana: " + op)


def coerce(value: Any, hint: str) -> Any:
    actual = type_name(value)
    if hint == "namba" and actual == "desimali" and float(value).is_integer():
        return int(value)
    if actual == hint:
        return value
    if hint == "desimali" and actual == "namba":
        return float(value)
    if hint == "orodha" and actual == "kipeano":
        return list(value)
    return value


def too_large_message(size: int, limit: int) -> tuple[str, str]:
    return (f"Matokeo ni makubwa mno ({size} > {limit})",
            f"Result is too large ({size} > {limit})")


def exponent_too_large_message(exponent: int, bits: int) -> tuple[str, str]:
    return ("Namba inayotokana na ** ni kubwa mno",
            f"Result of ** is too large (exponent {exponent}, {bits} bits)")


def format_value(value: Any) -> str:
    return display(value)
