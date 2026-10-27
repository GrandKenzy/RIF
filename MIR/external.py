"""Entry points for compiling an external MIR program against RIF Rules."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

from gram import lexer

from Frontend import RIF_LANG_SESSION, globals
from pack import PackReader
from rif_limits import COMPILATION_LOCK, resolve_limits

from .function_context import RIFFunctionContext
from .functions import FunctionModule, load_function_file, load_function_source
from .instructions import CompiledRuleSet
from .output import AssemblyImage
from .artifacts import apply_before, apply_inserts
from .pipeline import compile_definition
from .runtime import ExecutionResult, RIFMachine


MAX_MIR_SOURCE_BYTES = 64 << 20
MAX_MIR_TOKENS = 4_000_000


class MIRInputError(ValueError):
    """An external MIR input or linker-extension error."""


def _write_binary_atomic(
    output: str | Path,
    data: bytes,
    *,
    protected: tuple[Path, ...],
) -> Path:
    target = Path(output).expanduser().resolve()
    if any(target == item for item in protected):
        raise MIRInputError(f"La salida no puede sobrescribir un archivo de entrada: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        temporary.write_bytes(data)
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()
    return target


@dataclass(frozen=True)
class PreparedTarget:
    """A compiled target and its optional loaded ``funcs.py`` module."""

    program: CompiledRuleSet
    target_path: Path | None
    function_module: FunctionModule | None = None
    assets: dict[str, bytes] = field(default_factory=dict)


@dataclass
class MIRCompilation:
    """Binary result of applying an external MIR program to a RIF target."""

    program: CompiledRuleSet
    image: AssemblyImage
    executions: tuple[ExecutionResult, ...]
    section: str
    binary: bytes
    context: RIFFunctionContext
    target_path: Path | None = None
    mir_path: Path | None = None

    @property
    def section_binary(self) -> bytes:
        """Return only the finalized bytes of the selected section."""

        return self.image.final_binary(self.section)


def tokenize_mir(source: str, name: str = "<memory>") -> tuple[lexer.TokenType, ...]:
    """Tokenize MIR once for callers that do not already have tokens."""

    if not isinstance(source, str):
        raise TypeError("El MIR fuente debe ser str.")
    if len(source.encode("utf-8")) > resolve_limits().cap(MAX_MIR_SOURCE_BYTES):
        raise MIRInputError("El MIR excede el límite de 64 MiB.")
    with COMPILATION_LOCK:
        RIF_LANG_SESSION.load()
        return tuple(RIF_LANG_SESSION.tokenize(source, name))


def prepare_target(path: str | Path) -> PreparedTarget:
    """Compile a ``.rif``/``.pack`` and load its sibling/package funcs.py."""

    target_path = Path(path).expanduser().resolve()
    if target_path.suffix.lower() not in {".rif", ".pack"}:
        raise MIRInputError("La definición RIF debe terminar en .rif o .pack.")
    program = compile_definition(target_path)
    function_module: FunctionModule | None = None
    assets: dict[str, bytes] = {}
    if target_path.suffix.lower() == ".rif":
        function_path = target_path.parent / "funcs.py"
        if function_path.is_file():
            function_module = load_function_file(function_path)
    else:
        with PackReader(target_path) as package:
            function_source = package.function_source()
            if function_source is not None:
                function_module = load_function_source(
                    function_source,
                    package.virtual_function_path(),
                )
            assets = package.assets()
    return PreparedTarget(program, target_path, function_module, assets)


def _prepare_target(
    target: PreparedTarget | CompiledRuleSet | str | Path,
) -> PreparedTarget:
    if isinstance(target, PreparedTarget):
        return target
    if isinstance(target, CompiledRuleSet):
        return PreparedTarget(target, None)
    return prepare_target(target)


def _require_target_config(program: CompiledRuleSet) -> globals.ConfigData:
    if program.context.config is None:
        raise MIRInputError("La definición RIF requiere un bloque @config.")
    return program.context.config


def _split_lines(
    tokens: Iterable[lexer.TokenType],
) -> tuple[tuple[lexer.TokenType, ...], ...]:
    lines: list[tuple[lexer.TokenType, ...]] = []
    current: list[lexer.TokenType] = []
    for token in tokens:
        if token.token == lexer.Token.EOF:
            break
        if token.token == lexer.Token.NEWLINE:
            if current:
                lines.append(tuple(current))
                current = []
            continue
        current.append(token)
    if current:
        lines.append(tuple(current))
    return tuple(lines)


def _line_number(line: tuple[lexer.TokenType, ...]) -> int | None:
    return getattr(line[0], "line", None) if line else None


def _resolve_rule_name(
    program: CompiledRuleSet,
    line: tuple[lexer.TokenType, ...],
    *,
    line_number: int | None,
) -> str:
    if not line:
        raise MIRInputError("No se puede resolver una línea MIR vacía.")
    value = line[0].value
    if not isinstance(value, str) or not value:
        location = f" en la línea {line_number}" if line_number else ""
        raise MIRInputError(
            f"La primera posición de una línea MIR debe identificar una Rule{location}."
        )
    if value in program.rules:
        return value
    config = program.context.config
    if config is not None and not config.casesensitive:
        folded = value.casefold()
        matches = [name for name in program.rules if name.casefold() == folded]
        if len(matches) == 1:
            return matches[0]
    location = f" en la línea {line_number}" if line_number else ""
    raise MIRInputError(f"No existe una Rule llamada '{value}'{location}.")


def compile_mir_tokens(
    target: PreparedTarget | CompiledRuleSet | str | Path,
    tokens: Iterable[lexer.TokenType],
    *,
    section: str | None = None,
    rule_name: str | None = None,
    mir_path: str | Path | None = None,
) -> MIRCompilation:
    """Compile already-tokenized MIR without lexing or parsing it again.

    With no ``rule_name``, each line is dispatched by its first token value.
    Supplying ``rule_name`` treats the complete token stream as one Rule input.
    """

    prepared = _prepare_target(target)
    program = prepared.program
    config = _require_target_config(program)
    selected_section = section or config.entrysection
    if selected_section not in config.sections:
        raise MIRInputError(f"La sección MIR '{selected_section}' no existe en @config.")

    image = AssemblyImage(config)
    machine = RIFMachine(
        program,
        emitter=image.emitter(selected_section),
        function_module=prepared.function_module,
        section_name=selected_section,
    )
    section_data = image.section(selected_section)
    context = RIFFunctionContext(
        program=program,
        machine=machine,
        image=image,
        section=section_data,
        target_path=prepared.target_path,
        mir_path=Path(mir_path).expanduser().resolve() if mir_path else None,
    )
    machine.bind_function_context(context)
    apply_inserts(
        image,
        program.inserts,
        function_module=prepared.function_module,
        context=context,
        assets=prepared.assets,
    )
    collected: list[lexer.TokenType] = []
    for index, token in enumerate(tokens):
        if index >= MAX_MIR_TOKENS:
            raise MIRInputError(
                f"El MIR excede el límite de {MAX_MIR_TOKENS} tokens."
            )
        collected.append(token)
    token_stream = tuple(collected)
    if rule_name is not None:
        lines = ((
            tuple(
                token
                for token in token_stream
                if token.token not in {lexer.Token.EOF, lexer.Token.NEWLINE}
            ),
        ))
        resolved_names = (rule_name,)
    else:
        lines = _split_lines(token_stream)
        resolved_names = tuple(
            _resolve_rule_name(program, line, line_number=_line_number(line))
            for line in lines
        )

    executions: list[ExecutionResult] = []
    for name, line in zip(resolved_names, lines):
        result = machine.execute_line(name, line)
        if result.position != len(line):
            line_number = _line_number(line)
            location = f" en la línea {line_number}" if line_number else ""
            raise MIRInputError(
                f"La Rule '{name}' dejó {len(line) - result.position} token(s) sin consumir{location}."
            )
        executions.append(result)

    apply_before(
        image,
        machine,
        program.before,
        function_module=prepared.function_module,
        context=context,
    )

    return MIRCompilation(
        program=program,
        image=image,
        executions=tuple(executions),
        section=selected_section,
        binary=image.file_bytes(),
        context=context,
        target_path=prepared.target_path,
        mir_path=context.mir_path,
    )


def compile_mir_source(
    target: PreparedTarget | CompiledRuleSet | str | Path,
    source: str,
    *,
    name: str = "<memory>",
    section: str | None = None,
    rule_name: str | None = None,
    mir_path: str | Path | None = None,
) -> MIRCompilation:
    """Compile MIR text through the shared direct token execution path."""

    return compile_mir_tokens(
        target,
        tokenize_mir(source, name),
        section=section,
        rule_name=rule_name,
        mir_path=mir_path,
    )


def compile_mir_file(
    target: PreparedTarget | CompiledRuleSet | str | Path,
    mir_path: str | Path,
    *,
    output: str | Path | None = None,
    section: str | None = None,
) -> MIRCompilation:
    """Compile one MIR file after validating the target's linker extension."""

    input_path = Path(mir_path).expanduser().resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"Archivo MIR no encontrado: {input_path}")
    if input_path.stat().st_size > resolve_limits().cap(MAX_MIR_SOURCE_BYTES):
        raise MIRInputError("El archivo MIR excede el límite de 64 MiB.")
    prepared = _prepare_target(target)
    _config = _require_target_config(prepared.program)
    if prepared.program.context.linker is None:
        raise MIRInputError("La entrada por archivo requiere un bloque @linker.")
    linker = prepared.program.context.linker
    expected = linker.ext
    if not expected.startswith("."):
        expected = "." + expected
    actual = input_path.suffix
    matches = actual == expected if _config.casesensitive else actual.casefold() == expected.casefold()
    if not matches:
        raise MIRInputError(
            f"El MIR debe usar la extensión '{linker.ext}', no '{actual}'."
        )
    result = compile_mir_source(
        prepared,
        input_path.read_text(encoding="utf-8"),
        name=str(input_path),
        section=section,
        mir_path=input_path,
    )
    result.mir_path = input_path
    if output is not None:
        protected = (input_path,) + (
            (prepared.target_path,) if prepared.target_path is not None else ()
        )
        _write_binary_atomic(output, result.binary, protected=protected)
    return result


def compile_mir(
    target: PreparedTarget | CompiledRuleSet | str | Path,
    mir: str | Iterable[lexer.TokenType],
    *,
    name: str = "<memory>",
    section: str | None = None,
    rule_name: str | None = None,
) -> MIRCompilation:
    """Direct convenience entry point for MIR text or pre-tokenized MIR."""

    if isinstance(mir, str):
        return compile_mir_source(
            target,
            mir,
            name=name,
            section=section,
            rule_name=rule_name,
        )
    return compile_mir_tokens(
        target,
        mir,
        section=section,
        rule_name=rule_name,
    )


__all__ = [
    "MIRInputError",
    "PreparedTarget",
    "MIRCompilation",
    "prepare_target",
    "tokenize_mir",
    "compile_mir",
    "compile_mir_tokens",
    "compile_mir_source",
    "compile_mir_file",
]
