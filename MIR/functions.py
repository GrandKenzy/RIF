"""Loading and validating the external ``funcs.py`` contract."""

from __future__ import annotations

import hashlib
import importlib.util
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, Callable


class RIFFunctionError(RuntimeError):
    """A function module is missing, failed, or returned an invalid value."""


Handler = Callable[[str, Any], bool | str]


@dataclass(frozen=True)
class FunctionModule:
    """A loaded ``funcs.py`` module and its validated handler."""

    module: ModuleType
    origin: str
    handler: Handler

    def invoke(self, name: str, context: Any) -> bool | str:
        try:
            result = self.handler(name, context)
        except Exception as exc:  # pragma: no cover - exact exception is user code
            raise RIFFunctionError(
                f"La función Python '{name}' falló en {self.origin}: {exc}"
            ) from exc
        if isinstance(result, bool):
            return result
        if isinstance(result, str) and result and set(result) <= {"0", "1"}:
            return result
        raise RIFFunctionError(
            f"La función Python '{name}' devolvió {result!r}; "
            "solo se permiten bool o strings binarios no vacíos."
        )


def _module_name(origin: str, source: bytes) -> str:
    digest = hashlib.sha256(origin.encode("utf-8") + b"\0" + source).hexdigest()[:16]
    return f"rif_funcs_{digest}"


def _validate_module(module: ModuleType, origin: str) -> FunctionModule:
    handler = getattr(module, "handler", None)
    if not callable(handler):
        raise RIFFunctionError(
            f"El archivo de funciones {origin} debe definir un handler callable."
        )
    return FunctionModule(module=module, origin=origin, handler=handler)


def load_function_source(source: str | bytes, origin: str) -> FunctionModule:
    """Execute source code from a loose file or package entry."""

    source_bytes = source.encode("utf-8") if isinstance(source, str) else bytes(source)
    module = ModuleType(_module_name(origin, source_bytes))
    module.__file__ = origin
    module.__package__ = ""
    try:
        code = compile(source_bytes.decode("utf-8"), origin, "exec")
        exec(code, module.__dict__)
    except Exception as exc:  # pragma: no cover - exact exception is user code
        raise RIFFunctionError(
            f"No se pudo cargar el archivo de funciones {origin}: {exc}"
        ) from exc
    return _validate_module(module, origin)


def load_function_file(path: str | Path) -> FunctionModule:
    """Load a loose ``funcs.py`` from disk."""

    function_path = Path(path).expanduser().resolve()
    if not function_path.is_file():
        raise FileNotFoundError(f"Archivo de funciones no encontrado: {function_path}")
    source = function_path.read_bytes()
    try:
        module_name = _module_name(str(function_path), source)
        spec = importlib.util.spec_from_file_location(module_name, function_path)
        if spec is None or spec.loader is None:
            raise ImportError("no se pudo crear el loader Python")
        loaded = importlib.util.module_from_spec(spec)
        loaded.__file__ = str(function_path)
        spec.loader.exec_module(loaded)
    except Exception as exc:  # pragma: no cover - exact exception is user code
        raise RIFFunctionError(
            f"No se pudo cargar el archivo de funciones {function_path}: {exc}"
        ) from exc
    return _validate_module(loaded, str(function_path))


__all__ = [
    "FunctionModule",
    "RIFFunctionError",
    "load_function_file",
    "load_function_source",
]
