"""Target-extensible relocation specifications."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from Frontend import globals
from .operations import OperationError, execute_operation


@dataclass(frozen=True)
class RelocationSpec:
    """A target-neutral relocation calculation declared by name."""

    name: str
    width_bits: int
    mode: str

    @property
    def relative(self) -> bool:
        return self.mode in {"pc", "arm_pc24"}

    def encode(self, value: int) -> int:
        if self.mode == "arm_pc24":
            # ARM B/BL use the architectural PC (instruction address + 8),
            # while RIF records the address of the next emitted instruction.
            value -= 4
            if value % 4:
                raise ValueError(
                    f"{self.name}: el destino ARM no está alineado a una palabra."
                )
            value //= 4
            mode = "pc"
        else:
            mode = "pc" if self.relative else "abs"
        try:
            return execute_operation(
                "encode_relocation", value, self.width_bits, mode
            )
        except OperationError as exc:
            raise ValueError(f"{self.name}: {exc}") from exc


_BUILTINS: Mapping[str, RelocationSpec] = {
    **{
        f"pc{width}": RelocationSpec(f"pc{width}", width, "pc")
        for width in (8, 16, 32, 64)
    },
    **{
        f"abs{width}": RelocationSpec(f"abs{width}", width, "abs")
        for width in (8, 16, 32, 64)
    },
}


def _block_value(entry: globals.BlockEntryData, index: int) -> object:
    try:
        return entry.values[index].value
    except IndexError as exc:
        raise ValueError(
            f"La relocación '{entry.name}' requiere ancho y modo."
        ) from exc


def relocation_specs(context: globals.TargetContext) -> dict[str, RelocationSpec]:
    """Return built-ins plus declarations from ``@block relocations``.

    Each generic block line is ``name width mode``. ``mode`` is ``pc`` for a
    signed displacement from the next virtual instruction byte, ``abs`` for
    an unsigned absolute virtual address, or ``arm_pc24`` for an ARM branch
    displacement (PC+8, word-scaled, signed). The declaration is deliberately
    independent of any ISA except for explicitly named target modes.
    """

    specs = dict(_BUILTINS)
    for block in context.blocks.get("relocations", ()):
        for entry in block.entries:
            if len(entry.values) != 2:
                raise ValueError(
                    f"La relocación '{entry.name}' requiere ancho y modo."
                )
            width = _block_value(entry, 0)
            mode = str(_block_value(entry, 1)).casefold()
            if isinstance(width, bool) or not isinstance(width, int):
                raise ValueError(
                    f"El ancho de la relocación '{entry.name}' debe ser entero."
                )
            if width <= 0 or width % 8:
                raise ValueError(
                    f"El ancho de la relocación '{entry.name}' debe ser positivo y múltiplo de ocho."
                )
            if mode in {"relative", "pcrel", "pc"}:
                mode = "pc"
            elif mode in {"arm_pc24", "arm-branch24", "arm_branch24"}:
                mode = "arm_pc24"
            elif mode in {"absolute", "abs"}:
                mode = "abs"
            else:
                raise ValueError(f"El modo de la relocación '{entry.name}' no es válido.")
            name = entry.name
            if not name or name in specs:
                raise ValueError(f"La relocación '{name}' está duplicada.")
            specs[name] = RelocationSpec(name, width, mode)
    return specs


def relocation_spec(context: globals.TargetContext, name: str) -> RelocationSpec:
    try:
        return relocation_specs(context)[name]
    except KeyError as exc:
        raise ValueError(f"Clase de relocación desconocida: {name!r}.") from exc


__all__ = ["RelocationSpec", "relocation_spec", "relocation_specs"]
