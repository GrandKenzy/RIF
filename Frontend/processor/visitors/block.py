"""Normalize generic blocks and bridge known blocks to legacy visitors."""

from __future__ import annotations

import json
from typing import Any

from Frontend import RIF_LANG_SESSION, globals

from .config import visit as visit_config
from .linker import visit as visit_linker


_VALUE_KINDS = {"KEYWORD", "IDENT", "NUMBER", "DECIMAL", "STRING", "BOOL"}


def _kind(token: Any) -> str:
    return getattr(getattr(token, "token", None), "name", "")


def _value(token: Any) -> Any:
    return getattr(token, "value", None)


def _render_value(token: Any) -> str:
    kind = _kind(token)
    value = _value(token)
    if kind == "STRING":
        return json.dumps(value, ensure_ascii=False)
    if kind == "BOOL":
        return "true" if value else "false"
    return str(value)


def _entries(node: Any) -> tuple[globals.BlockEntryData, ...]:
    result: list[globals.BlockEntryData] = []
    for line in tuple(getattr(node, "lines", ()) or ()):
        tokens = list(line)
        if tokens and _kind(tokens[-1]) == "NEWLINE":
            tokens.pop()
        if not tokens:
            continue
        if _kind(tokens[0]) == "DOT":
            tokens.pop(0)
        if not tokens or _kind(tokens[0]) not in {"IDENT", "KEYWORD"}:
            raise RuntimeError("Un bloque genérico requiere un nombre por línea.")
        if len(tokens) > 3:
            raise RuntimeError(
                "Un bloque genérico acepta un nombre y como máximo dos valores por línea."
            )
        values: list[globals.BlockValueData] = []
        for token in tokens[1:]:
            kind = _kind(token)
            if kind not in _VALUE_KINDS:
                raise RuntimeError(
                    f"El valor de '{_value(tokens[0])}' no es válido en un bloque genérico."
                )
            values.append(
                globals.BlockValueData(kind, _value(token), _render_value(token))
            )
        result.append(globals.BlockEntryData(str(_value(tokens[0])), tuple(values)))
    return tuple(result)


def _legacy_source(block_name: str, entries: tuple[globals.BlockEntryData, ...]) -> str:
    lines = [f"@{block_name}:"]
    for entry in entries:
        rendered = " ".join(value.raw or str(value.value) for value in entry.values)
        lines.append(f".{entry.name}{(' ' + rendered) if rendered else ''}")
    lines.append(f"@{block_name}end")
    return "\n".join(lines) + "\n"


def _visit_legacy(block_name: str, entries: tuple[globals.BlockEntryData, ...], source_path: str | None) -> None:
    source = _legacy_source(block_name, entries)
    name = source_path or f"<block {block_name}>"
    RIF_LANG_SESSION.load()
    ast = RIF_LANG_SESSION.parse(RIF_LANG_SESSION.tokenize(source, name), name)
    if not ast or len(ast) != 1:
        raise RuntimeError(f"No se pudo materializar el bloque genérico '{block_name}'.")
    if block_name == "config":
        visit_config(ast[0])
    else:
        visit_linker(ast[0])


def visit(node: Any, source_path: str | None = None) -> None:
    block_name = str(getattr(node, "block_name", "")).lower()
    if not block_name:
        raise RuntimeError("Un bloque genérico requiere un nombre.")
    entries = _entries(node)
    block = globals.BlockData(block_name, entries, source_path)
    globals.BLOCKS.setdefault(block_name, []).append(block)
    if block_name in {"config", "linker"}:
        _visit_legacy(block_name, entries, source_path)


__all__ = ["visit"]
