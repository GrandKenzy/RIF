"""Carga inclusiones explícitas ``@LOAD \"archivo.rif\"``."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from Frontend import globals
from rif_limits import resolve_limits


MAX_SOURCE_BYTES = 16 << 20


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


def resolve_source(
    requested: str,
    source_path: str | Path | None,
    project_root: str | Path | None = None,
) -> Path:
    """Resuelve una inclusión relativa al archivo que contiene ``@LOAD``."""

    path = Path(requested).expanduser()
    if path.is_absolute():
        raise ValueError("@LOAD solo acepta rutas relativas.")
    base = Path(source_path).expanduser().parent if source_path else Path.cwd()
    candidate = (base / path).resolve(strict=False)
    root = Path(project_root).expanduser().resolve(strict=False) if project_root else base.resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("@LOAD intenta salir de la raíz del proyecto.") from exc
    return candidate


def load_source(
    node: Any,
    source_path: str | Path | None,
    *,
    scope: str = "root",
    source_provider: Any | None = None,
    project_root: str | Path | None = None,
) -> None:
    """Carga y procesa un archivo RIF dentro del alcance solicitado."""

    requested = _requested_path(node)
    provider = source_provider if source_provider is not None else globals.SOURCE_PROVIDER
    if provider is not None:
        path_key = provider.resolve_load(source_path, requested)
        path = None
    else:
        path = resolve_source(requested, source_path, project_root)
        path_key = str(path)

    if path_key in globals.ACTIVE_SOURCES:
        cycle = " -> ".join((*globals.ACTIVE_SOURCES, path_key))
        raise RuntimeError(f"Ciclo de @LOAD detectado: {cycle}")
    if path_key in globals.LOADED_SOURCES:
        return
    if path is not None and not path.is_file():
        raise FileNotFoundError(f"No se encontró el archivo solicitado por @LOAD: {path}")

    from Frontend import RIF_LANG_SESSION
    from . import process

    globals.ACTIVE_SOURCES.append(path_key)
    try:
        if path is not None and path.stat().st_size > resolve_limits().cap(MAX_SOURCE_BYTES):
            raise ValueError(f"La fuente RIF excede el límite de tamaño: {path}")
        source = (
            provider.source_text(path_key)
            if provider is not None
            else path.read_text(encoding="utf-8")
        )
        RIF_LANG_SESSION.load()
        tokens = RIF_LANG_SESSION.tokenize(source, path_key)
        ast = RIF_LANG_SESSION.parse(tokens, path_key)
        process(
            ast,
            source_path=path_key,
            load_variants=False,
            scope=scope,
            source_provider=provider,
            project_root=project_root,
        )
        globals.LOADED_SOURCES[path_key] = "load"
    finally:
        if globals.ACTIVE_SOURCES and globals.ACTIVE_SOURCES[-1] == path_key:
            globals.ACTIVE_SOURCES.pop()
        elif path_key in globals.ACTIVE_SOURCES:
            globals.ACTIVE_SOURCES.remove(path_key)


__all__ = ["resolve_source", "load_source"]
