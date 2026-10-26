"""Small executable runtime for the resolved RIF MIR."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from gram import lexer

from .emitter import BitEmitter, BitField
from .function_context import RIFFunctionContext
from .functions import FunctionModule, RIFFunctionError
from .instructions import CompiledRuleSet, Instruction, Operand
from .semantic import RuleRef, TableLookupRef, TableRef, TokenRef


MAX_RULE_CALL_DEPTH = 256


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
    """Physical and virtual spans produced by one Rule invocation."""

    name: str
    start: int
    bits: int
    end: int
    padding_bits: int
    virtual_start: int
    virtual_bits: int
    virtual_end: int
    virtual_padding_bits: int

    @property
    def emitted_bits(self) -> int:
        return self.bits


@dataclass
class _RuleTraceState:
    name: str
    start: int
    virtual_start: int
    padding_bits: int = 0
    virtual_padding_bits: int = 0


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
        self.context = program.context
        self.emitter = emitter or BitEmitter(
            wordsize=self.context.config.wordsize if self.context.config else 32
        )
        self.function_module = function_module
        self.function_context: RIFFunctionContext | None = None
        self.section_name = section_name
        self.tokens: tuple[lexer.TokenType, ...] = ()
        self.position = 0
        self.last_token: lexer.TokenType | None = None
        self.stored_token: lexer.TokenType | None = None
        self.storage: dict[str, lexer.TokenType] = {}
        self.stack: dict[int, Any] | None = (
            {} if self.context.stack_size is not None else None
        )
        self.datastack: list[Any] = []
        self.selected_rows: dict[str, int] = {}
        self.last_call: object = None
        self.rule_traces: list[RuleTrace] = []
        self.last_rule_trace: RuleTrace | None = None
        self.rule_addresses: dict[str, int] = {}
        self.virtual_rule_addresses: dict[str, int] = {}
        self.variant_stack: list[str] = []
        self._trace_stack: list[_RuleTraceState] = []
        self._rule_depth = 0

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
        self.datastack.clear()
        self.selected_rows.clear()
        self.rule_traces.clear()
        self.last_rule_trace = None
        self.rule_addresses.clear()
        self.virtual_rule_addresses.clear()
        self.variant_stack.clear()
        self._trace_stack.clear()
        self._rule_depth = 0
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
        table = self.context.tables[reference.table]
        row = table.matrix[self.selected_rows[reference.table]]
        return row[reference.index]

    def _table_lookup_value(self, reference: TableLookupRef) -> Any:
        table = self.context.tables[reference.table]
        try:
            row_index = table.index_for(reference.selector)[reference.key]
        except KeyError as exc:
            raise RIFRuntimeError(
                f"La clave {reference.key!r} no existe en "
                f"{reference.table}.{reference.selector}."
            ) from exc
        return table.matrix[row_index][reference.index]

    def _value(self, operand: Operand, source: Instruction | None = None) -> Any:
        if operand.kind == "data_pop":
            if not self.datastack:
                raise RIFRuntimeError("DLOAD requiere un valor en el datastack.")
            return self.datastack.pop()
        if operand.kind == "data_peek":
            if not self.datastack:
                raise RIFRuntimeError("DPEEK requiere un valor en el datastack.")
            return self.datastack[-1]
        if operand.kind == "data_depth":
            return len(self.datastack)
        if operand.kind == "size":
            return self.emitter.buffer.bit_length
        if operand.kind == "vsize":
            return self.emitter.virtual_position
        if operand.kind == "alignment":
            return self._current_alignment()
        if operand.kind in {
            "distance",
            "vdistance",
            "reservation_address",
            "reservation_vaddress",
            "reservation_distance",
            "reservation_vdistance",
            "reservation_width",
            "reservation_vwidth",
        }:
            return self._address_value(operand.kind, str(operand.value))
        if operand.kind == "table_access":
            if not isinstance(operand.resolved, TableRef):
                raise RIFRuntimeError("TABLE_ACCESS no fue resuelto semánticamente.")
            return self._table_value(operand.resolved)
        if operand.kind == "table_lookup":
            if not isinstance(operand.resolved, TableLookupRef):
                raise RIFRuntimeError("TABLE_LOOKUP no fue resuelto semánticamente.")
            return self._table_lookup_value(operand.resolved)
        if operand.kind == "reservation_access":
            return self.emitter.query(str(operand.value)).value
        if operand.kind == "call":
            self.last_call = self._call_external(str(operand.value), source or operand)
            return self.last_call
        return operand.value

    def _current_alignment(self) -> int:
        config = self.context.config
        if config is None:
            return 0
        section = self.section_name or config.defaultsection
        return config.sectionalign.get(section, 0)

    def _address_value(self, kind: str, name: str) -> int:
        regions = self.emitter.buffer.regions
        virtual = kind in {
            "vdistance",
            "reservation_vaddress",
            "reservation_vdistance",
            "reservation_vwidth",
        }
        if kind in {
            "reservation_address",
            "reservation_vaddress",
            "reservation_distance",
            "reservation_vdistance",
            "reservation_width",
            "reservation_vwidth",
        }:
            if virtual:
                try:
                    address = self.emitter.virtual_query(name).offset
                except KeyError as exc:
                    raise RIFRuntimeError(f"No existe una reserva virtual llamada '{name}'.") from exc
            else:
                if name not in regions:
                    raise RIFRuntimeError(f"No existe una reserva llamada '{name}'.")
                address = regions[name].offset
        else:
            if virtual and name in self.emitter.virtual_regions:
                address = self.emitter.virtual_query(name).offset
            elif virtual and name in self.virtual_rule_addresses:
                address = self.virtual_rule_addresses[name]
            elif not virtual and name in regions:
                address = regions[name].offset
            elif not virtual and name in self.rule_addresses:
                address = self.rule_addresses[name]
            else:
                raise RIFRuntimeError(f"No existe una reserva o etiqueta llamada '{name}'.")
        if kind in {"reservation_width", "reservation_vwidth"}:
            return self.emitter.virtual_query(name).width if virtual else regions[name].width
        if kind in {
            "distance",
            "vdistance",
            "reservation_distance",
            "reservation_vdistance",
        }:
            current = self.emitter.virtual_position if virtual else self.emitter.buffer.bit_length
            return current - address
        return address

    def _record_padding(self, width: int) -> None:
        if self._trace_stack:
            self._trace_stack[-1].padding_bits += width

    def _record_virtual_padding(self, width: int) -> None:
        if self._trace_stack:
            self._trace_stack[-1].virtual_padding_bits += width

    def _bit_integer(
        self, operand: Operand, source: Instruction, name: str, *, positive: bool
    ) -> int:
        value = self._value(operand, source)
        if isinstance(value, bool) or not isinstance(value, int) or value < (1 if positive else 0):
            minimum = "positivo" if positive else "no negativo"
            raise RIFRuntimeError(f"{name.capitalize()} debe ser un entero {minimum}.")
        return value

    def _fit_width(self, operand: Operand, source: Instruction) -> int:
        value = (
            self._value(Operand("data_peek", None), source)
            if operand.kind == "data_pop"
            else self._value(operand, source)
        )
        if isinstance(value, bool) or not isinstance(value, int):
            raise RIFRuntimeError("FIT requiere un ancho entero.")
        if value <= 0 or value % 2:
            raise RIFRuntimeError("FIT requiere un ancho positivo y múltiplo de dos.")
        return value

    @staticmethod
    def _immediate_fits(token: lexer.TokenType, width: int) -> bool:
        if token.token not in {lexer.Token.NUMBER, lexer.Token.DECIMAL, lexer.Token.STRING}:
            raise RIFRuntimeError(
                "FIT requiere que el token actual sea NUMBER, DECIMAL o STRING."
            )
        value = token.value
        if token.token == lexer.Token.STRING:
            if not isinstance(value, str) or not value or any(bit not in "01" for bit in value):
                raise RIFRuntimeError("FIT solo puede emitir strings binarios.")
            return len(value) <= width
        if token.token == lexer.Token.DECIMAL and isinstance(value, float) and value.is_integer():
            value = int(value)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise RIFRuntimeError("FIT requiere un inmediato entero no negativo.")
        return value < (1 << width)

    @staticmethod
    def _immediate_bits(token: lexer.TokenType, width: int, *, truncate: bool) -> int:
        if not RIFMachine._immediate_fits(token, width) and not truncate:
            value = token.value
            if token.token == lexer.Token.STRING:
                raise RIFRuntimeError(
                    f"El string binario tiene {len(value)} bits y no cabe en {width}."
                )
            raise RIFRuntimeError(f"El inmediato {value} no cabe en {width} bits.")
        value = token.value
        if token.token == lexer.Token.DECIMAL and isinstance(value, float) and value.is_integer():
            value = int(value)
        if token.token == lexer.Token.STRING:
            value = value[-width:] if truncate else value
            return int(value, 2)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise RIFRuntimeError("FIT requiere un inmediato entero no negativo.")
        return value & ((1 << width) - 1)

    def _emit_fit(self, operand: Operand, instruction: Instruction, *, exact: bool) -> None:
        width = self._fit_width(operand, instruction)
        token = self._current()
        value = self._immediate_bits(token, width, truncate=not exact)
        self.emitter.emit(value, width)
        if operand.kind == "data_pop":
            self.datastack.pop()
        self.position += 1
        self.last_token = token

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
        value = self._bit_field(operand, source)
        if isinstance(value, BitField):
            return value
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
        if self._rule_depth >= MAX_RULE_CALL_DEPTH:
            raise RIFRuntimeError(
                f"La profundidad de llamadas excede {MAX_RULE_CALL_DEPTH} Rules."
            )
        rule = self.program.rules[rule_name]
        frame = _RuleTraceState(
            rule_name,
            self.emitter.buffer.bit_length,
            self.emitter.virtual_position,
        )
        self.rule_addresses.setdefault(rule_name, frame.start)
        self.virtual_rule_addresses.setdefault(rule_name, frame.virtual_start)
        self._trace_stack.append(frame)
        self._rule_depth += 1
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
                virtual_start=frame.virtual_start,
                virtual_bits=self.emitter.virtual_position - frame.virtual_start,
                virtual_end=self.emitter.virtual_position,
                virtual_padding_bits=frame.virtual_padding_bits,
            )
            self.rule_traces.append(trace)
            self.last_rule_trace = trace
            self._trace_stack.pop()
            self._rule_depth -= 1

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
            table = self.context.tables[table_ref.table]
            try:
                index = table.index_for(table_ref.column).get(token.value)
            except (TypeError, ValueError) as exc:
                raise RIFRuntimeError(str(exc)) from exc
            if index is not None:
                self.selected_rows[table_ref.table] = index
                self.position += 1
                self.last_token = token
                return
            raise RIFRuntimeError(
                f"El valor {token.value!r} no existe en "
                f"{table_ref.table}.{table_ref.column}."
            )

        if opcode == "dload":
            references = operands[0].resolved
            if not isinstance(references, tuple) or len(references) != 2 or not all(isinstance(ref, TableRef) for ref in references):
                raise RIFRuntimeError("DLOAD no fue resuelto semánticamente.")
            selector, field = references
            token = self._current()
            table = self.context.tables[selector.table]
            try:
                row_index = table.index_for(selector.column).get(token.value)
            except TypeError as exc:
                raise RIFRuntimeError("El token actual no es indexable en la tabla.") from exc
            if row_index is None:
                raise RIFRuntimeError(
                    f"El valor {token.value!r} no existe en {selector.table}.{selector.column}."
                )
            self.datastack.append(table.matrix[row_index][field.index])
            self.selected_rows[selector.table] = row_index
            self.position += 1
            self.last_token = token
            return

        if opcode == "dsave":
            self.datastack.append(self._value(operands[0], instruction))
            return

        if opcode == "dpop":
            self._value(Operand("data_pop", None), instruction)
            return

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

        if opcode == "fits":
            self._emit_fit(operands[0], instruction, exact=False)
            return

        if opcode == "iffits":
            self._emit_fit(operands[0], instruction, exact=True)
            return

        if opcode == "ifnfits":
            width = self._fit_width(operands[0], instruction)
            token = self._current()
            if not self._immediate_fits(token, width):
                if operands[0].kind == "data_pop":
                    self.datastack.pop()
                self.position += 1
                self.last_token = token
                return
            raise RIFRuntimeError(f"El inmediato cabe en {width} bits; IFNFITS falló.")

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

        if opcode == "vpadding":
            width = int(operands[0].value)
            self.emitter.vpadding(width)
            self._record_virtual_padding(width)
            return

        if opcode == "valignement":
            alignment = int(operands[0].value)
            width = (-self.emitter.virtual_position) % alignment
            if width:
                self.emitter.vpadding(width)
                self._record_virtual_padding(width)
            return

        if opcode in {"emitbits", "readbits", "patchbits"}:
            try:
                if opcode == "emitbits":
                    value = self._value(operands[0], instruction)
                    width = self._bit_integer(operands[1], instruction, "ancho", positive=True)
                    self.emitter.emit(value, width)
                else:
                    offset = self._bit_integer(operands[0], instruction, "offset", positive=False)
                    width = self._bit_integer(operands[1], instruction, "ancho", positive=True)
                    if opcode == "readbits":
                        self.datastack.append(self.emitter.read_bits(offset, width))
                    else:
                        self.emitter.patch_bits(offset, width, self._value(operands[2], instruction))
            except (ValueError, TypeError) as exc:
                raise RIFRuntimeError(str(exc)) from exc
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

        if opcode == "vreserve":
            self.emitter.vreserve(str(operands[0].value), int(operands[1].value))
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


__all__ = [
    "MAX_RULE_CALL_DEPTH",
    "RIFRuntimeError",
    "ExecutionResult",
    "RuleTrace",
    "RIFMachine",
]
