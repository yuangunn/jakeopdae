"""Macro-variable substitution + expression evaluation.

Two syntaxes, in increasing order of power:

    ``${name}``
        Plain variable reference. Looks up ``name`` in the runtime
        variables dict and inserts ``str(value)``. Unknown names are
        kept verbatim so a typo doesn't crash mid-run.

    ``${expr | <expression>}``
        Expression form. ``<expression>`` is a small whitelisted
        subset of Python evaluated against a sandbox namespace that
        exposes:

        - The runtime variables (so ``counter`` resolves to its value)
        - ``random(a, b)`` — uniform random integer in ``[a, b]``
        - ``randf(a, b)`` — uniform random float
        - ``strftime(fmt)`` — current local time formatted (e.g.
          ``strftime('%Y%m%d')`` for "20250507")
        - ``int(...)``, ``float(...)``, ``str(...)``, ``len(...)`` —
          common conversions
        - Arithmetic operators (+ - * / // % **), comparisons, and
          boolean operators

        AST whitelisting (no ``eval`` of arbitrary code) prevents
        attribute access, imports, dunders, calls to anything other
        than the registered helpers, etc. — so a malicious YAML can't
        spawn shells or read files.

Examples that now work:
    ${counter+1}                   → next iteration counter
    ${expr | counter * 2}           → explicit form, equivalent
    ${expr | random(0, 100)}        → "37"
    ${expr | strftime("%Y%m%d")}    → "20250507"
    ${expr | len(otp) }             → length of the captured OTP

The plain-name path stays the fast common case — most templates only
reference variables.
"""

from __future__ import annotations

import ast
import logging
import operator as _op
import random as _random
import re
import time as _time
from typing import Any, Callable, Mapping

log = logging.getLogger(__name__)

# Plain variable: ${name}
# Expression form: ${expr | <python expression>}
_VAR_PATTERN = re.compile(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}")
_EXPR_PATTERN = re.compile(r"\$\{expr\s*\|\s*(.+?)\}", re.DOTALL)


# --- expression sandbox -----------------------------------------------------


class _ExpressionError(ValueError):
    """Raised when a ${expr | ...} block is malformed or accesses
    something the sandbox doesn't allow. Caught at substitution time
    so the original text is preserved and a warning logged."""


def _sandbox_random(a: int, b: int) -> int:
    return _random.randint(int(a), int(b))


def _sandbox_randf(a: float, b: float) -> float:
    return _random.uniform(float(a), float(b))


def _sandbox_strftime(fmt: str) -> str:
    return _time.strftime(fmt, _time.localtime())


_SANDBOX_FUNCS: dict[str, Callable[..., Any]] = {
    "random": _sandbox_random,
    "randf": _sandbox_randf,
    "strftime": _sandbox_strftime,
    "int": int,
    "float": float,
    "str": str,
    "len": len,
    "min": min,
    "max": max,
    "abs": abs,
    "round": round,
}


# AST node → operator function. Anything not in this map is rejected
# at compile time, so attribute access, imports, etc. raise before we
# ever execute user input.
_BIN_OPS: dict[type, Callable[[Any, Any], Any]] = {
    ast.Add: _op.add,
    ast.Sub: _op.sub,
    ast.Mult: _op.mul,
    ast.Div: _op.truediv,
    ast.FloorDiv: _op.floordiv,
    ast.Mod: _op.mod,
    ast.Pow: _op.pow,
}
_UNARY_OPS: dict[type, Callable[[Any], Any]] = {
    ast.UAdd: _op.pos,
    ast.USub: _op.neg,
    ast.Not: _op.not_,
}
_CMP_OPS: dict[type, Callable[[Any, Any], bool]] = {
    ast.Eq: _op.eq, ast.NotEq: _op.ne,
    ast.Lt: _op.lt, ast.LtE: _op.le,
    ast.Gt: _op.gt, ast.GtE: _op.ge,
}


