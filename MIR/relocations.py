"""Target-declared, ISA-neutral relocation recipes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from Frontend import globals
from .operations import OperationError, execute_operation


def _integer(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{name} debe ser un entero.")
    return value


def _positive(value: Any, name: str) -> int:
    value = _integer(value, name)
    if value <= 0:
        raise ValueError(f"{name} debe ser positivo.")
    return value


def _mask(width: int) -> int:
    return (1 << width) - 1


@dataclass(frozen=True)
class RelocationField:
    """One source bit range placed into the output word."""

    source_shift: int
    width_bits: int
    target_shift: int

    def __post_init__(self) -> None:
        source_shift = _integer(self.source_shift, "source_shift")
        width_bits = _positive(self.width_bits, "width_bits")
        target_shift = _integer(self.target_shift, "target_shift")
        if source_shift < 0 or target_shift < 0:
            raise ValueError("Los desplazamientos de un campo no pueden ser negativos.")
        object.__setattr__(self, "source_shift", source_shift)
        object.__setattr__(self, "width_bits", width_bits)
        object.__setattr__(self, "target_shift", target_shift)


@dataclass(frozen=True)
class RelocationSpec:
    """A declarative relocation recipe independent of any instruction set.

    ``value`` received by :meth:`encode` is the target address minus the
    recorded next-instruction address. ``pc_bias`` is subtracted from that
    value before scaling. Fields can copy non-contiguous source bits into a
    fixed output template.
    """

    name: str
    width_bits: int
    mode: str
    pc_bias: int = 0
    scale: int = 1
    alignment: int = 1
    signed: bool | None = None
    template: int = 0
    fields: tuple[RelocationField, ...] = ()

    def __post_init__(self) -> None:
        name = str(self.name)
        if not name:
            raise ValueError("Una relocación requiere un nombre.")
        width_bits = _positive(self.width_bits, "width_bits")
        mode = str(self.mode).casefold()
        if mode in {"relative", "pcrel"}:
            mode = "pc"
        elif mode == "absolute":
            mode = "abs"
        if mode not in {"pc", "abs"}:
            raise ValueError(f"El modo de la relocación '{name}' no es válido.")
        pc_bias = _integer(self.pc_bias, "pc_bias")
        scale = _positive(self.scale, "scale")
        alignment = _positive(self.alignment, "alignment")
        template = _integer(self.template, "template")
        if template < 0 or template >= 1 << width_bits:
            raise ValueError(f"La plantilla de '{name}' no cabe en {width_bits} bits.")
        signed = self.signed
        if signed is not None and not isinstance(signed, bool):
            raise ValueError("signed debe ser booleano o None.")
        fields = tuple(self.fields)
        if any(not isinstance(field, RelocationField) for field in fields):
            raise ValueError("fields solo puede contener RelocationField.")
        if not fields and template:
            raise ValueError(
                f"La plantilla de '{name}' requiere al menos un campo de salida."
            )
        for field in fields:
            if field.target_shift + field.width_bits > width_bits:
                raise ValueError(
                    f"El campo de '{name}' excede la salida de {width_bits} bits."
                )
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "width_bits", width_bits)
        object.__setattr__(self, "mode", mode)
        object.__setattr__(self, "pc_bias", pc_bias)
        object.__setattr__(self, "scale", scale)
        object.__setattr__(self, "alignment", alignment)
        object.__setattr__(self, "signed", signed if signed is not None else mode == "pc")
        object.__setattr__(self, "template", template)
        object.__setattr__(self, "fields", fields)

    @property
    def relative(self) -> bool:
        return self.mode == "pc"

    def encode(self, value: int) -> int:
        value = _integer(value, "value")
        adjusted = value - self.pc_bias if self.relative else value
        if adjusted % self.alignment:
            raise ValueError(
                f"{self.name}: el desplazamiento no respeta la alineación "
                f"de {self.alignment} bytes."
            )
        if adjusted % self.scale:
            raise ValueError(
                f"{self.name}: el desplazamiento no puede escalarse por {self.scale}."
            )
        scaled = adjusted // self.scale
        source_width = (
            max((field.source_shift + field.width_bits for field in self.fields), default=0)
            or self.width_bits
        )
        if self.signed:
            limit = 1 << (source_width - 1)
            if not -limit <= scaled < limit:
                raise ValueError(
                    f"{self.name}: el valor signed no cabe en {source_width} bits."
                )
        elif not 0 <= scaled < 1 << source_width:
            raise ValueError(
                f"{self.name}: el valor unsigned no cabe en {source_width} bits."
            )

        if not self.fields:
            try:
                return execute_operation(
                    "encode_relocation",
                    scaled,
                    self.width_bits,
                    "pc" if self.signed else "abs",
                )
            except OperationError as exc:
                raise ValueError(f"{self.name}: {exc}") from exc

        encoded = self.template
        for field in self.fields:
            field_mask = _mask(field.width_bits)
            target_mask = field_mask << field.target_shift
            field_value = (scaled >> field.source_shift) & field_mask
            encoded = (encoded & ~target_mask) | (field_value << field.target_shift)
        return encoded


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


def _table_value(table: globals.TableData, row: tuple[Any, ...], column: str) -> Any:
    try:
        return row[table.columns[column]]
    except KeyError as exc:
        raise ValueError(
            f"La tabla '{table.name}' requiere la columna '{column}'."
        ) from exc


def _optional_table_value(
    table: globals.TableData,
    row: tuple[Any, ...],
    column: str,
    default: Any,
) -> Any:
    if column not in table.columns:
        return default
    return row[table.columns[column]]


def _field_table(context: globals.TargetContext) -> dict[str, tuple[RelocationField, ...]]:
    table = context.tables.get("relocation_fields")
    if table is None:
        return {}
    required = {"relocation", "source_shift", "width", "target_shift"}
    missing = sorted(required - set(table.columns))
    if missing:
        raise ValueError(
            "La tabla 'relocation_fields' requiere las columnas: "
            + ", ".join(missing)
            + "."
        )
    fields: dict[str, list[RelocationField]] = {}
    for row in table.matrix:
        name = _table_value(table, row, "relocation")
        if not isinstance(name, str) or not name:
            raise ValueError("relocation_fields.relocation debe ser un nombre.")
        fields.setdefault(name, []).append(
            RelocationField(
                _table_value(table, row, "source_shift"),
                _table_value(table, row, "width"),
                _table_value(table, row, "target_shift"),
            )
        )
    return {name: tuple(items) for name, items in fields.items()}


def _table_specs(
    context: globals.TargetContext,
    existing: Mapping[str, RelocationSpec],
) -> dict[str, RelocationSpec]:
    table = context.tables.get("relocations")
    if table is None:
        orphan_fields = _field_table(context)
        if orphan_fields:
            raise ValueError(
                "relocation_fields requiere una tabla 'relocations' con sus recetas."
            )
        return {}
    required = {"name", "width", "mode"}
    missing = sorted(required - set(table.columns))
    if missing:
        raise ValueError(
            "La tabla 'relocations' requiere las columnas: "
            + ", ".join(missing)
            + "."
        )
    fields = _field_table(context)
    result: dict[str, RelocationSpec] = {}
    for row in table.matrix:
        name = _table_value(table, row, "name")
        if not isinstance(name, str) or not name:
            raise ValueError("relocations.name debe ser un nombre.")
        if name in existing or name in result:
            raise ValueError(f"La relocación '{name}' está duplicada.")
        spec = RelocationSpec(
            name=name,
            width_bits=_table_value(table, row, "width"),
            mode=_table_value(table, row, "mode"),
            pc_bias=_optional_table_value(table, row, "pc_bias", 0),
            scale=_optional_table_value(table, row, "scale", 1),
            alignment=_optional_table_value(table, row, "alignment", 1),
            signed=_optional_table_value(table, row, "signed", None),
            template=_optional_table_value(table, row, "template", 0),
            fields=fields.get(name, ()),
        )
        result[name] = spec
    unknown_fields = sorted(set(fields) - set(result))
    if unknown_fields:
        raise ValueError(
            "relocation_fields referencia relocaciones inexistentes: "
            + ", ".join(unknown_fields)
            + "."
        )
    return result


def relocation_specs(context: globals.TargetContext) -> dict[str, RelocationSpec]:
    """Return built-ins and target-declared generic relocation recipes.

    Simple ``@block relocations`` entries keep the ``name width mode`` form
    for ordinary ``pc`` and ``abs`` fields. Complex encodings use two tables:
    ``relocations`` describes the displacement transform and ``relocation_fields``
    describes how transformed bits are placed into the output template.
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
            if mode in {"relative", "pcrel"}:
                mode = "pc"
            elif mode == "absolute":
                mode = "abs"
            if mode not in {"pc", "abs"}:
                raise ValueError(
                    f"El modo de la relocación '{entry.name}' solo puede ser pc o abs."
                )
            if entry.name in specs:
                raise ValueError(f"La relocación '{entry.name}' está duplicada.")
            specs[entry.name] = RelocationSpec(entry.name, width, mode)
    specs.update(_table_specs(context, specs))
    return specs


def relocation_spec(context: globals.TargetContext, name: str) -> RelocationSpec:
    try:
        return relocation_specs(context)[name]
    except KeyError as exc:
        raise ValueError(f"Clase de relocación desconocida: {name!r}.") from exc


__all__ = [
    "RelocationField",
    "RelocationSpec",
    "relocation_spec",
    "relocation_specs",
]
