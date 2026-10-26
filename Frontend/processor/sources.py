"""Carga inclusiones explícitas ``@LOAD \"archivo.rif\"``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from Frontend import globals


def _children(node: Any) -> tuple[Any, ...]:
    if isinstance(node, (list, tuple)):
        return tuple(node)
    return tuple(getattr(node, "nodes", ()) or ())


def _walk(node: Any):
    yield node
    for child in _children(node):
        yield from _walk(child)


def _token_kind(node: Any) -> str | None:
    token = getattr(node, "token", None)
    return getattr(getattr(token, "token", None), "name", None)


def _token_value(node: Any) -> Any:
    token = getattr(node, "token", None)
    return getattr(token, "value", None)


def _requested_path(node: Any) -> str:
    values = tuple(
        _token_value(current)
        for current in _walk(node)
        if _token_kind(current) == "STRING"
    )
    if len(values) != 1 or not isinstance(values[0], str) or not values[0]:
        raise RuntimeError("@LOAD requiere un único path string no vacío.")
    requested = values[0]
    if Path(requested).suffix.lower() != ".rif":
        raise RuntimeError(f"@LOAD solo acepta archivos .rif: {requested}")
    return requested


def resolve_source(requested: str, source_path: str | Path | None) -> Path:
    """Resuelve una inclusión relativa al archivo que contiene ``@LOAD``."""

    path = Path(requested).expanduser()
    if not path.is_absolute():
        base = Path(source_path).expanduser().parent if source_path else Path.cwd()
        path = base / path
    return Path(str(path.resolve(strict=False)))


def load_source(
    node: Any,
    source_path: str | Path | None,
    *,
    scope: str = "root",
) -> None:
    """Carga y procesa un archivo RIF dentro del alcance solicitado."""

    requested = _requested_path(node)
    path = resolve_source(requested, source_path)
    path_key = str(path)

    if path_key in globals.ACTIVE_SOURCES:
        cycle = " -> ".join((*globals.ACTIVE_SOURCES, path_key))
        raise RuntimeError(f"Ciclo de @LOAD detectado: {cycle}")
    if path_key in globals.LOADED_SOURCES:
        return
    if not path.is_file():
        raise FileNotFoundError(f"No se encontró el archivo solicitado por @LOAD: {path}")

    from Frontend import RIF_LANG_SESSION
    from . import process

    globals.ACTIVE_SOURCES.append(path_key)
    try:
        source = path.read_text(encoding="utf-8")
        RIF_LANG_SESSION.load()
        tokens = RIF_LANG_SESSION.tokenize(source, path_key)
        ast = RIF_LANG_SESSION.parse(tokens, path_key)
        process(ast, source_path=path_key, load_variants=False, scope=scope)
        globals.LOADED_SOURCES[path_key] = "load"
    finally:
        if globals.ACTIVE_SOURCES and globals.ACTIVE_SOURCES[-1] == path_key:
            globals.ACTIVE_SOURCES.pop()
        elif path_key in globals.ACTIVE_SOURCES:
            globals.ACTIVE_SOURCES.remove(path_key)


__all__ = ["resolve_source", "load_source"]
