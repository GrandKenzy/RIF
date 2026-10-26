"""Validate and materialize top-level binary insert/finalization blocks."""

from __future__ import annotations

from typing import Any

from Frontend import globals


_VALUE_KINDS = {"NUMBER", "DECIMAL", "STRING", "IDENT", "BOOL"}
_NATIVE_KINDS = {"query", "qssize", "qlsize", "qvsize", "qvssize"}


def _body(line: tuple[Any, ...]) -> tuple[Any, ...]:
    if line and getattr(getattr(line[-1], "token", None), "name", None) == "NEWLINE":
        return line[:-1]
    return line


def _kind(token: Any) -> str:
    return getattr(getattr(token, "token", None), "name", "")


def _value(token: Any) -> Any:
    return getattr(token, "value", None)


def _line_name(tokens: tuple[Any, ...], directive: str) -> tuple[Any, ...]:
    if len(tokens) < 2 or _kind(tokens[0]) != "DOT" or _value(tokens[1]) != directive:
        raise RuntimeError(f"Se esperaba la directiva '.{directive}'.")
    return tokens[2:]


def _single_string(tokens: tuple[Any, ...], directive: str) -> str:
    if len(tokens) != 1 or _kind(tokens[0]) != "STRING":
        raise RuntimeError(f".{directive} requiere un único string.")
    value = _value(tokens[0])
    if not isinstance(value, str) or not value:
        raise RuntimeError(f".{directive} no puede recibir un string vacío.")
    return value


def _check_section(section: str) -> None:
    if globals.CONFIG is not None and section not in globals.CONFIG.sections:
        raise RuntimeError(f"La sección '{section}' no existe en @config.")


def _insert_lines(node: Any) -> tuple[tuple[Any, ...], ...]:
    lines = tuple(getattr(node, "lines", ()) or ())
    return tuple(_body(line) for line in lines if _body(line))


def visit_insert(node: Any, source_path: str | None = None) -> None:
    """Register an ordered binary prelude without executing it."""

    section = globals.CONFIG.defaultsection if globals.CONFIG is not None else ""
    section_declared = False
    seen_payload = False
    for tokens in _insert_lines(node):
        if len(tokens) >= 2 and _kind(tokens[0]) == "DOT" and _value(tokens[1]) == "section":
            if seen_payload:
                raise RuntimeError(".section debe aparecer antes de los payloads de @insert.")
            if section_declared:
                raise RuntimeError("@insert solo puede declarar .section una vez.")
            section = _single_string(tokens[2:], "section")
            _check_section(section)
            section_declared = True
            continue

        if len(tokens) < 2 or _kind(tokens[0]) != "DOT":
            raise RuntimeError("Cada línea de @insert debe ser una directiva con punto.")
        directive = str(_value(tokens[1]))
        if directive in {"binary", "bytes", "file"}:
            value = _single_string(tokens[2:], directive)
        elif directive == "call":
            rest = tokens[2:]
            if (
                len(rest) != 5
                or _kind(rest[0]) != "HASH"
                or _value(rest[1]) != "call"
                or _kind(rest[2]) != "LBRACKET"
                or _kind(rest[3]) != "IDENT"
                or _kind(rest[4]) != "RBRACKET"
            ):
                raise RuntimeError(".call requiere #call[nombre].")
            value = str(_value(rest[3]))
        else:
            raise RuntimeError(f"Directiva de @insert desconocida: .{directive}.")

        seen_payload = True
        globals.INSERTS.append(
            globals.InsertData(
                section=section,
                kind=directive,
                value=value,
                source_path=source_path,
            )
        )


def _literal(token: Any) -> dict[str, Any]:
    kind = _kind(token)
    if kind not in _VALUE_KINDS:
        raise RuntimeError(f"Se esperaba un valor y se encontró {kind or 'desconocido'}.")
    return {"kind": "literal", "token": kind, "value": _value(token)}


