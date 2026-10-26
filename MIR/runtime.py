"""Small executable runtime for the resolved RIF MIR."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from gram import lexer

from Frontend import globals

from .emitter import BitEmitter, BitField
from .function_context import RIFFunctionContext
from .functions import FunctionModule, RIFFunctionError
from .instructions import CompiledRuleSet, Instruction, Operand
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


@dataclass(frozen=True)
class RuleTrace:
    """Physical output span produced by one Rule invocation."""

    name: str
    start: int
    bits: int
    end: int
    padding_bits: int

    @property
    def emitted_bits(self) -> int:
        return self.bits


@dataclass
class _RuleTraceState:
    name: str
    start: int
    padding_bits: int = 0


class RIFMachine:
    """Execute the resolved subset of RIF instructions over input tokens."""

    def __init__(
        self,
        program: CompiledRuleSet,
        *,
        emitter: BitEmitter | None = None,
        function_module: FunctionModule | None = None,
        section_name: str | None = None,
    ) -> None:
        self.program = program
        self.emitter = emitter or BitEmitter(
            wordsize=globals.CONFIG.wordsize if globals.CONFIG else 32
        )
        self.function_module = function_module
        self.function_context: RIFFunctionContext | None = None
        self.section_name = section_name
        self.tokens: tuple[lexer.TokenType, ...] = ()
        self.position = 0
        self.last_token: lexer.TokenType | None = None
        self.stored_token: lexer.TokenType | None = None
        self.storage: dict[str, lexer.TokenType] = {}
        self.selected_rows: dict[str, int] = {}
        self.last_call: object = None
        self.rule_traces: list[RuleTrace] = []
        self.last_rule_trace: RuleTrace | None = None
        self.rule_addresses: dict[str, int] = {}
        self._trace_stack: list[_RuleTraceState] = []

    def bind_function_context(self, context: RIFFunctionContext) -> None:
        """Bind the live context passed to ``funcs.py``."""

        self.function_context = context

    def execute(
        self,
        rule_name: str,
        tokens: Iterable[lexer.TokenType],
    ) -> ExecutionResult:
        if rule_name not in self.program.rules:
            raise RIFRuntimeError(f"La Rule '{rule_name}' no existe en el MIR.")
        self.storage.clear()
        self.selected_rows.clear()
        self.rule_traces.clear()
        self.last_rule_trace = None
        self.rule_addresses.clear()
        self._trace_stack.clear()
        return self.execute_line(rule_name, tokens)

    def execute_line(
        self,
        rule_name: str,
        tokens: Iterable[lexer.TokenType],
    ) -> ExecutionResult:
        """Execute one external MIR instruction while keeping machine state.

        ``execute`` starts a fresh standalone run. External MIR programs use
        this method for each logical line so reservations, saved tokens and
        selected table rows can survive between instructions.
        """
        if rule_name not in self.program.rules:
            raise RIFRuntimeError(f"La Rule '{rule_name}' no existe en el MIR.")
        self.tokens = tuple(tokens)
        self.position = 0
        self.last_token = None
        self.stored_token = None
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

    def _value(self, operand: Operand, source: Instruction | None = None) -> Any:
        if operand.kind == "size":
            return self.emitter.buffer.bit_length
        if operand.kind == "vsize":
            return self.emitter.buffer.bit_length
        if operand.kind == "alignment":
            return self._current_alignment()
        if operand.kind in {
            "distance",
            "vdistance",
            "reservation_address",
            "reservation_vaddress",
            "reservation_distance",
            "reservation_vdistance",
        }:
            return self._address_value(operand.kind, str(operand.value))
        if operand.kind == "table_access":
            if not isinstance(operand.resolved, TableRef):
                raise RIFRuntimeError("TABLE_ACCESS no fue resuelto semánticamente.")
            return self._table_value(operand.resolved)
        if operand.kind == "reservation_access":
            return self.emitter.query(str(operand.value)).value
        if operand.kind == "call":
            self.last_call = self._call_external(str(operand.value), source or operand)
            return self.last_call
        return operand.value

    def _current_alignment(self) -> int:
        config = globals.CONFIG
        if config is None:
            return 0
        section = self.section_name or config.defaultsection
        return config.sectionalign.get(section, 0)

    def _address_value(self, kind: str, name: str) -> int:
        regions = self.emitter.buffer.regions
        if kind in {"reservation_address", "reservation_vaddress", "reservation_distance", "reservation_vdistance"}:
            if name not in regions:
                raise RIFRuntimeError(f"No existe una reserva llamada '{name}'.")
            address = regions[name].offset
        else:
            if name in regions:
                address = regions[name].offset
            elif name in self.rule_addresses:
                address = self.rule_addresses[name]
            else:
                raise RIFRuntimeError(f"No existe una reserva o etiqueta llamada '{name}'.")
        if kind in {"distance", "vdistance", "reservation_distance", "reservation_vdistance"}:
            return self.emitter.buffer.bit_length - address
        return address

    def _record_padding(self, width: int) -> None:
        if self._trace_stack:
            self._trace_stack[-1].padding_bits += width

    def _call_external(self, name: str, source: Operand | Instruction) -> bool | str:
        if self.function_module is None:
            raise RIFRuntimeError(
                f"La llamada Python '{name}' requiere un archivo funcs.py cargado."
            )
        context = self.function_context
        if context is None:
            context = RIFFunctionContext(
                program=self.program,
                machine=self,
                image=None,
                section=None,
            )
            self.function_context = context
        try:
            return self.function_module.invoke(name, context)
        except RIFFunctionError as exc:
            if isinstance(source, Instruction):
                location = source.span.path or "<memoria>"
                if source.span.line is not None:
                    location += f":{source.span.line}:{source.span.column or 0}"
                raise RIFRuntimeError(f"{location}: {exc}") from exc
            raise RIFRuntimeError(str(exc)) from exc

    def _bit_field(
        self,
        operand: Operand,
        source: Instruction | None = None,
    ) -> BitField | int | str:
        value = self._value(operand, source)
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

    def _frame_field(
        self,
        operand: Operand,
        source: Instruction | None = None,
    ) -> BitField | str:
        value = self._value(operand, source)
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

    def _condition(self, operand: Operand, source: Instruction | None = None) -> bool:
        if operand.kind == "bool":
            return bool(operand.value)
        if operand.kind == "call":
            self.last_call = self._call_external(str(operand.value), source or operand)
            if not isinstance(self.last_call, bool):
                raise RIFRuntimeError(
                    f"La función Python '{operand.value}' debe devolver True o False "
                    "cuando se usa como condición."
                )
            return self.last_call
        raise RIFRuntimeError("La condición no es booleana ni una llamada externa.")

    def _execute_rule(self, rule_name: str) -> None:
        rule = self.program.rules[rule_name]
        frame = _RuleTraceState(rule_name, self.emitter.buffer.bit_length)
        self.rule_addresses[rule_name] = frame.start
        self._trace_stack.append(frame)
        try:
            for instruction in rule.instructions:
                self._execute_instruction(instruction)
        except _BreakFlow:
            return
        finally:
            end = self.emitter.buffer.bit_length
            trace = RuleTrace(
                name=frame.name,
                start=frame.start,
                bits=end - frame.start,
                end=end,
                padding_bits=frame.padding_bits,
            )
            self.rule_traces.append(trace)
            self.last_rule_trace = trace
            self._trace_stack.pop()

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
            self.emitter.put(
                self._bit_field(operands[0], instruction),
                self._bit_field(operands[1], instruction),
            )
            return

        if opcode == "ebit":
            self.emitter.ebit(
                *(self._bit_field(operand, instruction) for operand in operands)
            )
            return

        if opcode == "emmit":
            value = self._value(operands[0], instruction)
            if isinstance(value, bool) or not isinstance(value, (int, str, BitField)):
                raise RIFRuntimeError("EMMIT requiere un valor numérico o un campo binario.")
            self.emitter.emmit(value)
            return

        if opcode == "padding":
            width = int(operands[0].value)
            self.emitter.padding(width)
            self._record_padding(width)
            return

        if opcode == "alignement":
            alignment = int(operands[0].value)
            remainder = self.emitter.buffer.bit_length % alignment
            width = 0 if remainder == 0 else alignment - remainder
            if width:
                self.emitter.padding(width)
                self._record_padding(width)
            return

        if opcode == "emitfr":
            rows = operands[0].value
            self.emitter.emitfr(
                tuple(
                    tuple(self._frame_field(operand, instruction) for operand in row)
                    for row in rows
                )
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
            if self._condition(operands[1], instruction):
                self._execute_rule(reference.name)
            return

        if opcode == "call":
            operand = operands[0]
            if operand.kind != "call":
                raise RIFRuntimeError("CALL requiere una función #call.")
            self.last_call = self._call_external(str(operand.value), instruction)
            return

        if opcode == "break":
            raise _BreakFlow()

        if opcode == "error":
            raise RIFRuntimeError(str(operands[0].value))

        if opcode == "reserve":
            self.emitter.reserve(str(operands[0].value), int(operands[1].value))
            return

        if opcode == "ldres":
            self.emitter.ldres(
                str(operands[0].value),
                self._value(operands[1], instruction),
            )
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


__all__ = ["RIFRuntimeError", "ExecutionResult", "RuleTrace", "RIFMachine"]
