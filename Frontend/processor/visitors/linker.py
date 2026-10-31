from __future__ import annotations

from Frontend import globals


def _value(entry: globals.BlockEntryData) -> str | bool:
    if len(entry.values) != 1:
        raise RuntimeError(f"La entrada '{entry.name}' requiere un único valor.")
    value = entry.values[0]
    if value.kind == "STRING" and isinstance(value.value, str):
        return value.value
    if value.kind == "BOOL" and isinstance(value.value, bool):
        return value.value
    raise RuntimeError(f"La entrada '{entry.name}' requiere un string o booleano.")


def visit(block: globals.BlockData) -> None:
    """Validate and materialize the canonical generic ``linker`` block."""

    if globals.LINKER is not None:
        raise RuntimeError("Solo puede declararse un bloque @block linker por programa.")

    values: dict[str, str | bool] = {}
    for entry in block.entries:
        if entry.name not in {"ext", "name", "searching"}:
            raise RuntimeError(f"Entrada de @block linker desconocida: {entry.name}.")
        if entry.name in values:
            raise RuntimeError(f"La entrada '{entry.name}' solo puede aparecer una vez.")
        values[entry.name] = _value(entry)

    missing = [field for field in ("ext", "name", "searching") if field not in values]
    if missing:
        raise RuntimeError(
            "Faltan entradas obligatorias en @block linker: " + ", ".join(missing)
        )

    ext = values["ext"]
    name = values["name"]
    searching = values["searching"]
    if not isinstance(ext, str) or not ext:
        raise RuntimeError("ext debe ser un string no vacío.")
    if not isinstance(name, str) or not name:
        raise RuntimeError("name debe ser un string no vacío.")
    if searching is True:
        raise RuntimeError("searching acepta una carpeta, \"\" o false; true no es válido.")
    if not isinstance(searching, (str, bool)):
        raise RuntimeError("searching debe ser un string o false.")

    globals.LINKER = globals.LinkerData(
        ext=ext,
        name=name,
        searching=searching,
    )


__all__ = ["visit"]
