"""Line-oriented instruction consumption for RIF Rule bodies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from gram import combinators as cmb
from gram import lexer

from ..keywords import INSTRUCTION_OPCODES


@dataclass(frozen=True)
class RawInstruction:
    """One logical RIF instruction captured without recursive combinators."""

    opcode: str
    lines: tuple[tuple[lexer.TokenType, ...], ...]

    @property
    def tokens(self) -> tuple[lexer.TokenType, ...]:
        return tuple(token for line in self.lines for token in line)

    @property
    def start(self) -> lexer.TokenType | None:
        return self.tokens[0] if self.tokens else None


class InstructionConsumer(cmb.Combinator):
    """Consume one complete instruction, stopping only at line boundaries."""

    _KEYWORDS = INSTRUCTION_OPCODES

    @staticmethod
    def _consume_line(parser: Any) -> tuple[lexer.TokenType, ...] | None:
        line: list[lexer.TokenType] = []
        while not parser.is_eof():
            token = parser.peek()
            if token is None:
                return None
            line.append(parser.consume())
            if token.token == lexer.Token.NEWLINE:
                return tuple(line)
        return None

    @staticmethod
    def _is_frame_end(parser: Any) -> bool:
        first = parser.peek()
        second = parser.peek_dist(1)
        return bool(
            first is not None
            and second is not None
            and first.token == lexer.Token.ARROW
            and second.token == lexer.Token.KEYWORD
            and second.value == "emitfrend"
        )

    def parse(self, analyzer: Any) -> RawInstruction | None:
        parser = analyzer.parser
        checkpoint = parser.savepoint("RIF-INSTRUCTION-CONSUMER")
        first = parser.peek()
        if first is None or first.token != lexer.Token.ARROW:
            return None

        first_line = self._consume_line(parser)
        if not first_line or len(first_line) < 2:
            parser.restore(checkpoint)
            return None

        body = first_line[1:-1]  # remove ARROW and NEWLINE
        if not body:
            parser.restore(checkpoint)
            return None

        if body[0].token == lexer.Token.DOLLAR:
            opcode = "table_matcher"
        elif body[0].token == lexer.Token.LBRACKET:
            opcode = "store"
        elif body[0].token == lexer.Token.KEYWORD:
            opcode = self._KEYWORDS.get(str(body[0].value))
            if opcode is None:
                if lexer.Token.from_string(str(body[0].value)) is None:
                    parser.restore(checkpoint)
                    return None
                opcode = "consumer"
        elif body[0].token in {lexer.Token.NUMBER, lexer.Token.DECIMAL, lexer.Token.IDENT}:
            opcode = "consumer"
        else:
            parser.restore(checkpoint)
            return None

        lines = [first_line]
        if opcode == "emitfr":
            while True:
                if parser.is_eof() or self._is_frame_end(parser):
                    break
                line = self._consume_line(parser)
                if not line or all(token.token == lexer.Token.NEWLINE for token in line):
                    parser.restore(checkpoint)
                    return None
                lines.append(line)
            if not self._is_frame_end(parser):
                parser.restore(checkpoint)
                return None
            end_line = self._consume_line(parser)
            if not end_line:
                parser.restore(checkpoint)
                return None
            lines.append(end_line)

        return RawInstruction(opcode=opcode, lines=tuple(lines))


class INSTRUCTION(cmb.RuleItem):
    nodeable = False
    description = "Consume una instrucción RIF completa por líneas."
    entrypoint = InstructionConsumer()


__all__ = ["RawInstruction", "InstructionConsumer", "INSTRUCTION"]
