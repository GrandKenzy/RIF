"""Compilation of the current Gram AST representation into flat RIF MIR."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Iterable

from Frontend import globals
from Frontend.syntax.items.instructions import RawInstruction

from .instructions import CompiledRule, CompiledRuleSet, Instruction, Operand, SourceSpan


_VALUE_KINDS = {"NUMBER", "IDENT", "STRING", "BOOL"}

# Fuentes virtuales cargadas desde un .pack. Gram conserva el valor numérico
# ya convertido, pero el MIR también necesita el lexema original (por ejemplo,
# ``0000``) para conservar anchos explícitos.
SOURCE_TEXTS: dict[str, str] = {}


def _children(node: Any) -> tuple[Any, ...]:
    if isinstance(node, (list, tuple)):
        return tuple(node)
    items = getattr(node, "items", None)
    if items is not None:
        return tuple(items)
    return tuple(getattr(node, "nodes", ()) or ())


def _walk(node: Any):
    yield node
    for child in _children(node):
        yield from _walk(child)


def _token(node: Any) -> Any:
    if hasattr(node, "line") and hasattr(node, "col") and hasattr(node, "value"):
        return node
    return getattr(node, "token", None)


def _token_kind(node: Any) -> str | None:
    token = _token(node)
    return getattr(getattr(token, "token", None), "name", None)


def _token_value(node: Any) -> Any:
    return getattr(_token(node), "value", None)


def _named(node: Any, name: str) -> tuple[Any, ...]:
    return tuple(current for current in _walk(node) if getattr(current, "name", None) == name)


def _source_lexeme(node: Any, source_path: str | None) -> str | None:
    token = _token(node)
    if token is None:
        return None
    line = getattr(token, "line", None)
    column = getattr(token, "col", None)
    if not source_path or not isinstance(line, int) or not isinstance(column, int):
        return str(getattr(token, "value", ""))
    if source_path in SOURCE_TEXTS:
        lines = SOURCE_TEXTS[source_path].splitlines()
    else:
        path = Path(source_path)
        if not path.is_file():
            return str(getattr(token, "value", ""))
        lines = path.read_text(encoding="utf-8").splitlines()
    if line <= 0 or line > len(lines):
        return str(getattr(token, "value", ""))
    remainder = lines[line - 1][column:]
    match = re.match(r"[^\s,\]\[)]+", remainder)
    return match.group(0) if match else str(getattr(token, "value", ""))


def _span(node: Any, source_path: str | None) -> SourceSpan:
    for current in _walk(node):
        token = _token(current)
        if token is not None:
            return SourceSpan(
                source_path,
                getattr(token, "line", None),
                getattr(token, "col", None),
            )
    return SourceSpan(source_path, None, None)


def _literal_operand(node: Any, source_path: str | None) -> Operand:
    kind = _token_kind(node)
    value = _token_value(node)
    raw = _source_lexeme(node, source_path)
    width = None
    if kind == "NUMBER" and isinstance(raw, str) and raw.isdigit():
        width = len(raw)
    return Operand(kind=(kind or "VALUE").lower(), value=value, raw=raw, width=width)


def _token_operand(node: Any, source_path: str | None) -> Operand:
    leaves = tuple(current for current in _walk(node) if _token_kind(current) in {"KEYWORD", "NUMBER"})
    if len(leaves) != 1:
        raise RuntimeError("La referencia TOKEN debe contener un único nombre o número.")
    leaf = leaves[0]
    value = _token_value(leaf)
    return Operand("token", value, _source_lexeme(leaf, source_path))


def _value_operand(node: Any, source_path: str | None) -> Operand:
    table = _named(node, "TABLE_ACCESS")
    if table:
        leaves = tuple(current for current in _walk(table[0]) if _token_kind(current) == "IDENT")
        if len(leaves) != 2:
            raise RuntimeError("TABLE_ACCESS debe contener tabla y columna.")
        return Operand("table_access", (_token_value(leaves[0]), _token_value(leaves[1])))

    reservation = _named(node, "RESERVATION_ACCESS")
    if reservation:
        leaves = tuple(current for current in _walk(reservation[0]) if _token_kind(current) == "IDENT")
        if len(leaves) != 1:
            raise RuntimeError("RESERVATION_ACCESS debe contener un nombre.")
        return Operand("reservation_access", _token_value(leaves[0]))

    call = _named(node, "CALL_VALUE")
    if call:
        leaves = tuple(current for current in _walk(call[0]) if _token_kind(current) == "IDENT")
        if len(leaves) != 1:
            raise RuntimeError("CALL_VALUE debe contener un nombre.")
        return Operand("call", _token_value(leaves[0]))

    position_values = {
        "SIZE_VALUE": "size",
        "VSIZE_VALUE": "vsize",
        "ALIGNMENT_VALUE": "alignment",
        "DIST_VALUE": "distance",
        "VDIST_VALUE": "vdistance",
        "RESDIR_VALUE": "reservation_address",
        "RESVDIR_VALUE": "reservation_vaddress",
        "RESDIST_VALUE": "reservation_distance",
        "RESVDIST_VALUE": "reservation_vdistance",
    }
    for node_name, operand_kind in position_values.items():
        matches = _named(node, node_name)
        if not matches:
            continue
        strings = tuple(
            current
            for current in _walk(matches[0])
            if _token_kind(current) == "STRING"
        )
        if operand_kind in {"size", "vsize", "alignment"}:
            return Operand(operand_kind, None)
        if len(strings) != 1:
            raise RuntimeError(f"{node_name} debe contener un nombre string.")
        return Operand(operand_kind, _token_value(strings[0]))

    leaves = tuple(current for current in _walk(node) if _token_kind(current) in _VALUE_KINDS)
    if len(leaves) != 1:
        raise RuntimeError("VALUE debe contener un único literal o acceso.")
    return _literal_operand(leaves[0], source_path)


def _direct_leaves(node: Any) -> tuple[Any, ...]:
    return tuple(
        current
        for current in _walk(node)
        if _token_kind(current) in _VALUE_KINDS
        and getattr(current, "name", None) not in {"VALUE", "TOKEN"}
    )


def _compile_operands(node: Any, source_path: str | None) -> tuple[Operand, ...]:
    name = getattr(node, "name", None)
    if name == "TABLE_MATCHER":
        return (
            _value_operand(_named(node, "TABLE_ACCESS")[0], source_path),
            _token_operand(_named(node, "TOKEN")[0], source_path),
        )
    if name == "CONSUMER" or isinstance(node, list):
        tokens = _named(node, "TOKEN")
        return tuple(_token_operand(token, source_path) for token in tokens)
    if name == "STORE":
        arrays = tuple(current for current in _walk(node) if hasattr(current, "items"))
        if not arrays:
            return ()
        return tuple(_token_operand(item, source_path) for item in _named(arrays[0], "TOKEN"))
    if name in {"PUT", "EBIT", "EMMIT", "LDRES"}:
        values = _named(node, "VALUE")
        operands = [_value_operand(value, source_path) for value in values]
        if name == "LDRES":
            strings = tuple(current for current in _walk(node) if _token_kind(current) == "STRING")
            return (Operand("string", _token_value(strings[0]), _source_lexeme(strings[0], source_path)), *operands)
        return tuple(operands)
    if name == "JMPIF":
        identifiers = tuple(current for current in _walk(node) if _token_kind(current) == "IDENT")
        conditions = tuple(
            _value_operand(current, source_path)
            for current in _walk(node)
            if _token_kind(current) == "BOOL"
        ) + tuple(_value_operand(current, source_path) for current in _named(node, "CALL_VALUE"))
        return (Operand("rule", _token_value(identifiers[0])), *conditions)
    if name == "CALL":
        return tuple(_value_operand(current, source_path) for current in _named(node, "CALL_VALUE"))
    if name in {"KW", "SAVE", "LOAD", "RESERVE", "DLRES", "GTRES", "ERROR"}:
        strings = tuple(current for current in _walk(node) if _token_kind(current) == "STRING")
        operands = [Operand("string", _token_value(item), _source_lexeme(item, source_path)) for item in strings]
        if name == "RESERVE":
            operands.extend(
                _literal_operand(current, source_path)
                for current in _walk(node)
                if _token_kind(current) == "NUMBER"
            )
        return tuple(operands)
    if name == "JMP":
        identifiers = tuple(current for current in _walk(node) if _token_kind(current) == "IDENT")
        return tuple(Operand("rule", _token_value(item)) for item in identifiers)
    if name == "EMITFR":
        children = _children(node)
        rows: list[tuple[Operand, ...]] = []
        if len(children) > 2:
            first_values = tuple(
                _value_operand(item, source_path)
                for item in _children(children[2])
                if getattr(item, "name", None) == "VALUE"
            )
            if first_values:
                rows.append(first_values)
        if len(children) > 4:
            for line in _children(children[4]):
                values = tuple(
                    _value_operand(item, source_path)
                    for item in _walk(line)
                    if getattr(item, "name", None) == "VALUE"
                )
                if values:
                    rows.append(values)
        return (Operand("frame", tuple(rows)),)

    return tuple(
        _literal_operand(current, source_path)
        for current in _direct_leaves(node)
        if _token_kind(current) not in {"KEYWORD", "NEWLINE"}
    )


def _raw_literal(token: Any, source_path: str | None) -> Operand:
    kind = getattr(getattr(token, "token", None), "name", None)
    return _literal_operand(type("TokenNode", (), {"token": token})(), source_path)


def _raw_token_reference(token: Any, source_path: str | None) -> Operand:
    kind = getattr(getattr(token, "token", None), "name", None)
    if kind not in {"KEYWORD", "NUMBER"}:
        raise RuntimeError("Una instrucción debe referenciar un nombre de token o número.")
    return Operand("token", token.value, _source_lexeme(token, source_path))


def _raw_value(tokens: tuple[Any, ...], index: int, source_path: str | None) -> tuple[Operand, int]:
    token = tokens[index]
    kind = getattr(getattr(token, "token", None), "name", None)
    if kind == "COLON":
        if (
            index + 2 >= len(tokens)
            or tokens[index + 1].token.name != "COLON"
            or tokens[index + 2].token.name != "KEYWORD"
        ):
            raise RuntimeError("VALUE de posición incompleto.")
        position_names = {
            "SIZE": "size",
            "VSIZE": "vsize",
            "ALIGNMENT": "alignment",
        }
        operand_kind = position_names.get(str(tokens[index + 2].value))
        if operand_kind is None:
            raise RuntimeError("VALUE de posición desconocido.")
        return Operand(operand_kind, None), index + 3
    if kind == "KEYWORD":
        distance_names = {
            "dist": "distance",
            "vdist": "vdistance",
            "resdir": "reservation_address",
            "resvdir": "reservation_vaddress",
            "resdist": "reservation_distance",
            "resvdist": "reservation_vdistance",
        }
        operand_kind = distance_names.get(str(tokens[index].value))
        if operand_kind is not None:
            if index + 1 >= len(tokens) or tokens[index + 1].token.name != "STRING":
                raise RuntimeError(f"{tokens[index].value} requiere un nombre string.")
            return Operand(operand_kind, tokens[index + 1].value), index + 2
    if kind == "DOLLAR":
        if index + 3 >= len(tokens) or tokens[index + 1].token.name != "IDENT" or tokens[index + 2].token.name != "DOT" or tokens[index + 3].token.name != "IDENT":
            raise RuntimeError("TABLE_ACCESS está incompleto.")
        return (
            Operand("table_access", (tokens[index + 1].value, tokens[index + 3].value)),
            index + 4,
        )
    if kind == "AND":
        if index + 1 >= len(tokens) or tokens[index + 1].token.name != "IDENT":
            raise RuntimeError("RESERVATION_ACCESS está incompleto.")
        return Operand("reservation_access", tokens[index + 1].value), index + 2
    if kind == "HASH":
        if index + 4 >= len(tokens) or tokens[index + 1].value != "call" or tokens[index + 2].token.name != "LBRACKET" or tokens[index + 3].token.name != "IDENT" or tokens[index + 4].token.name != "RBRACKET":
            raise RuntimeError("CALL_VALUE está incompleto.")
        return Operand("call", tokens[index + 3].value), index + 5
    if kind in _VALUE_KINDS:
        return _raw_literal(token, source_path), index + 1
    raise RuntimeError(f"VALUE no reconocido: {kind}.")


def _raw_values(tokens: tuple[Any, ...], source_path: str | None) -> tuple[Operand, ...]:
    values: list[Operand] = []
    index = 0
    while index < len(tokens):
        if tokens[index].token.name in {"COMMA", "NEWLINE"}:
            index += 1
            continue
        value, index = _raw_value(tokens, index, source_path)
        values.append(value)
    return tuple(values)


def _compile_raw(node: RawInstruction, source_path: str | None) -> Instruction:
    first = node.lines[0]
    body = first[1:-1]
    opcode = node.opcode
    operands: tuple[Operand, ...]

    if opcode == "consumer":
        operands = (_raw_token_reference(body[0], source_path),)
    elif opcode == "table_matcher":
        if len(body) < 6 or body[0].token.name != "DOLLAR":
            raise RuntimeError("TABLE_MATCHER está incompleto.")
        operands = (
            Operand("table_access", (body[1].value, body[3].value)),
            _raw_token_reference(body[5], source_path),
        )
    elif opcode == "store":
        candidates = tuple(
            _raw_token_reference(token, source_path)
            for token in body[1:]
            if token.token.name in {"KEYWORD", "NUMBER"}
        )
        operands = candidates
    elif opcode == "emitfr":
        rows = []
        first_values = tuple(token for token in body[1:] if token.token.name not in {"COMMA"})
        rows.append(_raw_values(first_values, source_path))
        for line in node.lines[1:-1]:
            values = tuple(token for token in line if token.token.name != "NEWLINE")
            if values:
                rows.append(_raw_values(values, source_path))
        operands = (Operand("frame", tuple(rows)),)
    else:
        rest = tuple(body[1:])
        if opcode in {"put", "ebit", "emmit", "ldres", "padding", "alignement"}:
            if opcode == "ldres":
                first_string = next((token for token in rest if token.token.name == "STRING"), None)
                if first_string is None:
                    raise RuntimeError("LDRES requiere el nombre de una reserva.")
                value_tokens = rest[rest.index(first_string) + 1:]
                operands = (
                    Operand("string", first_string.value, _source_lexeme(first_string, source_path)),
                    *_raw_values(tuple(token for token in value_tokens if token.token.name != "COMMA"), source_path),
                )
            else:
                operands = _raw_values(rest, source_path)
        elif opcode in {"kw", "save", "load", "error"}:
            strings = tuple(token for token in rest if token.token.name == "STRING")
            operands = tuple(
                Operand("string", token.value, _source_lexeme(token, source_path))
                for token in strings
            )
        elif opcode in {"jmp", "jmplabel"}:
            operands = tuple(Operand("rule", token.value) for token in rest if token.token.name == "IDENT")
        elif opcode == "jmpif":
            identifiers = tuple(token for token in rest if token.token.name == "IDENT")
            conditions = tuple(token for token in rest if token.token.name in {"BOOL", "HASH"})
            condition_tokens = tuple(token for token in rest if token.token.name not in {"COMMA"})
            condition, _ = _raw_value(condition_tokens, 1, source_path)
            operands = (Operand("rule", identifiers[0].value), condition)
        elif opcode == "call":
            operands = (_raw_value(rest, 0, source_path)[0],)
        elif opcode == "reserve":
            strings = tuple(token for token in rest if token.token.name == "STRING")
            numbers = tuple(token for token in rest if token.token.name == "NUMBER")
            operands = (
                Operand("string", strings[0].value, _source_lexeme(strings[0], source_path)),
                _raw_literal(numbers[0], source_path),
            )
        elif opcode in {"dlres", "gtres"}:
            strings = tuple(token for token in rest if token.token.name == "STRING")
            operands = (Operand("string", strings[0].value, _source_lexeme(strings[0], source_path)),)
        else:
            operands = ()

    start = node.start
    span = SourceSpan(
        source_path,
        getattr(start, "line", None),
        getattr(start, "col", None),
    )
    return Instruction(opcode, operands, span, source_node=node)


def compile_instruction(node: Any, source_path: str | None = None) -> Instruction:
    if isinstance(node, RawInstruction):
        return _compile_raw(node, source_path)
    name = getattr(node, "name", None)
    if name is None and isinstance(node, (list, tuple)):
        name = "CONSUMER"
    if name is None:
        raise RuntimeError("No se pudo identificar el opcode de una instrucción.")
    return Instruction(
        opcode=name.lower(),
        operands=_compile_operands(node, source_path),
        span=_span(node, source_path),
        source_node=node,
    )


def compile_rule(rule: globals.RuleData) -> CompiledRule:
    return CompiledRule(
        name=rule.name,
        instructions=tuple(compile_instruction(node, rule.source_path) for node in rule.instructions),
        source_path=rule.source_path,
    )


def compile_rules(
    rules: Iterable[globals.RuleData] | None = None,
    *,
    resolve: bool = False,
) -> CompiledRuleSet:
    selected = tuple(rules) if rules is not None else tuple(globals.RULES.values())
    compiled = {rule.name: compile_rule(rule) for rule in selected}
    program = CompiledRuleSet(compiled)
    if resolve:
        from .semantic import resolve_program

        return resolve_program(program)
    return program


__all__ = ["compile_instruction", "compile_rule", "compile_rules"]
