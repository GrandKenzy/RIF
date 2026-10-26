"""Flat intermediate representation for compiled RIF Rules."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class SourceSpan:
    path: str | None
    line: int | None
    column: int | None


@dataclass(frozen=True)
class Operand:
    kind: str
    value: Any
    raw: str | None = None
    width: int | None = None
    resolved: Any = None


@dataclass(frozen=True)
class Instruction:
    opcode: str
    operands: tuple[Operand, ...]
    span: SourceSpan
    source_node: Any = None


@dataclass(frozen=True)
class RuleIR:
    name: str
    instructions: tuple[Instruction, ...]
    source_path: str | None = None


@dataclass(frozen=True)
class ProgramIR:
    rules: dict[str, RuleIR]


__all__ = ["SourceSpan", "Operand", "Instruction", "RuleIR", "ProgramIR"]
