"""Small executable runtime for the resolved RIF MIR."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Iterable, Mapping

from gram import lexer

from Frontend import globals

from .emitter import BitEmitter, BitField
from .instructions import Instruction, Operand, ProgramIR
from .semantic import RuleRef, TableRef, TokenRef


class RIFRuntimeError(RuntimeError):
    """An execution failure associated with a MIR instruction."""


class _BreakFlow(Exception):
    pass


@dataclass(frozen=True)
class ExecutionResult:
    rule: str
    position: int
    last_token: lexer.TokenType | None
    stored_token: lexer.TokenType | None
    buffer: bytes


ExternalFunction = Callable[[], object]


class RIFMachine:
    """Execute the resolved subset of RIF instructions over input tokens."""

    def __init__(
        self,
        program: ProgramIR,
        *,
        emitter: BitEmitter | None = None,
        functions: Mapping[str, ExternalFunction] | None = None,
    ) -> None:
        self.program = program
        self.emitter = emitter or BitEmitter(
            wordsize=globals.CONFIG.wordsize if globals.CONFIG else 32
        )
        self.functions = dict(functions or {})
        self.tokens: tuple[lexer.TokenType, ...] = ()
        self.position = 0
        self.last_token: lexer.TokenType | None = None
        self.stored_token: lexer.TokenType | None = None
        self.storage: dict[str, lexer.TokenType] = {}
        self.selected_rows: dict[str, int] = {}
        self.last_call: object = None

    def execute(
        self,
        rule_name: str,
        tokens: Iterable[lexer.TokenType],
    ) -> ExecutionResult:
        if rule_name not in self.program.rules:
            raise RIFRuntimeError(f"La Rule '{rule_name}' no existe en el MIR.")
        self.tokens = tuple(tokens)
        self.position = 0
        self.last_token = None
        self.stored_token = None
        self.storage.clear()
        self.selected_rows.clear()
        self.last_call = None
        self._execute_rule(rule_name)
        return ExecutionResult(
            rule=rule_name,
            position=self.position,
            last_token=self.last_token,
            stored_token=self.stored_token,
            buffer=self.emitter.buffer.to_bytes(),
        )

    def _current(self) -> lexer.TokenType:
        if self.position >= len(self.tokens):
            raise RIFRuntimeError("Se alcanzó EOF mientras se ejecutaba una Rule.")
        token = self.tokens[self.position]
        if token.token == lexer.Token.EOF:
            raise RIFRuntimeError("Se alcanzó EOF mientras se ejecutaba una Rule.")
        return token

    @staticmethod
    def _matches_token(token: lexer.TokenType, reference: TokenRef) -> bool:
        return token.token == reference.token

    def _consume_token(self, reference: TokenRef) -> lexer.TokenType:
        token = self._current()
        if not self._matches_token(token, reference):
            raise RIFRuntimeError(
                f"Se esperaba Token.{reference.token.name}, pero se encontró "
                f"Token.{token.token.name} ({token.value!r})."
            )
        self.position += 1
        self.last_token = token
        return token

    def _table_value(self, reference: TableRef) -> Any:
        if reference.table not in self.selected_rows:
            raise RIFRuntimeError(
                f"La tabla '{reference.table}' no tiene una fila seleccionada."
            )
        table = globals.TABLES[reference.table]
        row = table.matrix[self.selected_rows[reference.table]]
        return row[reference.index]

    def _value(self, operand: Operand) -> Any:
        if operand.kind == "table_access":
            if not isinstance(operand.resolved, TableRef):
                raise RIFRuntimeError("TABLE_ACCESS no fue resuelto semánticamente.")
            return self._table_value(operand.resolved)
        if operand.kind == "reservation_access":
            return self.emitter.query(str(operand.value)).value
        if operand.kind == "call":
            function = self.functions.get(str(operand.value))
            if function is None:
                raise RIFRuntimeError(f"La función externa '{operand.value}' no existe.")
            self.last_call = function()
            return self.last_call
        return operand.value

    def _bit_field(self, operand: Operand) -> BitField | int | str:
        value = self._value(operand)
        if operand.kind == "number" and operand.width:
            return BitField(int(value), operand.width)
        if operand.kind == "bool":
            return BitField(1 if value else 0, 1)
        if operand.kind == "reservation_access":
            query = self.emitter.query(str(operand.value))
            return BitField(query.value, query.span.width)
        if operand.kind == "string" and isinstance(value, str) and set(value) <= {"0", "1"}:
            return value
        if operand.kind == "table_access" and isinstance(value, str):
            return value
        if isinstance(value, int):
            return value
        return str(value)

    def _frame_field(self, operand: Operand) -> BitField | str:
        value = self._value(operand)
        if operand.kind == "number" and operand.width:
            return BitField(int(value), operand.width)
        if operand.kind == "bool":
            return BitField(1 if value else 0, 1)
        if operand.kind == "reservation_access":
            query = self.emitter.query(str(operand.value))
            return BitField(query.value, query.span.width)
        if isinstance(value, str):
            return value
        if isinstance(value, int):
            return BitField(value, self.emitter.wordsize)
        raise RIFRuntimeError(f"El valor {value!r} no puede emitirse en un frame.")

    def _condition(self, operand: Operand) -> bool:
        if operand.kind == "bool":
            return bool(operand.value)
        if operand.kind == "call":
            function = self.functions.get(str(operand.value))
            if function is None:
                raise RIFRuntimeError(f"La función externa '{operand.value}' no existe.")
            self.last_call = function()
            if not isinstance(self.last_call, (bool, int, float)):
                raise RIFRuntimeError(
                    f"La función externa '{operand.value}' debe devolver bool o número."
                )
            return bool(self.last_call)
        raise RIFRuntimeError("La condición no es booleana ni una llamada externa.")

    def _execute_rule(self, rule_name: str) -> None:
        rule = self.program.rules[rule_name]
        try:
            for instruction in rule.instructions:
                self._execute_instruction(instruction)
        except _BreakFlow:
            return

    def _execute_instruction(self, instruction: Instruction) -> None:
        opcode = instruction.opcode
        operands = instruction.operands

        if opcode == "consumer":
            self._consume_token(operands[0].resolved)
            return

        if opcode == "table_matcher":
            table_ref = operands[0].resolved
            token_ref = operands[1].resolved
            if not isinstance(table_ref, TableRef) or not isinstance(token_ref, TokenRef):
                raise RIFRuntimeError("TABLE_MATCHER no fue resuelto semánticamente.")
            token = self._current()
            if not self._matches_token(token, token_ref):
                raise RIFRuntimeError(
                    f"TABLE_MATCHER esperaba Token.{token_ref.token.name}."
                )
            table = globals.TABLES[table_ref.table]
            for index, row in enumerate(table.matrix):
                if row[table_ref.index] == token.value:
                    self.selected_rows[table_ref.table] = index
                    self.position += 1
                    self.last_token = token
                    return
            raise RIFRuntimeError(
                f"El valor {token.value!r} no existe en "
                f"{table_ref.table}.{table_ref.column}."
            )

        if opcode == "store":
            token = self._current()
            refs = tuple(
                operand.resolved
                for operand in operands
                if isinstance(operand.resolved, TokenRef)
            )
            if not any(self._matches_token(token, reference) for reference in refs):
                raise RIFRuntimeError("STORE no encontró un token candidato.")
            self.position += 1
            self.last_token = token
            self.stored_token = token
            return

        if opcode == "put":
            self.emitter.put(self._bit_field(operands[0]), self._bit_field(operands[1]))
            return

        if opcode == "ebit":
            self.emitter.ebit(*(self._bit_field(operand) for operand in operands))
            return

        if opcode == "emmit":
            value = self._value(operands[0])
            if isinstance(value, bool) or not isinstance(value, (int, str, BitField)):
                raise RIFRuntimeError("EMMIT requiere un valor numérico o un campo binario.")
            self.emitter.emmit(value)
            return

        if opcode == "emitfr":
            rows = operands[0].value
            self.emitter.emitfr(
                tuple(tuple(self._frame_field(operand) for operand in row) for row in rows)
            )
            return

        if opcode == "kw":
            token = self._current()
            expected = operands[0].value
            if token.token != lexer.Token.KEYWORD or token.value != expected:
                raise RIFRuntimeError(f"KW esperaba {expected!r}.")
            self.position += 1
            self.last_token = token
            return

        if opcode == "jmp":
            reference = operands[0].resolved
            if not isinstance(reference, RuleRef):
                raise RIFRuntimeError("JMP no fue resuelto semánticamente.")
            self._execute_rule(reference.name)
            return

        if opcode == "jmpif":
            reference = operands[0].resolved
            if not isinstance(reference, RuleRef):
                raise RIFRuntimeError("JMPIF no fue resuelto semánticamente.")
            if self._condition(operands[1]):
                self._execute_rule(reference.name)
            return

        if opcode == "call":
            operand = operands[0]
            if operand.kind != "call":
                raise RIFRuntimeError("CALL requiere una función #call.")
            function = self.functions.get(str(operand.value))
            if function is None:
                raise RIFRuntimeError(f"La función externa '{operand.value}' no existe.")
            self.last_call = function()
            return

        if opcode == "break":
            raise _BreakFlow()

        if opcode == "error":
            raise RIFRuntimeError(str(operands[0].value))

        if opcode == "reserve":
            self.emitter.reserve(str(operands[0].value), int(operands[1].value))
            return

        if opcode == "ldres":
            self.emitter.ldres(str(operands[0].value), self._value(operands[1]))
            return

        if opcode == "gtres":
            self.emitter.gtres(str(operands[0].value))
            return

        if opcode == "dlres":
            self.emitter.dlres(str(operands[0].value))
            return

        if opcode == "save":
            self.storage[str(operands[0].value)] = self._current()
            return

        if opcode == "load":
            name = str(operands[0].value)
            if name not in self.storage:
                raise RIFRuntimeError(f"No existe token guardado bajo '{name}'.")
            saved = self.storage[name]
            current = self._current()
            if current.token != saved.token or current.value != saved.value:
                raise RIFRuntimeError(f"LOAD no coincide con el token guardado '{name}'.")
            self.position += 1
            self.last_token = current
            return

        raise NotImplementedError(f"El runtime todavía no implementa '{opcode}'.")


__all__ = ["RIFRuntimeError", "ExecutionResult", "RIFMachine"]
