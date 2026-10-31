from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path
from typing import Any

from Frontend import globals
from .visitors.define import visit as visit_define
from .visitors.rule import visit as visit_rule
from .visitors.stack import visit as visit_stack
from .visitors.table import visit as visit_table
from .visitors.variant import visit_support, visit_variant
from .visitors.artifacts import visit_before, visit_insert
from .visitors.block import visit as visit_block
from .sources import load_source
from .variants import current_variant, enter_variant, exit_variant, load_variants as _load_variants


def process(
    result: Iterable[Any] | None,
    source_path: str | Path | None = None,
    *,
    load_variants: bool = True,
    scope: str = "root",
    source_provider: Any | None = None,
    project_root: str | Path | None = None,
) -> None:
    """Recorre y despacha cada nodo producido por el parser."""
    if result is None:
        return

    nodes = list(result)
    provider = source_provider if source_provider is not None else globals.SOURCE_PROVIDER
    raw_source = str(source_path) if source_path is not None else ""
    if raw_source.startswith("pack://"):
        source_key = raw_source
    else:
        source_key = (
            str(Path(source_path).expanduser().resolve(strict=False))
            if source_path
            else None
        )
    resolved_root = (
        Path(project_root).expanduser().resolve(strict=False)
        if project_root is not None
        else (
            Path(source_path).expanduser().resolve(strict=False).parent
            if source_path and not raw_source.startswith("pack://")
            else None
        )
    )
    previous_provider = globals.SOURCE_PROVIDER
    owns_provider = source_provider is not None and previous_provider is not source_provider
    if owns_provider:
        globals.SOURCE_PROVIDER = source_provider
    owns_source = bool(source_key and source_key not in globals.ACTIVE_SOURCES)
    if owns_source:
        globals.ACTIVE_SOURCES.append(source_key)

    try:
        allowed = {
            "root": {
                "DEFINE", "SUPPORTS", "ASMVARIANT",
                "TABLE", "STACK", "RULE", "LOAD_FILE",
                "INSERT", "BEFORE",
                "BLOCK",
            },
            "include": {"DEFINE", "TABLE", "RULE", "LOAD_FILE"},
            "variant": {"DEFINE", "RULE"},
        }
        try:
            allowed_names = allowed[scope]
        except KeyError as exc:
            raise ValueError(f"Alcance de procesamiento desconocido: {scope}") from exc
        forbidden = {
            getattr(node, "name", type(node).__name__)
            for node in nodes
            if getattr(node, "name", type(node).__name__) not in allowed_names
        }
        if forbidden:
            names = ", ".join(sorted(forbidden))
            raise RuntimeError(
                f"El alcance '{scope}' no permite estas declaraciones: {names}."
            )

        # Los bloques genéricos, los labels y los soportes se registran antes
        # de resolver tablas u otras referencias, sin depender del orden.
        for node in nodes:
            name = getattr(node, "name", type(node).__name__)
            if name == "DEFINE":
                visit_define(node)
            elif name == "SUPPORTS":
                visit_support(node)
            elif name == "BLOCK":
                visit_block(node, source_path=source_key)

        for node in nodes:
            if getattr(node, "name", type(node).__name__) == "ASMVARIANT":
                visit_variant(node)

        for node in nodes:
            name = getattr(node, "name", type(node).__name__)
            if name in {"DEFINE", "SUPPORTS", "ASMVARIANT", "BLOCK"}:
                continue
            if name == "TABLE":
                visit_table(node)
            elif name == "STACK":
                visit_stack(node)
            elif name == "RULE":
                visit_rule(node, source_path=source_key)
            elif name == "LOAD_FILE":
                load_source(
                    node,
                    source_key,
                    scope="include",
                    source_provider=provider,
                    project_root=resolved_root,
                )
            elif name == "INSERT":
                visit_insert(node, source_path=source_key)
            elif name == "BEFORE":
                visit_before(node, source_path=source_key)
            else:
                print("falta por procesar", name)

        if load_variants and source_key:
            _load_variants(
                source_key,
                source_provider=provider,
                project_root=resolved_root,
            )
    finally:
        if owns_source and source_key in globals.ACTIVE_SOURCES:
            globals.ACTIVE_SOURCES.remove(source_key)
        if owns_provider:
            globals.SOURCE_PROVIDER = previous_provider


__all__ = [
    "process",
    "load_variants",
    "load_source",
    "enter_variant",
    "exit_variant",
    "current_variant",
]

# API pública con el nombre previsto por el plan; el alias interno evita que
# el parámetro ``load_variants`` de process oculte la función importada.
load_variants = _load_variants
