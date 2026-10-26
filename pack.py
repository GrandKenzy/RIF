"""Formato y creación de paquetes fuente ``.pack`` de RIF.

Un paquete ``.pack`` es un ZIP reproducible que contiene todos los archivos
``.rif`` del directorio del proyecto bajo ``sources/``, un manifiesto JSON y,
cuando se crea con ``precompile=True``, una base SQLite con el MIR y el
contexto ya resueltos.
"""

from __future__ import annotations

import hashlib
import json
import os
import posixpath
import re
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any


PACK_FORMAT = "RIF_PACK"
PACK_FORMAT_VERSION = 2
MANIFEST_NAME = "manifest.json"
SOURCE_PREFIX = "sources/"
_LOAD_RE = re.compile(r'^\s*@LOAD\s+"([^"]+)"(?:\s*;.*)?\s*$', re.IGNORECASE)


@dataclass(frozen=True)
class PackEntry:
    """Metadata de un archivo RIF incluido en el paquete."""

    path: str
    size: int
    sha256: str
    loads: tuple[str, ...] = ()


@dataclass(frozen=True)
class PackManifest:
    """Manifiesto validado de un paquete ``.pack``."""

    name: str
    version: str
    entrypoint: str
    files: tuple[PackEntry, ...]
    load_graph: dict[str, tuple[str, ...]]
    dependency_order: tuple[str, ...]
    compiled: PackEntry | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "format": PACK_FORMAT,
            "format_version": PACK_FORMAT_VERSION,
            "name": self.name,
            "version": self.version,
            "entrypoint": self.entrypoint,
            "files": [
                {
                    "path": entry.path,
                    "size": entry.size,
                    "sha256": entry.sha256,
                    "loads": list(entry.loads),
                }
                for entry in self.files
            ],
            "load_graph": {
                path: list(dependencies)
                for path, dependencies in sorted(self.load_graph.items())
            },
            "dependency_order": list(self.dependency_order),
            "compiled": (
                {
                    "path": self.compiled.path,
                    "size": self.compiled.size,
                    "sha256": self.compiled.sha256,
                }
                if self.compiled is not None
                else None
            ),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PackManifest":
        if data.get("format") != PACK_FORMAT:
            raise ValueError("El archivo no es un paquete RIF válido.")
        format_version = data.get("format_version")
        if format_version not in {1, PACK_FORMAT_VERSION}:
            raise ValueError(
                "Versión de formato .pack no compatible: "
                f"{format_version!r}."
            )

        raw_files = data.get("files")
        if not isinstance(raw_files, list):
            raise ValueError("El manifiesto .pack no contiene una lista de archivos.")

        entries: list[PackEntry] = []
        for raw in raw_files:
            if not isinstance(raw, dict):
                raise ValueError("El manifiesto contiene una entrada de archivo inválida.")
            path = raw.get("path")
            size = raw.get("size")
            sha256 = raw.get("sha256")
            raw_loads = raw.get("loads", [])
            if (
                not isinstance(path, str)
                or not isinstance(size, int)
                or size < 0
                or not isinstance(sha256, str)
                or len(sha256) != 64
                or not isinstance(raw_loads, list)
                or not all(isinstance(item, str) for item in raw_loads)
            ):
                raise ValueError("El manifiesto contiene metadatos de archivo inválidos.")
            entries.append(PackEntry(path, size, sha256, tuple(raw_loads)))

        raw_graph = data.get("load_graph", {})
        raw_order = data.get("dependency_order", [])
        if not isinstance(raw_graph, dict) or not isinstance(raw_order, list):
            raise ValueError("El manifiesto contiene un índice de LOAD inválido.")
        load_graph = {
            str(path): tuple(dependencies)
            for path, dependencies in raw_graph.items()
            if isinstance(path, str)
            and isinstance(dependencies, list)
            and all(isinstance(item, str) for item in dependencies)
        }
        if len(load_graph) != len(raw_graph) or not all(
            isinstance(item, str) for item in raw_order
        ):
            raise ValueError("El manifiesto contiene un índice de LOAD inválido.")

        raw_compiled = data.get("compiled")
        compiled = None
        if raw_compiled is not None:
            if not isinstance(raw_compiled, dict):
                raise ValueError("El manifiesto contiene metadata compilada inválida.")
            compiled_path = raw_compiled.get("path")
            compiled_size = raw_compiled.get("size")
            compiled_sha256 = raw_compiled.get("sha256")
            if (
                not isinstance(compiled_path, str)
                or not isinstance(compiled_size, int)
                or compiled_size < 0
                or not isinstance(compiled_sha256, str)
                or len(compiled_sha256) != 64
            ):
                raise ValueError("El manifiesto contiene metadata compilada inválida.")
            compiled = PackEntry(compiled_path, compiled_size, compiled_sha256)

        return cls(
            name=str(data.get("name", "")),
            version=str(data.get("version", "")),
            entrypoint=str(data.get("entrypoint", "")),
            files=tuple(entries),
            load_graph=load_graph,
            dependency_order=tuple(raw_order),
            compiled=compiled,
        )