class _ExpressionParser:
    def __init__(self, tokens: tuple[Any, ...]) -> None:
        self.tokens = tokens
        self.index = 0

    def _peek(self) -> Any | None:
        return self.tokens[self.index] if self.index < len(self.tokens) else None

    def _take(self, expected: str | None = None) -> Any:
        token = self._peek()
        if token is None:
            raise RuntimeError("Expresión nativa incompleta.")
        if expected is not None and _kind(token) != expected:
            raise RuntimeError(f"Se esperaba {expected} y se encontró {_kind(token)}.")
        self.index += 1
        return token

    def expression(self, *, stop: str | None = None) -> dict[str, Any]:
        left = self.atom()
        while self._peek() is not None:
            if stop is not None and _kind(self._peek()) == stop:
                break
            current = self._peek()
            if _kind(current) not in {"PLUS", "MINUS"}:
                break
            operator = "+" if _kind(self._take()) == "PLUS" else "-"
            right = self.atom()
            left = {"kind": "calc", "operator": operator, "left": left, "right": right}
        return left

    def atom(self) -> dict[str, Any]:
        token = self._peek()
        if token is None:
            raise RuntimeError("Expresión nativa incompleta.")
        if _kind(token) == "LPAREN":
            self._take("LPAREN")
            value = self.expression(stop="RPAREN")
            self._take("RPAREN")
            return value
        if _kind(token) == "HASH":
            if (
                self.index + 4 < len(self.tokens)
                and _value(self.tokens[self.index + 1]) == "call"
                and _kind(self.tokens[self.index + 2]) == "LBRACKET"
                and _kind(self.tokens[self.index + 3]) == "IDENT"
                and _kind(self.tokens[self.index + 4]) == "RBRACKET"
            ):
                self.index += 5
                return {"kind": "call", "name": str(_value(self.tokens[self.index - 2]))}
            return self.native()
        return _literal(self._take())

    def native(self) -> dict[str, Any]:
        self._take("HASH")
        self._take("COLON")
        name = str(_value(self._take()))
        if name == "calc":
            if self._peek() is not None and _kind(self._peek()) == "LPAREN":
                self._take("LPAREN")
                expression = self.expression(stop="RPAREN")
                self._take("RPAREN")
            else:
                expression = self.expression()
            return expression
        if name not in _NATIVE_KINDS:
            raise RuntimeError(f"Función nativa desconocida: #:{name}.")

        parenthesized = self._peek() is not None and _kind(self._peek()) == "LPAREN"
        if parenthesized:
            self._take("LPAREN")
        first = self.atom()
        self._take("COMMA")
        second = self.atom()
        if parenthesized:
            self._take("RPAREN")
        return {"kind": name, "args": [first, second]}

    def finish(self) -> dict[str, Any]:
        result = self.expression()
        if self._peek() is not None:
            raise RuntimeError("Sobran tokens al final de la expresión nativa.")
        return result


def _rplc(tokens: tuple[Any, ...], source_path: str | None) -> globals.BeforePatchData:
    rest = _line_name(tokens, "rplc")
    if len(rest) < 2 or _kind(rest[0]) not in {"NUMBER", "DECIMAL"} or _kind(rest[1]) != "COMMA":
        raise RuntimeError(".rplc requiere offset y payload.")
    offset = _value(rest[0])
    if isinstance(offset, bool) or not isinstance(offset, int) or offset < 0:
        raise RuntimeError("El offset de .rplc debe ser un entero no negativo.")
    payload = rest[2:]
    width: int | None = None
    if len(payload) >= 2 and _kind(payload[0]) in {"NUMBER", "DECIMAL"} and _kind(payload[1]) == "COMMA":
        width = _value(payload[0])
        if isinstance(width, bool) or not isinstance(width, int) or width <= 0:
            raise RuntimeError("El ancho de .rplc debe ser un entero mayor que cero.")
        payload = payload[2:]
    if not payload:
        raise RuntimeError(".rplc requiere un payload.")
    expression = _ExpressionParser(tuple(payload)).finish()
    return globals.BeforePatchData(offset, width, expression, source_path)


def visit_before(node: Any, source_path: str | None = None) -> None:
    """Register final patches for execution after external MIR completes."""

    for tokens in _insert_lines(node):
        if len(tokens) < 2 or _kind(tokens[0]) != "DOT":
            raise RuntimeError("Cada línea de @before debe ser una directiva con punto.")
        directive = str(_value(tokens[1]))
        if directive != "rplc":
            raise RuntimeError(f"Directiva de @before desconocida: .{directive}.")
        globals.BEFORE.append(_rplc(tokens, source_path))


__all__ = ["visit_insert", "visit_before"]
