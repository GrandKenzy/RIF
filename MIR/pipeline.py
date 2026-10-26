"""High-level RIF parse, process, resolve and output pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from Frontend import RIF_LANG_SESSION, globals
from Frontend.processor import process
from pack import PackReader

from . import compiler as compiler_module
from .compiler import compile_rules
from .compiled import load_database
from .instructions import ProgramIR
from .output import AssemblyImage
from .runtime import ExecutionResult, RIFMachine


@dataclass
class Compilation:
    source_path: Path
    program: ProgramIR
    image: AssemblyImage | None = None


def parse_source(path: str | Path):
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
    source = source_path.read_text(encoding="utf-8")
    RIF_LANG_SESSION.load()
    tokens = RIF_LANG_SESSION.tokenize(source, str(source_path))
    return RIF_LANG_SESSION.parse(tokens, str(source_path)), source_path


def compile_source(path: str | Path) -> ProgramIR:
    source_path = Path(path).expanduser().resolve()
    if source_path.suffix.lower() == ".pack":
        return compile_pack(source_path)
    ast, source_path = parse_source(path)
    process(ast, source_path=source_path)
    return compile_rules(resolve=True)


def compile_pack(path: str | Path) -> ProgramIR:
    """Compile a .pack entrypoint using its precomputed source index."""

    package_path = Path(path).expanduser().resolve()
    with PackReader(package_path) as package:
        compiled_database = package.compiled_database()
        if compiled_database is not None:
            return load_database(compiled_database)
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


def compile_project(path: str | Path) -> Compilation:
    program = compile_source(path)
    if globals.CONFIG is None:
        raise RuntimeError("El proyecto requiere @config para crear una salida por secciones.")
    source_path = Path(path).expanduser().resolve()
    return Compilation(source_path, program, AssemblyImage(globals.CONFIG))


def execute_rule(
    compilation: Compilation,
    rule_name: str,
    tokens: Iterable[object],
    *,
    section: str | None = None,
    functions: dict[str, object] | None = None,
) -> ExecutionResult:
    if compilation.image is None:
        raise RuntimeError("La compilación no tiene AssemblyImage.")
    machine = RIFMachine(
        compilation.program,
        emitter=compilation.image.emitter(section),
        functions=functions,
    )
    return machine.execute(rule_name, tokens)  # type: ignore[arg-type]


__all__ = [
    "Compilation",
    "parse_source",
    "compile_source",
    "compile_pack",
    "compile_project",
    "execute_rule",
]