def _canonical_path(path: str | Path) -> Path:
    return Path(path).expanduser().resolve(strict=False)


def _project_files(entrypoint: Path) -> tuple[tuple[str, Path], ...]:
    """Collect all local ``.rif`` files with stable POSIX paths."""

    root = entrypoint.parent
    collected: list[tuple[str, Path]] = []
    for candidate in root.rglob("*"):
        if not candidate.is_file() or candidate.suffix.lower() != ".rif":
            continue
        resolved = candidate.resolve(strict=True)
        try:
            relative = resolved.relative_to(root)
        except ValueError as exc:
            raise ValueError(
                f"El archivo RIF está fuera del proyecto: {candidate}"
            ) from exc
        relative_name = PurePosixPath(relative.as_posix()).as_posix()
        collected.append((relative_name, resolved))

    expected = entrypoint.relative_to(root).as_posix()
    if expected not in {relative for relative, _ in collected}:
        raise FileNotFoundError(f"No se pudo incluir el entrypoint RIF: {entrypoint}")

    return tuple(sorted(collected, key=lambda item: item[0].casefold()))


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _source_key(relative: str) -> str:
    return f"{SOURCE_PREFIX}{relative}"


def _resolve_load(
    requested: str,
    relative_source: str,
    root: Path,
) -> str:
    requested_path = Path(requested).expanduser()
    if requested_path.is_absolute() or requested_path.suffix.lower() != ".rif":
        raise ValueError(
            f"@LOAD inválido en {relative_source}: se esperaba una ruta .rif local, "
            f"se recibió {requested!r}."
        )

    candidate = (root / Path(relative_source).parent / requested_path).resolve(strict=False)
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(
            f"@LOAD en {relative_source} intenta salir del proyecto: {requested!r}."
        ) from exc
    if not candidate.is_file():
        raise FileNotFoundError(
            f"@LOAD en {relative_source} referencia un archivo inexistente: {requested!r}."
        )
    return _source_key(PurePosixPath(relative.as_posix()).as_posix())


def _scan_loads(relative: str, path: Path, root: Path) -> tuple[str, ...]:
    dependencies: list[str] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        match = _LOAD_RE.match(line)
        if match is None:
            continue
        try:
            dependency = _resolve_load(match.group(1), relative, root)
        except (FileNotFoundError, ValueError) as exc:
            raise type(exc)(f"{exc} (línea {line_number})") from exc
        if dependency not in dependencies:
            dependencies.append(dependency)
    return tuple(dependencies)


def _dependency_index(
    entrypoint: Path,
    files: tuple[tuple[str, Path], ...],
) -> tuple[dict[str, tuple[str, ...]], tuple[str, ...]]:
    """Build and validate a dependency-first index for every local source."""

    root = entrypoint.parent
    graph = {
        _source_key(relative): _scan_loads(relative, path, root)
        for relative, path in files
    }
    entry_key = _source_key(entrypoint.relative_to(root).as_posix())
    order: list[str] = []
    visiting: list[str] = []
    visited: set[str] = set()

    def visit(source: str) -> None:
        if source in visited:
            return
        if source in visiting:
            cycle = " -> ".join((*visiting, source))
            raise ValueError(f"Ciclo de @LOAD detectado al empaquetar: {cycle}")
        visiting.append(source)
        for dependency in graph[source]:
            if dependency not in graph:
                raise ValueError(
                    f"El índice de @LOAD referencia una fuente no incluida: {dependency}"
                )
            visit(dependency)
        visiting.pop()
        visited.add(source)
        order.append(source)

    visit(entry_key)
    for source in sorted(graph):
        visit(source)
    return graph, tuple(order)


