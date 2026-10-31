from __future__ import annotations

from typing import Any

from Frontend import globals
from rif_limits import resolve_limits


_FIELDS = (
    "sectiondef",
    "sectionend",
    "entrysection",
    "entrylabel",
    "comment",
    "labelend",
    "datasection",
    "defaultsection",
    "wordsize",
    "addresssize",
    "endianness",
    "casesensitive",
    "symbolprefix",
    "localprefix",
    "undefinedsymbols",
    "duplicatesymbols",
    "strict",
    "allowemptysections",
)


def _string_value(entry: globals.BlockEntryData) -> str:
    if len(entry.values) != 1:
        raise RuntimeError(f"La entrada '{entry.name}' requiere un único string.")
    value = entry.values[0]
    if value.kind != "STRING" or not isinstance(value.value, str) or not value.value:
        raise RuntimeError(f"La entrada '{entry.name}' requiere un string no vacío.")
    return value.value


def _literal_value(entry: globals.BlockEntryData, kind: str) -> Any:
    if len(entry.values) != 1:
        raise RuntimeError(f"La entrada '{entry.name}' requiere un valor {kind}.")
    value = entry.values[0]
    allowed = {kind}
    if kind == "NUMBER":
        allowed.add("DECIMAL")
    if value.kind not in allowed:
        raise RuntimeError(f"La entrada '{entry.name}' requiere un valor {kind}.")
    return value.value


def _section_name(entry: globals.BlockEntryData) -> str:
    if len(entry.values) != 2:
        raise RuntimeError("La entrada 'make' requiere 'section' y un nombre.")
    kind, value = entry.values[0].kind, entry.values[0].value
    if kind not in {"IDENT", "KEYWORD"} or value != "section":
        raise RuntimeError("La entrada 'make' solo admite la forma 'make section <nombre>'.")
    section = entry.values[1]
    if section.kind != "STRING" or not isinstance(section.value, str) or not section.value:
        raise RuntimeError("La entrada 'make' requiere un nombre de sección no vacío.")
    return section.value


def _section_string_and_number(
    entry: globals.BlockEntryData,
    field: str,
) -> tuple[str, Any]:
    if len(entry.values) != 2:
        raise RuntimeError(f"La entrada '{field}' requiere una sección y un número.")
    section, number = entry.values
    if section.kind != "STRING" or not isinstance(section.value, str) or not section.value:
        raise RuntimeError(f"{field} requiere una sección no vacía.")
    if number.kind not in {"NUMBER", "DECIMAL"}:
        raise RuntimeError(f"{field} requiere un número.")
    return section.value, number.value


