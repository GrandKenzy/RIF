from __future__ import annotations

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


def _items(node: Any) -> tuple[Any, ...]:
    children = _children(node)
    if len(children) < 5 or not isinstance(children[4], list):
        raise RuntimeError("@linker debe contener directivas de linker.")
    items = tuple(children[4])
    if not all(getattr(item, "name", None) for item in items):
        raise RuntimeError("No se pudo identificar una directiva dentro de @linker.")
    return items


def _value(node: Any) -> str | bool:
    values = tuple(
        (_token_kind(child), _token_value(child))
        for child in _walk(node)
        if _token_kind(child) in {"STRING", "BOOL"}
    )
    if len(values) != 1:
        raise RuntimeError("La directiva del linker requiere un único valor.")
    kind, value = values[0]
    if kind == "STRING" and isinstance(value, str):
        return value
    if kind == "BOOL" and isinstance(value, bool):
        return value
    raise RuntimeError("El valor de la directiva del linker no es válido.")


def visit(node: Any) -> None:
    """Valida y materializa el bloque único @linker."""
    if globals.LINKER is not None:
        raise RuntimeError("Solo puede declararse un bloque @linker por programa.")

    values: dict[str, str | bool] = {}
    for item in _items(node):
        field = {
            "EXT": "ext",
            "NAME": "name",
            "SEARCHING": "searching",
        }.get(getattr(item, "name", None))
        if field is None:
            raise RuntimeError(f"Directiva de @linker desconocida: {getattr(item, 'name', None)}.")
        if field in values:
            raise RuntimeError(f"La directiva '{field}' solo puede aparecer una vez.")
        values[field] = _value(item)

    missing = [field for field in ("ext", "name", "searching") if field not in values]
    if missing:
        raise RuntimeError(
            "Faltan directivas obligatorias en @linker: " + ", ".join(missing)
        )

    ext = values["ext"]
    name = values["name"]
    searching = values["searching"]
    if not isinstance(ext, str) or not ext:
        raise RuntimeError(".ext debe ser un string no vacío.")
    if not isinstance(name, str) or not name:
        raise RuntimeError(".name debe ser un string no vacío.")
    if searching is True:
        raise RuntimeError(".searching acepta una carpeta, \"\" o false; true no es válido.")
    if not isinstance(searching, (str, bool)):
        raise RuntimeError(".searching debe ser un string o false.")

    globals.LINKER = globals.LinkerData(
        ext=ext,
        name=name,
        searching=searching,
    )


__all__ = ["visit"]