def _manifest_for(
    entrypoint: Path,
    files: tuple[tuple[str, Path], ...],
    compiled_data: bytes | None = None,
) -> PackManifest:
    load_graph, dependency_order = _dependency_index(entrypoint, files)
    entries: list[PackEntry] = []
    for relative, path in files:
        data = path.read_bytes()
        key = _source_key(relative)
        entries.append(
            PackEntry(
                path=key,
                size=len(data),
                sha256=_sha256(data),
                loads=load_graph[key],
            )
        )
    return PackManifest(
        name=entrypoint.stem,
        version="1.0.0",
        entrypoint=f"{SOURCE_PREFIX}{entrypoint.relative_to(entrypoint.parent).as_posix()}",
        files=tuple(entries),
        load_graph=load_graph,
        dependency_order=dependency_order,
        compiled=(
            PackEntry(
                path="compiled/program.sqlite3",
                size=len(compiled_data),
                sha256=_sha256(compiled_data),
            )
            if compiled_data is not None
            else None
        ),
    )


def _build_compiled_database(entrypoint: Path) -> bytes:
    """Compile a source project in an isolated global context."""

    try:
        # Direct ``rif --pack`` must bootstrap the VNMA vendor projection before
        # importing MIR/Gram. Under ``vnma run`` this is already initialized.
        import vendor  # noqa: F401
        from Frontend import globals as rif_globals
        from MIR import compile_source
        from MIR.compiled import build_database
        from MIR import compiler as compiler_module
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "No se pudo precompilar el paquete: instala Gram con 'vnma install'."
        ) from exc

    mutable_names = (
        "DEFINES",
        "TABLES",
        "RULES",
        "SUPPORTS",
        "ASM_VARIANTS",
        "LOADED_SOURCES",
        "ACTIVE_SOURCES",
        "VARIANT_STACK",
    )
    previous = {
        "STACK": rif_globals.STACK,
        "STACK_SIZE": rif_globals.STACK_SIZE,
        "CONFIG": rif_globals.CONFIG,
        "LINKER": rif_globals.LINKER,
        "SOURCE_PROVIDER": rif_globals.SOURCE_PROVIDER,
        **{name: getattr(rif_globals, name) for name in mutable_names},
        "SOURCE_TEXTS": dict(compiler_module.SOURCE_TEXTS),
    }
    try:
        rif_globals.STACK = None
        rif_globals.STACK_SIZE = None
        rif_globals.CONFIG = None
        rif_globals.LINKER = None
        rif_globals.SOURCE_PROVIDER = None
        rif_globals.DEFINES = set()
        rif_globals.TABLES = {}
        rif_globals.RULES = {}
        rif_globals.SUPPORTS = {}
        rif_globals.ASM_VARIANTS = {}
        rif_globals.LOADED_SOURCES = {}
        rif_globals.ACTIVE_SOURCES = []
        rif_globals.VARIANT_STACK = []
        compiler_module.SOURCE_TEXTS.clear()
        program = compile_source(entrypoint)
        return build_database(program, source_root=entrypoint.parent)
    finally:
        for name, value in previous.items():
            if name == "SOURCE_TEXTS":
                compiler_module.SOURCE_TEXTS.clear()
                compiler_module.SOURCE_TEXTS.update(value)
            else:
                setattr(rif_globals, name, value)


def _zip_info(name: str) -> zipfile.ZipInfo:
    """Create deterministic ZIP metadata independent of filesystem time."""

    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.create_system = 0
    info.external_attr = 0o100644 << 16
    return info


