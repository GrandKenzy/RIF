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


def _children(node: Any) -> tuple[Any, ...]:
    if isinstance(node, (list, tuple)):
        return tuple(node)
    return tuple(getattr(node, "nodes", ()) or ())


def _token_kind(node: Any) -> str | None:
    token = getattr(node, "token", None)
    return getattr(getattr(token, "token", None), "name", None)


def _token_value(node: Any) -> Any:
    token = getattr(node, "token", None)
    return getattr(token, "value", None)


def _config_items(node: Any) -> tuple[Any, ...]:
    children = _children(node)
    if len(children) < 5 or not isinstance(children[4], list):
        raise RuntimeError("@config debe contener directivas de configuración.")

    items = tuple(children[4])
    if not all(getattr(item, "name", None) for item in items):
        raise RuntimeError("No se pudo identificar una directiva dentro de @config.")
    return items


def _string_value(node: Any) -> str:
    strings = tuple(
        _token_value(child)
        for child in _walk(node)
        if _token_kind(child) == "STRING"
    )
    if len(strings) != 1 or not isinstance(strings[0], str) or not strings[0]:
        raise RuntimeError("Las directivas de @config requieren un string no vacío.")
    return strings[0]


def _literal_values(node: Any, kind: str) -> tuple[Any, ...]:
    kinds = {kind}
    if kind == "NUMBER":
        kinds.add("DECIMAL")
    return tuple(
        _token_value(child)
        for child in _walk(node)
        if _token_kind(child) in kinds
    )


def _one_literal(node: Any, kind: str, field: str) -> Any:
    values = _literal_values(node, kind)
    if len(values) != 1:
        raise RuntimeError(f"La directiva '{field}' requiere un valor {kind}.")
    return values[0]


def _walk(node: Any):
    yield node
    for child in _children(node):
        yield from _walk(child)


def visit(node: Any) -> None:
    """Valida y materializa el bloque único @config."""
    if globals.CONFIG is not None:
        raise RuntimeError("Solo puede declararse un bloque @config por programa.")

    values: dict[str, str] = {}
    sections: list[str] = []

    for item in _config_items(node):
        item_name = getattr(item, "name", None)
        if item_name == "MAKE_SECTION":
            section = _string_value(item)
            if section in sections:
                raise RuntimeError(f"La sección '{section}' ya fue declarada.")
            sections.append(section)
            continue
        if item_name in {"SECTIONFLAGS", "SECTIONALIGN", "SECTIONVADDR"}:
            continue

        field = {
            "SECTIONDEF": "sectiondef",
            "SECTIONEND": "sectionend",
            "ENTRYSECTION": "entrysection",
            "ENTRYLABEL": "entrylabel",
            "COMMENT": "comment",
            "LABELEND": "labelend",
            "DATASECTION": "datasection",
            "DEFAULTSECTION": "defaultsection",
            "WORDSIZE": "wordsize",
            "ADDRESSSIZE": "addresssize",
            "ENDIANESS": "endianness",
            "CASESENSITIVE": "casesensitive",
            "SYMBOLPREFIX": "symbolprefix",
            "LOCALPREFIX": "localprefix",
            "UNDEFINEDSYMBOLS": "undefinedsymbols",
            "DUPLICATESYMBOLS": "duplicatesymbols",
            "STRICT": "strict",
            "ALLOWEMPTYSECTIONS": "allowemptysections",
            "BITORDER": "bitorder",
        }.get(item_name)
        if field is None:
            raise RuntimeError(f"Directiva de @config desconocida: {item_name}.")
        if field in values:
            raise RuntimeError(f"La directiva '{field}' solo puede aparecer una vez.")
        if field in {"wordsize", "addresssize"}:
            value = _one_literal(item, "NUMBER", field)
            if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
                raise RuntimeError(f"'{field}' debe ser un entero mayor que cero.")
            if value > resolve_limits().cap(256 << 20) * 8:
                raise RuntimeError(f"'{field}' excede el límite de recursos configurado.")
            values[field] = value  # type: ignore[assignment]
        elif field in {"casesensitive", "strict", "allowemptysections"}:
            value = _one_literal(item, "BOOL", field)
            if not isinstance(value, bool):
                raise RuntimeError(f"'{field}' debe ser booleano.")
            values[field] = value  # type: ignore[assignment]
        else:
            values[field] = _string_value(item)

    missing = [field for field in _FIELDS if field not in values]
    if not sections:
        raise RuntimeError("@config debe declarar al menos una sección.")
    if missing:
        raise RuntimeError(
            "Faltan directivas obligatorias en @config: " + ", ".join(missing)
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
    for item in _config_items(node):
        item_name = getattr(item, "name", None)
        if item_name == "SECTIONFLAGS":
            strings = _literal_values(item, "STRING")
            if len(strings) != 2 or any(not isinstance(value, str) or not value for value in strings):
                raise RuntimeError("sectionflags requiere sección y permisos no vacíos.")
            section, flags = strings
            if section not in sections:
                raise RuntimeError(f"sectionflags referencia sección desconocida '{section}'.")
            if section in sectionflags:
                raise RuntimeError(f"sectionflags ya fue declarada para '{section}'.")
            sectionflags[section] = flags
        elif item_name == "SECTIONALIGN":
            strings = _literal_values(item, "STRING")
            alignment = _one_literal(item, "NUMBER", "sectionalign")
            if len(strings) != 1 or not strings[0]:
                raise RuntimeError("sectionalign requiere una sección no vacía.")
            if isinstance(alignment, bool) or not isinstance(alignment, int) or alignment <= 0:
                raise RuntimeError("sectionalign debe ser un entero mayor que cero.")
            section = strings[0]
            if section not in sections:
                raise RuntimeError(f"sectionalign referencia sección desconocida '{section}'.")
            if section in sectionalign:
                raise RuntimeError(f"sectionalign ya fue declarada para '{section}'.")
            sectionalign[section] = alignment
        elif item_name == "SECTIONVADDR":
            strings = _literal_values(item, "STRING")
            address = _one_literal(item, "NUMBER", "sectionvaddr")
            if len(strings) != 1 or not strings[0]:
                raise RuntimeError("sectionvaddr requiere una sección no vacía.")
            if isinstance(address, bool) or not isinstance(address, int) or address < 0:
                raise RuntimeError("sectionvaddr debe ser un entero no negativo.")
            section = strings[0]
            if section not in sections:
                raise RuntimeError(f"sectionvaddr referencia sección desconocida '{section}'.")
            if section in sectionvaddr:
                raise RuntimeError(f"sectionvaddr ya fue declarada para '{section}'.")
            sectionvaddr[section] = address

    endianness = values["endianness"].lower()
    if endianness not in {"little", "big"}:
        raise RuntimeError("endianness debe ser 'little' o 'big'.")
    if values["undefinedsymbols"] not in {"error", "warn", "ignore"}:
        raise RuntimeError("undefinedsymbols debe ser 'error', 'warn' o 'ignore'.")
    if values["duplicatesymbols"] not in {"error", "warn", "ignore"}:
        raise RuntimeError("duplicatesymbols debe ser 'error', 'warn' o 'ignore'.")
    bitorder = values.get("bitorder", "msb").lower()
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
