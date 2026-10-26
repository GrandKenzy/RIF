"""Loading and validating the external ``funcs.py`` contract."""

from __future__ import annotations

import hashlib
import importlib.util
from dataclasses import dataclass, field
from pathlib import Path
from threading import RLock
from types import ModuleType
from typing import Any, Callable


class RIFFunctionError(RuntimeError):
    """A function module is missing, failed, or returned an invalid value."""


Handler = Callable[[str, Any], bool | str | bytes | bytearray | memoryview]


@dataclass
class FunctionModule:
    """A lazily loaded ``funcs.py`` module and its validated handler.

    Merely preparing a target must be safe for inspection.  Python code is
    therefore executed only when a Rule or artifact actually invokes it.
    """

    origin: str
    _loader: Callable[[], ModuleType] = field(repr=False)
    _module: ModuleType | None = field(default=None, init=False, repr=False)
    _handler: Handler | None = field(default=None, init=False, repr=False)
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)

    def _load(self) -> None:
        if self._module is not None:
            return
        with self._lock:
            if self._module is not None:
                return
            try:
                module = self._loader()
            except Exception as exc:  # pragma: no cover - exact exception is user code
                raise RIFFunctionError(
                    f"No se pudo cargar el archivo de funciones {self.origin}: {exc}"
                ) from exc
            handler = getattr(module, "handler", None)
            if not callable(handler):
                raise RIFFunctionError(
                    f"El archivo de funciones {self.origin} debe definir un handler callable."
                )
            self._module = module
            self._handler = handler

    @property
    def loaded(self) -> bool:
        return self._module is not None

    @property
    def module(self) -> ModuleType:
        self._load()
        assert self._module is not None
        return self._module

    @property
    def handler(self) -> Handler:
        self._load()
        assert self._handler is not None
        return self._handler

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

    def invoke_payload(self, name: str, context: Any) -> bytes | str:
        """Invoke a handler in binary-payload mode.

        Payload calls are intentionally separate from Rule calls: booleans are
        valid Rule conditions but cannot be inserted into a binary image.
        """

        try:
            result = self.handler(name, context)
        except Exception as exc:  # pragma: no cover - exact exception is user code
            raise RIFFunctionError(
                f"La función Python '{name}' falló en {self.origin}: {exc}"
            ) from exc
        if isinstance(result, (bytes, bytearray, memoryview)):
            return bytes(result)
        if isinstance(result, str) and result and set(result) <= {"0", "1"}:
            return result
        raise RIFFunctionError(
            f"La función Python '{name}' devolvió {result!r}; "
            "un payload solo puede ser bytes o un string binario no vacío."
        )


def _module_name(origin: str, source: bytes) -> str:
    digest = hashlib.sha256(origin.encode("utf-8") + b"\0" + source).hexdigest()[:16]
    return f"rif_funcs_{digest}"


def load_function_source(source: str | bytes, origin: str) -> FunctionModule:
    """Create a lazy module backed by source from a package entry."""

    source_bytes = source.encode("utf-8") if isinstance(source, str) else bytes(source)
    def load() -> ModuleType:
        module = ModuleType(_module_name(origin, source_bytes))
        module.__file__ = origin
        module.__package__ = ""
        code = compile(source_bytes.decode("utf-8"), origin, "exec")
        exec(code, module.__dict__)
        return module

    return FunctionModule(origin=origin, _loader=load)


def load_function_file(path: str | Path) -> FunctionModule:
    """Create a lazy module backed by a loose ``funcs.py`` file."""

    function_path = Path(path).expanduser().resolve()
    if not function_path.is_file():
        raise FileNotFoundError(f"Archivo de funciones no encontrado: {function_path}")
    source = function_path.read_bytes()
    def load() -> ModuleType:
        module_name = _module_name(str(function_path), source)
        spec = importlib.util.spec_from_file_location(module_name, function_path)
        if spec is None or spec.loader is None:
            raise ImportError("no se pudo crear el loader Python")
        loaded = importlib.util.module_from_spec(spec)
        loaded.__file__ = str(function_path)
        spec.loader.exec_module(loaded)
        return loaded

    return FunctionModule(origin=str(function_path), _loader=load)


__all__ = [
    "FunctionModule",
    "RIFFunctionError",
    "load_function_file",
    "load_function_source",
]
