"""Line-oriented top-level binary artifacts.

The payload grammar is intentionally captured without recursive combinators.
The semantic visitor can then validate byte strings, paths, native queries and
patch expressions in one place while the parser remains newline-delimited.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from gram import combinators as cmb
from gram import lexer


@dataclass(frozen=True)
class RawArtifactBlock:
    """One ``@insert`` or ``@before`` block, preserving its source tokens."""

    kind: str
    lines: tuple[tuple[lexer.TokenType, ...], ...]
    start: lexer.TokenType | None = None

    @property
    def name(self) -> str:
        return self.kind.upper()


class ArtifactBlockConsumer(cmb.Combinator):
    """Consume one complete top-level artifact block by line boundaries."""

    _KINDS = {"insert", "before"}

    @staticmethod
    def _consume_line(parser: Any) -> tuple[lexer.TokenType, ...] | None:
        line: list[lexer.TokenType] = []
        while not parser.is_eof():
            token = parser.peek()
            if token is None or token.token == lexer.Token.EOF:
                break
            line.append(parser.consume())
            if token.token == lexer.Token.NEWLINE:
                return tuple(line)
        return tuple(line) if line else None

    @staticmethod
    def _body(line: tuple[lexer.TokenType, ...]) -> tuple[lexer.TokenType, ...]:
        if line and line[-1].token == lexer.Token.NEWLINE:
            return line[:-1]
        return line

    def parse(self, analyzer: Any) -> RawArtifactBlock | None:
        parser = analyzer.parser
        checkpoint = parser.savepoint("RIF-ARTIFACT-BLOCK")

        first = parser.peek()
        second = parser.peek_dist(1)
        third = parser.peek_dist(2)
        if (
            first is None
            or second is None
            or third is None
            or first.token != lexer.Token.AT
            or second.value not in self._KINDS
            or third.token != lexer.Token.COLON
        ):
            return None

        first_line = self._consume_line(parser)
        if not first_line:
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
                return RawArtifactBlock(
                    kind=str(second.value),
                    lines=tuple(lines),
                    start=first,
                )
            lines.append(line)


class ARTIFACT_BLOCK(cmb.RuleItem):
    nodeable = False
    description = "Consume un bloque superior de inserts o parches finales."
    entrypoint = ArtifactBlockConsumer()


__all__ = ["RawArtifactBlock", "ArtifactBlockConsumer", "ARTIFACT_BLOCK"]
