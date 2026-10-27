"""High-level RIF parse, process, resolve and output pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from Frontend import RIF_LANG_SESSION, globals
from Frontend.processor import process
from pack import PackReader
from rif_limits import COMPILATION_LOCK, resolve_limits

from . import compiler as compiler_module
from .compiler import compile_rules
from .compiled import load_database
from .instructions import CompiledRuleSet
from .output import AssemblyImage
from .runtime import ExecutionResult, RIFMachine


MAX_SOURCE_BYTES = 16 << 20


@dataclass
class Compilation:
    source_path: Path
    program: CompiledRuleSet
    image: AssemblyImage | None = None


def _reset_context() -> None:
    """Start an independent target compilation in the process."""

    globals.STACK = None
    globals.STACK_SIZE = None
    globals.DEFINES.clear()
    globals.TABLES.clear()
    globals.RULES.clear()
    globals.CONFIG = None
    globals.LINKER = None
    globals.SUPPORTS.clear()
    globals.ASM_VARIANTS.clear()
    globals.LOADED_SOURCES.clear()
    globals.ACTIVE_SOURCES.clear()
    globals.VARIANT_STACK.clear()
    globals.SOURCE_PROVIDER = None
    globals.INSERTS.clear()
    globals.BEFORE.clear()


def parse_source(path: str | Path):
    with COMPILATION_LOCK:
        source_path = Path(path).expanduser().resolve()
        if source_path.suffix.lower() == ".pack":
            with PackReader(source_path) as package:
                source = package.source_text()
                source_name = package.virtual_path()
                RIF_LANG_SESSION.load()
                tokens = RIF_LANG_SESSION.tokenize(source, source_name)
                ast = RIF_LANG_SESSION.parse(tokens, source_name)
                return ast, source_path
        if not source_path.is_file():
            raise FileNotFoundError(f"Archivo RIF no encontrado: {source_path}")
        if source_path.stat().st_size > resolve_limits().cap(MAX_SOURCE_BYTES):
            raise ValueError(f"La fuente RIF excede el límite de tamaño: {source_path}")
        source = source_path.read_text(encoding="utf-8")
        RIF_LANG_SESSION.load()
        tokens = RIF_LANG_SESSION.tokenize(source, str(source_path))
        return RIF_LANG_SESSION.parse(tokens, str(source_path)), source_path


def compile_source(path: str | Path) -> CompiledRuleSet:
    """Compile a RIF definition source (``.rif`` or ``.pack``).

    The returned object is the internal compiled Rule set. It is not the
    external MIR program that those Rules will consume in the next phase.
    """
    with COMPILATION_LOCK:
        _reset_context()
        source_path = Path(path).expanduser().resolve()
        if source_path.suffix.lower() == ".pack":
            return compile_pack(source_path)
        ast, source_path = parse_source(path)
        process(ast, source_path=source_path, project_root=source_path.parent)
        return compile_rules(resolve=True)


def compile_pack(path: str | Path) -> CompiledRuleSet:
    """Compile a .pack entrypoint using its precomputed source index."""

    with COMPILATION_LOCK:
        _reset_context()
        package_path = Path(path).expanduser().resolve()
        with PackReader(package_path) as package:
            compiled_database = package.compiled_database()
            if compiled_database is not None:
                return load_database(
                    compiled_database,
                    expected_fingerprint=package.manifest.content_sha256,
                )
            previous_sources = dict(compiler_module.SOURCE_TEXTS)
            compiler_module.SOURCE_TEXTS.update(
                {
                    package.virtual_path(entry.path): package.source_text(entry.path)
                    for entry in package.manifest.files
                }
            )
            source_name = package.virtual_path()
            source = package.source_text()
            try:
                RIF_LANG_SESSION.load()
                tokens = RIF_LANG_SESSION.tokenize(source, source_name)
                ast = RIF_LANG_SESSION.parse(tokens, source_name)
                process(
                    ast,
                    source_path=source_name,
                    source_provider=package,
                )
                return compile_rules(resolve=True)
            finally:
                compiler_module.SOURCE_TEXTS.clear()
                compiler_module.SOURCE_TEXTS.update(previous_sources)


def compile_definition(path: str | Path) -> CompiledRuleSet:
    """Explicit name for compiling a ``.rif``/``.pack`` target definition."""

    return compile_source(path)


def compile_project(path: str | Path) -> Compilation:
    program = compile_source(path)
    if program.context.config is None:
        raise RuntimeError("El proyecto requiere @config para crear una salida por secciones.")
    source_path = Path(path).expanduser().resolve()
    return Compilation(source_path, program, AssemblyImage(program.context.config))


def execute_rule(
    compilation: Compilation,
    rule_name: str,
    tokens: Iterable[object],
    *,
    section: str | None = None,
) -> ExecutionResult:
    if compilation.image is None:
        raise RuntimeError("La compilación no tiene AssemblyImage.")
    machine = RIFMachine(
        compilation.program,
        emitter=compilation.image.emitter(section),
    )
    return machine.execute(rule_name, tokens)  # type: ignore[arg-type]


__all__ = [
    "Compilation",
    "parse_source",
    "compile_source",
    "compile_definition",
    "compile_pack",
    "compile_project",
    "execute_rule",
]