def create_pack(
    source: str | Path,
    output: str | Path | None = None,
    *,
    precompile: bool = False,
) -> Path:
    """Create a reproducible ``.pack`` from the project containing ``source``.

    ``precompile=True`` adds the SQLite/MIR cache used by the normal ``rif
    --pack`` command. The default remains source-only for low-level callers
    that only need the archive and dependency graph.
    """

    entrypoint = _canonical_path(source)
    if not entrypoint.is_file():
        raise FileNotFoundError(f"Archivo RIF no encontrado: {entrypoint}")
    if entrypoint.suffix.lower() != ".rif":
        raise ValueError(f"El entrypoint del paquete debe ser .rif: {entrypoint}")

    files = _project_files(entrypoint)
    compiled_data = _build_compiled_database(entrypoint) if precompile else None
    manifest = _manifest_for(entrypoint, files, compiled_data)
    target = _canonical_path(output) if output is not None else entrypoint.with_suffix(".pack")
    target.parent.mkdir(parents=True, exist_ok=True)

    fd, temporary_name = tempfile.mkstemp(
        prefix=f".{target.stem}.",
        suffix=".pack.tmp",
        dir=target.parent,
    )
    os.close(fd)
    temporary = Path(temporary_name)
    try:
        with zipfile.ZipFile(
            temporary,
            mode="w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as archive:
            manifest_bytes = (
                json.dumps(
                    manifest.as_dict(),
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                ).encode("utf-8")
                + b"\n"
            )
            archive.writestr(_zip_info(MANIFEST_NAME), manifest_bytes)
            if compiled_data is not None:
                archive.writestr(_zip_info("compiled/program.sqlite3"), compiled_data)
            for relative, path in files:
                archive.writestr(
                    _zip_info(f"{SOURCE_PREFIX}{relative}"),
                    path.read_bytes(),
                )
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()

    return target


def read_pack(path: str | Path, *, verify: bool = True) -> PackManifest:
    """Read and optionally verify a ``.pack`` manifest and its source hashes."""

    package = _canonical_path(path)
    if not package.is_file():
        raise FileNotFoundError(f"Paquete RIF no encontrado: {package}")

    with zipfile.ZipFile(package, mode="r") as archive:
        try:
            manifest_data = json.loads(archive.read(MANIFEST_NAME).decode("utf-8"))
        except KeyError as exc:
            raise ValueError("El paquete RIF no contiene manifest.json.") from exc
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("manifest.json no es JSON válido.") from exc

        if not isinstance(manifest_data, dict):
            raise ValueError("manifest.json debe contener un objeto JSON.")
        manifest = PackManifest.from_dict(manifest_data)
        names = set(archive.namelist())
        expected = {entry.path for entry in manifest.files}
        if manifest.entrypoint not in expected:
            raise ValueError("El entrypoint no está incluido en el paquete.")

        for entry in manifest.files:
            normalized = PurePosixPath(entry.path)
            if (
                not entry.path.startswith(SOURCE_PREFIX)
                or normalized.is_absolute()
                or ".." in normalized.parts
            ):
                raise ValueError(f"Ruta de fuente inválida en el paquete: {entry.path}")
            if entry.path not in names:
                raise ValueError(f"Falta el archivo declarado por el manifiesto: {entry.path}")
            if not verify:
                continue
            data = archive.read(entry.path)
            if len(data) != entry.size or _sha256(data) != entry.sha256:
                raise ValueError(f"Hash inválido para {entry.path}")

        if manifest.load_graph:
            if set(manifest.load_graph) != expected:
                raise ValueError("El índice de @LOAD no coincide con los archivos del paquete.")
            for source, dependencies in manifest.load_graph.items():
                if tuple(dependencies) != next(
                    entry.loads for entry in manifest.files if entry.path == source
                ):
                    raise ValueError(f"Índice de @LOAD inconsistente para {source}.")
                if any(dependency not in expected for dependency in dependencies):
                    raise ValueError(f"@LOAD apunta fuera del paquete desde {source}.")

            if set(manifest.dependency_order) != expected:
                raise ValueError("El orden de dependencias no cubre el paquete completo.")
            positions = {
                source: index for index, source in enumerate(manifest.dependency_order)
            }
            for source, dependencies in manifest.load_graph.items():
                if any(positions[dependency] >= positions[source] for dependency in dependencies):
                    raise ValueError("El orden de dependencias del paquete es inválido.")

        if manifest.compiled is not None:
            compiled = manifest.compiled
            if not compiled.path.startswith("compiled/"):
                raise ValueError("Ruta de base compilada inválida en el paquete.")
            if compiled.path not in names:
                raise ValueError("Falta la base SQLite compilada del paquete.")
            data = archive.read(compiled.path)
            if len(data) != compiled.size or _sha256(data) != compiled.sha256:
                raise ValueError("Hash inválido para la base SQLite compilada.")

    return manifest


class PackReader:
    """Lector directo de fuentes empaquetadas sin recorrer el filesystem."""

    def __init__(self, path: str | Path, *, verify: bool = True) -> None:
        self.path = _canonical_path(path)
        self.manifest = read_pack(self.path, verify=verify)
        self._archive = zipfile.ZipFile(self.path, mode="r")
        self._known_sources = {entry.path for entry in self.manifest.files}

    def close(self) -> None:
        self._archive.close()

    def __enter__(self) -> "PackReader":
        return self

    def __exit__(self, exc_type: object, exc_value: object, traceback: object) -> None:
        self.close()

    def _source_key(self, source: str | Path | None) -> str:
        if source is None:
            return self.manifest.entrypoint
        value = str(source).replace("\\", "/")
        if value.startswith("pack://") and "::" in value:
            value = value.rsplit("::", 1)[1]
        value = PurePosixPath(value).as_posix()
        if not value.startswith(SOURCE_PREFIX):
            value = f"{SOURCE_PREFIX}{value.lstrip('/')}"
        normalized = PurePosixPath(value)
        if normalized.is_absolute() or ".." in normalized.parts:
            raise ValueError(f"Ruta de fuente inválida: {source}")
        key = normalized.as_posix()
        if key not in self._known_sources:
            raise FileNotFoundError(f"Fuente no incluida en el paquete: {source}")
        return key

    def virtual_path(self, source: str | Path | None = None) -> str:
        """Return a stable source identifier usable in diagnostics and ASTs."""

        return f"pack://{self.path.as_posix()}::{self._source_key(source)}"

    def resolve_load(self, source: str | Path | None, requested: str) -> str:
        """Resolve an @LOAD through the precomputed package graph."""

        source_key = self._source_key(source)
        requested_path = PurePosixPath(requested.replace("\\", "/"))
        if requested_path.is_absolute() or ".." in requested_path.parts:
            raise ValueError(f"@LOAD intenta salir del paquete: {requested!r}")
        candidate = posixpath.normpath(
            str(PurePosixPath(PurePosixPath(source_key).parent) / requested_path)
        )
        if not candidate.startswith(SOURCE_PREFIX) or candidate == SOURCE_PREFIX.rstrip("/"):
            raise ValueError(f"@LOAD intenta salir del paquete: {requested!r}")
        key = candidate
        if key not in self._known_sources:
            raise FileNotFoundError(f"Fuente no incluida en el paquete: {requested}")
        if key not in self.manifest.load_graph.get(source_key, ()):
            raise ValueError(
                f"@LOAD no coincide con el índice precalculado: {source_key} -> {key}"
            )
        return self.virtual_path(key)

    def resolve_variant(self, name: str, searching: str = "") -> str:
        directory = PurePosixPath(SOURCE_PREFIX)
        if searching:
            directory /= PurePosixPath(searching.replace("\\", "/"))
        key = (directory / f"{name}.rif").as_posix()
        if key not in self._known_sources:
            raise FileNotFoundError(f"Variante no incluida en el paquete: {name}")
        return self.virtual_path(key)

    def source_bytes(self, source: str | Path | None = None) -> bytes:
        """Read one source directly from the package archive."""

        return self._archive.read(self._source_key(source))

    def source_text(self, source: str | Path | None = None) -> str:
        return self.source_bytes(source).decode("utf-8")

    def dependencies(self, source: str | Path | None = None) -> tuple[str, ...]:
        return self.manifest.load_graph[self._source_key(source)]

    def ordered_sources(self) -> tuple[str, ...]:
        """Return the precomputed dependency-first source order."""

        return self.manifest.dependency_order

    def compiled_database(self) -> bytes | None:
        if self.manifest.compiled is None:
            return None
        return self._archive.read(self.manifest.compiled.path)

    @property
    def has_compiled_database(self) -> bool:
        return self.manifest.compiled is not None


__all__ = [
    "MANIFEST_NAME",
    "PACK_FORMAT",
    "PACK_FORMAT_VERSION",
    "PackEntry",
    "PackManifest",
    "PackReader",
    "create_pack",
    "read_pack",
]