def _eval_node(node: ast.AST, variables: Mapping[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        if node.id in variables:
            # Don't auto-coerce here — let arithmetic call sites do it
            # so functions like ``len()`` receive the original string.
            return variables[node.id]
        if node.id in _SANDBOX_FUNCS:
            return _SANDBOX_FUNCS[node.id]
        raise _ExpressionError(f"unknown name: {node.id!r}")
    if isinstance(node, ast.BinOp):
        op_type = type(node.op)
        if op_type not in _BIN_OPS:
            raise _ExpressionError(f"operator {op_type.__name__} not allowed")
        # Numeric coercion happens here so ``${expr | counter + 1}``
        # works against an OCR-captured "41" without an explicit
        # ``int(${counter})`` wrapper, while ``len(otp)`` higher up
        # still sees the original string.
        return _BIN_OPS[op_type](
            _coerce_for_expr(_eval_node(node.left, variables)),
            _coerce_for_expr(_eval_node(node.right, variables)),
        )
    if isinstance(node, ast.UnaryOp):
        op_type = type(node.op)
        if op_type not in _UNARY_OPS:
            raise _ExpressionError(f"unary {op_type.__name__} not allowed")
        return _UNARY_OPS[op_type](
            _coerce_for_expr(_eval_node(node.operand, variables))
            if op_type is not ast.Not else _eval_node(node.operand, variables)
        )
    if isinstance(node, ast.BoolOp):
        values = [_eval_node(v, variables) for v in node.values]
        if isinstance(node.op, ast.And):
            return all(values) and values[-1]
        if isinstance(node.op, ast.Or):
            for v in values:
                if v:
                    return v
            return values[-1]
        raise _ExpressionError("unknown boolean op")
    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, variables)
        for op, right_node in zip(node.ops, node.comparators):
            right = _eval_node(right_node, variables)
            if type(op) not in _CMP_OPS:
                raise _ExpressionError(f"comparison {type(op).__name__} not allowed")
            if not _CMP_OPS[type(op)](left, right):
                return False
            left = right
        return True
    if isinstance(node, ast.Call):
        if not isinstance(node.func, ast.Name):
            raise _ExpressionError("only direct function calls allowed")
        fn_name = node.func.id
        if fn_name not in _SANDBOX_FUNCS:
            raise _ExpressionError(f"function {fn_name!r} not allowed")
        if node.keywords:
            raise _ExpressionError("keyword args not allowed in ${expr|}")
        args = [_eval_node(a, variables) for a in node.args]
        return _SANDBOX_FUNCS[fn_name](*args)
    raise _ExpressionError(f"node {type(node).__name__} not allowed")


def _coerce_for_expr(value: Any) -> Any:
    """When a runtime variable holds a numeric-looking string (common
    after ExtractTextAction reads "42" off the screen), coerce it so
    arithmetic in the expression works without explicit ``int(${var})``
    wrapping. Strings that don't parse as numbers pass through.
    """
    if isinstance(value, str):
        s = value.strip()
        if s and s.lstrip("-").isdigit():
            try:
                return int(s)
            except ValueError:
                return value
        try:
            return float(s)
        except ValueError:
            return value
    return value


def evaluate_expression(expr: str, variables: Mapping[str, Any]) -> str:
    """Compile + evaluate a single ``${expr | ...}`` body.

    Raises :class:`_ExpressionError` for malformed input or sandbox
    violations; callers swallow these and keep the original text.
    """
    try:
        tree = ast.parse(expr.strip(), mode="eval")
    except SyntaxError as e:
        raise _ExpressionError(f"syntax error: {e.msg}") from e
    return str(_eval_node(tree.body, variables))


# --- public API -------------------------------------------------------------


def substitute(text: str, variables: Mapping[str, Any]) -> str:
    """Replace every ``${name}`` and ``${expr | ...}`` in ``text``.

    - Unknown plain names stay verbatim.
    - Malformed/disallowed expressions stay verbatim and log a warning.
    Values are stringified.
    """
    if not text or "${" not in text:
        return text  # fast path

    # Expression form first so its braces don't get mistaken for a
    # plain ``${name}`` lookup.
    def _eval_sub(m: re.Match[str]) -> str:
        try:
            return evaluate_expression(m.group(1), variables)
        except _ExpressionError as e:
            log.warning("bad expression %s: %s", m.group(0), e)
            return m.group(0)

    text = _EXPR_PATTERN.sub(_eval_sub, text)

    def _name_sub(m: re.Match[str]) -> str:
        name = m.group(1)
        if name not in variables:
            log.debug("unknown variable ${%s}; leaving as-is", name)
            return m.group(0)
        return str(variables[name])

    return _VAR_PATTERN.sub(_name_sub, text)


def referenced_names(text: str) -> set[str]:
    """Return the set of variable names referenced in ``text`` (plain
    form only — expression bodies aren't statically inspected)."""
    if not text or "${" not in text:
        return set()
    return {m.group(1) for m in _VAR_PATTERN.finditer(text)}
