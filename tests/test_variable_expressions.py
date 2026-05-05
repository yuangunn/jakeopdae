"""${expr | ...} sandboxed expression evaluation.

The plain ``${name}`` path is already covered by test_ocr_and_variables;
these tests focus on the new expression form added in B2.

Security: malicious YAML must not be able to escape the sandbox.
"""

from __future__ import annotations

import re

import pytest

from keymacro.core.variables import (
    evaluate_expression,
    substitute,
)
from keymacro.core.variables import _ExpressionError  # type: ignore[attr-defined]


# --- arithmetic + comparisons ---------------------------------------------


def test_arithmetic_with_variable():
    assert substitute("${expr | counter + 1}", {"counter": 4}) == "5"


def test_arithmetic_with_string_numeric_coercion():
    """OCR captures land as strings — expressions should still treat
    a numeric-looking string as a number for arithmetic."""
    assert substitute("${expr | counter + 1}", {"counter": "41"}) == "42"


def test_multiple_expressions_in_one_string():
    out = substitute(
        "x=${expr | a + b}, y=${expr | a * b}",
        {"a": 3, "b": 4},
    )
    assert out == "x=7, y=12"


def test_unknown_variable_raises():
    with pytest.raises(_ExpressionError):
        evaluate_expression("ghost + 1", {})


def test_unknown_variable_in_substitute_keeps_text():
    """Bad expression → original text preserved (so the user can fix
    it without the macro crashing mid-run)."""
    out = substitute("${expr | ghost + 1}", {})
    assert out == "${expr | ghost + 1}"


# --- helper functions -----------------------------------------------------


def test_random_int_in_range():
    out = substitute("${expr | random(10, 12)}", {})
    assert out in ("10", "11", "12")


def test_strftime_runs_against_local_time():
    """We don't pin the value (it's the wall clock), just sanity-check
    that the helper got called and produced a YYYYMMDD-shaped string."""
    out = substitute("${expr | strftime('%Y%m%d')}", {})
    assert re.fullmatch(r"\d{8}", out)


def test_len_of_variable():
    assert substitute("${expr | len(otp)}", {"otp": "654321"}) == "6"


def test_int_conversion():
    assert substitute("${expr | int(x) * 2}", {"x": "21"}) == "42"


# --- security -------------------------------------------------------------


def test_attribute_access_rejected():
    """Dunder access would let a YAML escape into ``__class__`` etc.
    Blocked at AST compile time."""
    with pytest.raises(_ExpressionError):
        evaluate_expression("(1).__class__", {})


def test_function_call_to_unknown_rejected():
    with pytest.raises(_ExpressionError):
        evaluate_expression("eval('1+1')", {})


def test_import_rejected():
    """SyntaxError from ast.parse(mode='eval') → wrapped as
    _ExpressionError (not a true sandbox bypass, but worth verifying
    the error path)."""
    with pytest.raises(_ExpressionError):
        evaluate_expression("__import__('os')", {})


def test_indexing_rejected():
    """``var[0]`` could be used to walk dunder lookups via constants —
    cheaper to disallow Subscript wholesale."""
    with pytest.raises(_ExpressionError):
        evaluate_expression("a[0]", {"a": "hi"})


# --- mixing with plain ${var} ---------------------------------------------


def test_plain_var_still_works_alongside_expr():
    out = substitute(
        "Hello ${name}! Next: ${expr | counter + 1}",
        {"name": "Cody", "counter": 5},
    )
    assert out == "Hello Cody! Next: 6"


def test_fast_path_no_substitution_needed():
    """No ``${`` → bail without compiling anything, important for hot
    paths like substitute(action.text, ...) on every step."""
    assert substitute("plain string", {"x": 1}) == "plain string"
    assert substitute("", {}) == ""
