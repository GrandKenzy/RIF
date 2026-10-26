"""Small semantic adapter for RIF bit-emitting instructions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Sequence

from .bitbuffer import BitBuffer, BitLayout, BitQuery, BitSpan


@dataclass(frozen=True)
class BitField:
    value: int
    width: int


def field(value: int | str | BitField, width: int | None = None) -> BitField:
    """Normalize a literal while preserving binary strings such as ``0000``."""

    if isinstance(value, BitField):
        if width is not None and value.width != width:
            raise ValueError("El ancho del campo no coincide con el esperado.")
        return value
    if isinstance(value, str):
        if not value or any(bit not in "01" for bit in value):
            raise ValueError("Un campo binario debe contener solamente 0 y 1.")
        inferred = len(value)
        if width is not None and inferred != width:
            raise ValueError(
                f"El campo binario tiene {inferred} bits; se esperaban {width}."
            )
        return BitField(int(value, 2), inferred)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("El campo debe ser un entero, string binario o BitField.")
    if width is None:
        raise ValueError("Un entero requiere un ancho explícito.")
    if value < 0 or value >= (1 << width):
        raise ValueError(f"El valor {value} no cabe en {width} bits.")
    return BitField(value, width)


class BitEmitter:
    """Implements the bit-oriented RIF operations over a BitBuffer."""

    def __init__(
        self,
        buffer: BitBuffer | None = None,
        *,
        wordsize: int = 32,
        layout: BitLayout | None = None,
    ) -> None:
        if wordsize <= 0:
            raise ValueError("wordsize debe ser mayor que cero.")
        self.buffer = buffer if buffer is not None else BitBuffer(layout)
        self.wordsize = wordsize

    @classmethod
    def from_config(cls, config: object) -> "BitEmitter":
        """Build an emitter from the fields already materialized by RIF config."""

        return cls(
            wordsize=int(getattr(config, "wordsize")),
            layout=BitLayout(
                bit_order=str(getattr(config, "bitorder", "msb")),
                byte_order=str(getattr(config, "endianness")),
            ),
        )

    def put(self, first: int | str | BitField, second: int | str | BitField) -> tuple[BitSpan, BitSpan]:
        left = field(first, 4)
        right = field(second, 4)
        return (
            self.buffer.append_bits(left.value, left.width),
            self.buffer.append_bits(right.value, right.width),
        )

    def ebit(self, *values: int | str | BitField) -> tuple[BitSpan, ...]:
        if len(values) != 8:
            raise ValueError("ebit requiere exactamente ocho campos de un bit.")
        return tuple(
            self.buffer.append_bits(field(value, 1).value, 1) for value in values
        )

    def emmit(self, value: int | str | BitField) -> BitSpan:
        item = field(value, self.wordsize)
        if item.width % 8 == 0:
            return self.buffer.append_int(item.value, item.width)
        return self.buffer.append_bits(item.value, item.width)

    def reserve(self, name: str, width: int) -> BitSpan:
        return self.buffer.reserve(name, width)

    def ldres(self, name: str, value: int | str | BitField) -> None:
        span = self.buffer.query(name).span
        item = field(value, span.width)
        self.buffer.patch(span, item.value)

    def gtres(self, name: str) -> BitSpan:
        return self.buffer.copy_region(name)

    def dlres(self, name: str) -> BitSpan:
        return self.buffer.drop_region(name)

    def query(self, span_or_name: BitSpan | str) -> BitQuery:
        return self.buffer.query(span_or_name)

    def emitfr(self, rows: Iterable[Sequence[int | str | BitField]]) -> tuple[BitSpan, ...]:
        """Emit a multiline frame atomically after validating every field."""

        normalized: list[tuple[BitField, ...]] = []
        for row in rows:
            current = tuple(field(value) for value in row)
            if not current:
                raise ValueError("emitfr no admite filas vacías.")
            normalized.append(current)
        if not normalized:
            raise ValueError("emitfr requiere al menos una fila.")

        spans: list[BitSpan] = []
        with self.buffer.transaction():
            for row in normalized:
                for item in row:
                    spans.append(self.buffer.append_bits(item.value, item.width))
        return tuple(spans)


__all__ = ["BitField", "field", "BitEmitter"]