def visit(block: globals.BlockData) -> None:
    """Validate and materialize the canonical generic ``config`` block."""

    if globals.CONFIG is not None:
        raise RuntimeError("Solo puede declararse un bloque @block config por programa.")

    values: dict[str, Any] = {}
    sections: list[str] = []

    for entry in block.entries:
        name = entry.name
        if name == "make":
            section = _section_name(entry)
            if section in sections:
                raise RuntimeError(f"La sección '{section}' ya fue declarada.")
            sections.append(section)
            continue
        if name in {"sectionflags", "sectionalign", "sectionvaddr", "bitorder"}:
            continue

        if name not in _FIELDS:
            raise RuntimeError(f"Entrada de @block config desconocida: {name}.")
        if name in values:
            raise RuntimeError(f"La entrada '{name}' solo puede aparecer una vez.")
        if name in {"wordsize", "addresssize"}:
            value = _literal_value(entry, "NUMBER")
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise RuntimeError(f"'{name}' debe ser un entero mayor que cero.")
            if value > resolve_limits().cap(256 << 20) * 8:
                raise RuntimeError(f"'{name}' excede el límite de recursos configurado.")
            values[name] = value
        elif name in {"casesensitive", "strict", "allowemptysections"}:
            value = _literal_value(entry, "BOOL")
            if not isinstance(value, bool):
                raise RuntimeError(f"'{name}' debe ser booleano.")
            values[name] = value
        else:
            values[name] = _string_value(entry)

    missing = [field for field in _FIELDS if field not in values]
    if not sections:
        raise RuntimeError("@block config debe declarar al menos una sección.")
    if missing:
        raise RuntimeError(
            "Faltan entradas obligatorias en @block config: " + ", ".join(missing)
        )

    entrysection = values["entrysection"]
    datasection = values["datasection"]
    if entrysection not in sections:
        raise RuntimeError(
            f"entrysection '{entrysection}' no fue declarada con make section."
        )
    if datasection not in sections:
        raise RuntimeError(
            f"datasection '{datasection}' no fue declarada con make section."
        )

    defaultsection = values["defaultsection"]
    if defaultsection not in sections:
        raise RuntimeError(
            f"defaultsection '{defaultsection}' no fue declarada con make section."
        )

    sectionflags: dict[str, str] = {}
    sectionalign: dict[str, int] = {}
    sectionvaddr: dict[str, int] = {}
    for entry in block.entries:
        if entry.name == "sectionflags":
            if len(entry.values) != 2 or any(
                value.kind != "STRING" or not isinstance(value.value, str) or not value.value
                for value in entry.values
            ):
                raise RuntimeError("sectionflags requiere sección y permisos no vacíos.")
            section, flags = (value.value for value in entry.values)
            if section not in sections:
                raise RuntimeError(f"sectionflags referencia sección desconocida '{section}'.")
            if section in sectionflags:
                raise RuntimeError(f"sectionflags ya fue declarada para '{section}'.")
            sectionflags[section] = flags
        elif entry.name in {"sectionalign", "sectionvaddr"}:
            section, number = _section_string_and_number(entry, entry.name)
            if section not in sections:
                raise RuntimeError(f"{entry.name} referencia sección desconocida '{section}'.")
            if isinstance(number, bool) or not isinstance(number, int):
                raise RuntimeError(f"{entry.name} debe ser un entero.")
            if entry.name == "sectionalign":
                if number <= 0:
                    raise RuntimeError("sectionalign debe ser un entero mayor que cero.")
                if section in sectionalign:
                    raise RuntimeError(f"sectionalign ya fue declarada para '{section}'.")
                sectionalign[section] = number
            else:
                if number < 0:
                    raise RuntimeError("sectionvaddr debe ser un entero no negativo.")
                if section in sectionvaddr:
                    raise RuntimeError(f"sectionvaddr ya fue declarada para '{section}'.")
                sectionvaddr[section] = number

    endianness = values["endianness"].lower()
    if endianness not in {"little", "big"}:
        raise RuntimeError("endianness debe ser 'little' o 'big'.")
    if values["undefinedsymbols"] not in {"error", "warn", "ignore"}:
        raise RuntimeError("undefinedsymbols debe ser 'error', 'warn' o 'ignore'.")
    if values["duplicatesymbols"] not in {"error", "warn", "ignore"}:
        raise RuntimeError("duplicatesymbols debe ser 'error', 'warn' o 'ignore'.")

    bitorder = "msb"
    bitorder_seen = False
    for entry in block.entries:
        if entry.name == "bitorder":
            if bitorder_seen:
                raise RuntimeError("La entrada 'bitorder' solo puede aparecer una vez.")
            bitorder_seen = True
            bitorder = _string_value(entry).lower()
    if bitorder not in {"msb", "lsb"}:
        raise RuntimeError("bitorder debe ser 'msb' o 'lsb'.")

    globals.CONFIG = globals.ConfigData(
        sectiondef=values["sectiondef"],
        sections=tuple(sections),
        sectionend=values["sectionend"],
        entrysection=entrysection,
        entrylabel=values["entrylabel"],
        comment=values["comment"],
        labelend=values["labelend"],
        datasection=datasection,
        defaultsection=defaultsection,
        sectionflags=sectionflags,
        sectionalign=sectionalign,
        wordsize=values["wordsize"],
        addresssize=values["addresssize"],
        endianness=endianness,
        casesensitive=values["casesensitive"],
        symbolprefix=values["symbolprefix"],
        localprefix=values["localprefix"],
        undefinedsymbols=values["undefinedsymbols"],
        duplicatesymbols=values["duplicatesymbols"],
        strict=values["strict"],
        allowemptysections=values["allowemptysections"],
        bitorder=bitorder,
        sectionvaddr=sectionvaddr,
    )


__all__ = ["visit"]
