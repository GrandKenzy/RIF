"""Generic line-oriented ``@block`` syntax."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from gram import combinators as cmb
from gram import lexer


@dataclass(frozen=True)
class RawBlock:
    """A generic block whose body is preserved for semantic processing."""

    block_name: str
    lines: tuple[tuple[lexer.TokenType, ...], ...]
    start: lexer.TokenType | None = None

    @property
    def name(self) -> str:
        return "BLOCK"


class BlockConsumer(cmb.Combinator):
    """Capture ``@block name:`` until its matching ``@end``."""

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
        return tuple(line) if line else None

    @staticmethod
    def _body(line: tuple[lexer.TokenType, ...]) -> tuple[lexer.TokenType, ...]:
        if line and line[-1].token == lexer.Token.NEWLINE:
            return line[:-1]
        return line

    def parse(self, analyzer: Any) -> RawBlock | None:
        parser = analyzer.parser
        checkpoint = parser.savepoint("RIF-GENERIC-BLOCK")
        first = parser.peek()
        second = parser.peek_dist(1)
        third = parser.peek_dist(2)
        fourth = parser.peek_dist(3)
        fifth = parser.peek_dist(4)
        if not (
            first is not None
            and second is not None
            and third is not None
            and fourth is not None
            and fifth is not None
            and first.token == lexer.Token.AT
            and second.value == "block"
            and third.token in {lexer.Token.IDENT, lexer.Token.KEYWORD}
            and fourth.token == lexer.Token.COLON
            and fifth.token == lexer.Token.NEWLINE
        ):
            return None

        header = self._consume_line(parser)
        if not header:
            parser.restore(checkpoint)
            return None

        lines: list[tuple[lexer.TokenType, ...]] = []
        while True:
            line = self._consume_line(parser)
            if line is None:
                parser.restore(checkpoint)
                return None
            body = self._body(line)
            if (
                len(body) == 2
                and body[0].token == lexer.Token.AT
                and body[1].value == "end"
            ):
                return RawBlock(
                    block_name=str(third.value),
                    lines=tuple(lines),
                    start=first,
                )
            lines.append(line)


class BLOCK(cmb.RuleItem):
    nodeable = False
    description = "Bloque genérico de nombres y hasta dos valores por línea."
    entrypoint = BlockConsumer()


__all__ = ["BLOCK", "BlockConsumer", "RawBlock"]
