"""Semantic resolution and validation for the RIF MIR."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any

from gram import lexer

from Frontend import globals

from .instructions import CompiledRule, CompiledRuleSet, Instruction, Operand


class MIRSemanticError(ValueError):
    """A source-level semantic error with a useful MIR location."""


@dataclass(frozen=True)
class TokenRef:
    name: str
    token: lexer.Token


@dataclass(frozen=True)
class TableRef:
    table: str
    column: str
    index: int


@dataclass(frozen=True)
class RuleRef:
    name: str


def _where(instruction: Instruction) -> str:
    span = instruction.span
    if span.path is None:
        return "<memoria>"
    if span.line is None:
        return span.path
    return f"{span.path}:{span.line}:{span.column or 0}"


def _error(instruction: Instruction, message: str) -> MIRSemanticError:
    return MIRSemanticError(f"{_where(instruction)}: {message}")


def _resolve_token(instruction: Instruction, operand: Operand) -> Operand:
    value = operand.value
    if isinstance(value, bool):
        raise _error(instruction, "un token numérico no puede ser booleano.")
    if isinstance(value, int):
        token = lexer.Token.from_code(value)
        if token is None:
            raise _error(instruction, f"el código de token {value} no existe.")
        return replace(operand, resolved=TokenRef(str(value), token))
    if isinstance(value, str):
        token = lexer.Token.from_string(value)
        if token is None:
            raise _error(instruction, f"el token '{value}' no existe en lexer.Token.")
        return replace(operand, resolved=TokenRef(value, token))
    raise _error(instruction, f"referencia de token inválida: {value!r}.")


def _resolve_table(instruction: Instruction, operand: Operand) -> Operand:
    try:
        table_name, column_name = operand.value
    except (TypeError, ValueError) as exc:
        raise _error(instruction, "TABLE_ACCESS no tiene tabla y columna.") from exc
    table = globals.TABLES.get(table_name)
    if table is None:
        raise _error(instruction, f"la tabla '{table_name}' no existe.")
    try:
        index = table.columns[column_name]
    except KeyError as exc:
        raise _error(
            instruction,
            f"la columna '{column_name}' no existe en la tabla '{table_name}'.",
        ) from exc
    return replace(
        operand,
        resolved=TableRef(table_name, column_name, index),
    )


def _resolve_operand(instruction: Instruction, operand: Operand) -> Operand:
    if operand.kind == "token":
        return _resolve_token(instruction, operand)
    if operand.kind == "table_access":
        return _resolve_table(instruction, operand)
    if operand.kind == "rule":
        if operand.value not in globals.RULES:
            raise _error(instruction, f"la Rule '{operand.value}' no existe.")
        return replace(operand, resolved=RuleRef(operand.value))
    if operand.kind == "frame":
        rows = tuple(
            tuple(_resolve_operand(instruction, item) for item in row)
            for row in operand.value
        )
        return replace(operand, value=rows, resolved=rows)
    if operand.kind == "reservation_access":
        if not isinstance(operand.value, str) or not operand.value:
            raise _error(instruction, "el nombre de reserva no es válido.")
    if operand.kind in {
        "distance",
        "vdistance",
        "reservation_address",
        "reservation_vaddress",
        "reservation_distance",
        "reservation_vdistance",
    }:
        if not isinstance(operand.value, str) or not operand.value:
            raise _error(instruction, "el nombre de reserva o etiqueta no es válido.")
    return operand


_ARITY: dict[str, tuple[int, int | None]] = {
    "table_matcher": (2, 2),
    "consumer": (1, 1),
    "store": (1, None),
    "put": (2, 2),
    "ebit": (8, 8),
    "emmit": (1, 1),
    "padding": (1, 1),
    "alignement": (1, 1),
    "kw": (1, 1),
    "jmp": (1, 1),
    "save": (1, 1),
    "load": (1, 1),
    "reserve": (2, 2),
    "ldres": (2, 2),
    "dlres": (1, 1),
    "gtres": (1, 1),
    "jmpif": (2, 2),
    "break": (0, 0),
    "error": (1, 1),
    "call": (1, 1),
    "emitfr": (1, 1),
}


def _validate_instruction(instruction: Instruction) -> Instruction:
    minimum, maximum = _ARITY.get(instruction.opcode, (0, None))
    count = len(instruction.operands)
    if count < minimum or (maximum is not None and count > maximum):
        expected = str(minimum) if maximum == minimum else f"{minimum}..{maximum}"
        raise _error(
            instruction,
            f"'{instruction.opcode}' requiere {expected} operandos; recibió {count}.",
        )

    operands = tuple(_resolve_operand(instruction, operand) for operand in instruction.operands)

    if instruction.opcode == "put":
        for operand in operands:
            if operand.kind == "number" and operand.width not in {None, 4}:
                raise _error(instruction, "cada campo de put debe tener exactamente 4 bits.")
    elif instruction.opcode == "ebit":
        for operand in operands:
            if operand.kind == "number" and operand.value not in {0, 1}:
                raise _error(instruction, "cada campo de ebit debe ser 0 o 1.")
    elif instruction.opcode == "emmit":
        operand = operands[0]
        if operand.kind == "number" and globals.CONFIG is not None:
            if operand.value >= (1 << globals.CONFIG.wordsize):
                raise _error(
                    instruction,
                    f"el valor de emmit no cabe en wordsize={globals.CONFIG.wordsize}.",
                )
    elif instruction.opcode == "jmpif":
        if operands[1].kind not in {"bool", "call"}:
            raise _error(instruction, "JMPIF requiere BOOL o #call como condición.")
    elif instruction.opcode == "reserve":
        size = operands[1]
        if size.kind != "number" or not isinstance(size.value, int) or size.value <= 0:
            raise _error(instruction, "RESERVE requiere un tamaño entero mayor que cero.")
    elif instruction.opcode in {"padding", "alignement"}:
        size = operands[0]
        if size.kind != "number" or not isinstance(size.value, int) or size.value <= 0:
            raise _error(
                instruction,
                f"{instruction.opcode.upper()} requiere un tamaño entero mayor que cero.",
            )

    return replace(instruction, operands=operands)


def resolve_rule(rule: CompiledRule) -> CompiledRule:
    return replace(
        rule,
        instructions=tuple(_validate_instruction(instruction) for instruction in rule.instructions),
    )


def resolve_program(program: CompiledRuleSet) -> CompiledRuleSet:
    """Resolve names and validate every instruction in a compiled program."""

    return CompiledRuleSet({name: resolve_rule(rule) for name, rule in program.rules.items()})


__all__ = [
    "MIRSemanticError",
    "TokenRef",
    "TableRef",
    "RuleRef",
    "resolve_rule",
    "resolve_program",
]
