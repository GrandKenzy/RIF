"""High-level RIF parse, process, resolve and output pipeline."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from Frontend import RIF_LANG_SESSION, globals
from Frontend.processor import process

from .compiler import compile_rules
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
    if not source_path.is_file():
        raise FileNotFoundError(f"Archivo RIF no encontrado: {source_path}")
    source = source_path.read_text(encoding="utf-8")
    RIF_LANG_SESSION.load()
    tokens = RIF_LANG_SESSION.tokenize(source, str(source_path))
    return RIF_LANG_SESSION.parse(tokens, str(source_path)), source_path


def compile_source(path: str | Path) -> ProgramIR:
    ast, source_path = parse_source(path)
    process(ast, source_path=source_path)
    return compile_rules(resolve=True)


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


__all__ = ["Compilation", "parse_source", "compile_source", "compile_project", "execute_rule"]
