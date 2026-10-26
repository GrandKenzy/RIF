"""Entry points for compiling an external MIR program against RIF Rules."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from gram import lexer

from Frontend import RIF_LANG_SESSION, globals
from pack import PackReader

from .function_context import RIFFunctionContext
from .functions import FunctionModule, load_function_file, load_function_source
from .instructions import CompiledRuleSet
from .output import AssemblyImage
from .pipeline import compile_definition
from .runtime import ExecutionResult, RIFMachine


class MIRInputError(ValueError):
    """An external MIR input or linker-extension error."""


@dataclass(frozen=True)
class PreparedTarget:
    """A compiled target and its optional loaded ``funcs.py`` module."""

    program: CompiledRuleSet
    target_path: Path | None
    function_module: FunctionModule | None = None


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


def tokenize_mir(source: str, name: str = "<memory>") -> tuple[lexer.TokenType, ...]:
    """Tokenize MIR once for callers that do not already have tokens."""

    if not isinstance(source, str):
        raise TypeError("El MIR fuente debe ser str.")
    RIF_LANG_SESSION.load()
    return tuple(RIF_LANG_SESSION.tokenize(source, name))


def prepare_target(path: str | Path) -> PreparedTarget:
    """Compile a ``.rif``/``.pack`` and load its sibling/package funcs.py."""

    target_path = Path(path).expanduser().resolve()
    if target_path.suffix.lower() not in {".rif", ".pack"}:
        raise MIRInputError("La definición RIF debe terminar en .rif o .pack.")
    program = compile_definition(target_path)
    function_module: FunctionModule | None = None
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
    return PreparedTarget(program, target_path, function_module)


def _prepare_target(
    target: PreparedTarget | CompiledRuleSet | str | Path,
) -> PreparedTarget:
    if isinstance(target, PreparedTarget):
        return target
    if isinstance(target, CompiledRuleSet):
        return PreparedTarget(target, None)
    return prepare_target(target)


def _require_target_config() -> globals.ConfigData:
    if globals.CONFIG is None:
        raise MIRInputError("La definición RIF requiere un bloque @config.")
    return globals.CONFIG


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
    config = globals.CONFIG
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
    config = _require_target_config()
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
    token_stream = tuple(tokens)
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

    return MIRCompilation(
        program=program,
        image=image,
        executions=tuple(executions),
        section=selected_section,
        binary=image.binary(selected_section),
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
    prepared = _prepare_target(target)
    _config = _require_target_config()
    if globals.LINKER is None:
        raise MIRInputError("La entrada por archivo requiere un bloque @linker.")
    linker = globals.LINKER
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
        Path(output).expanduser().resolve().write_bytes(result.binary)
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
