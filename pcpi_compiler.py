"""RIF-backed compiler for textual PCP-I source files."""

from __future__ import annotations

from dataclasses import dataclass, replace
import os
from pathlib import Path
import tempfile

from MIR import compile_definition, compile_mir_source

from pcpi import (
    BITORDER_LSB,
    BITORDER_MSB,
    CompiledPCPI,
    ENDIAN_BIG,
    ENDIAN_LITTLE,
    PCPI_HEADER_SIZE,
    PCPIPit,
    PCPIError,
    parse_pcpi,
)
from rif_limits import resolve_limits


@dataclass(frozen=True)
class PCPISourceCompilation:
    """Compiled PCP-I plus source-level pit names for API callers."""

    source: Path
    entry_rule: str
    image: CompiledPCPI


def _entry_rule(program: object, requested: str | None) -> str:
    rules = getattr(program, "rules", {})
    if requested:
        if requested not in rules:
            raise PCPIError(f"La Rule PCP-I '{requested}' no existe.")
        return requested
    for candidate in ("pcpi", "image"):
        if candidate in rules:
            return candidate
    if len(rules) == 1:
        return next(iter(rules))
    names = ", ".join(sorted(rules)) or "ninguna"
    raise PCPIError(
        "La fuente PCP-I debe declarar una Rule 'pcpi' o 'image', "
        f"o indicar una entrada explícita. Rules disponibles: {names}."
    )


def _image_pits(compilation: object) -> tuple[PCPIPit, ...]:
    image = compilation.image
    if image is None:
        raise PCPIError("RIF no produjo una imagen para la PCP-I.")
    image.layout()
    pits: list[PCPIPit] = []
    for section_name in image.config.sections:
        section = image.sections[section_name]
        section_offset = section.file_offset
        for name, span in section.buffer.regions.items():
            if span.offset % 8 or span.width % 8:
                raise PCPIError(
                    f"El pit '{name}' no está alineado a bytes "
                    f"({span.offset}:{span.width} bits)."
                )
            address = section_offset + span.offset // 8
            size = span.width // 8
            if address > 0xFFFF or size > 0xFFFF:
                raise PCPIError(
                    f"El pit '{name}' no cabe en la representación de 16 bits."
                )
            pits.append(PCPIPit(address, size, name))
    return tuple(sorted(pits, key=lambda pit: (pit.address, pit.name or "")))


def compile_pcpi_source(
    source: str | Path,
    *,
    entry_rule: str | None = None,
) -> PCPISourceCompilation:
    """Compile a textual PCP-I definition using the public RIF pipeline."""

    source_path = Path(source).expanduser().resolve()
    if not source_path.is_file():
        raise FileNotFoundError(f"No se encontró la fuente PCP-I: {source_path}")
    program = compile_definition(source_path)
    config = program.context.config
    if config is None:
        raise PCPIError("La fuente PCP-I requiere un bloque @block config.")
    selected_rule = _entry_rule(program, entry_rule)
    compilation = compile_mir_source(
        program,
        "",
        name=str(source_path),
        section=config.entrysection,
        rule_name=selected_rule,
    )
    pits = _image_pits(compilation)
    image_data = compilation.binary
    maximum = resolve_limits().cap(128 << 20)
    if len(image_data) > maximum:
        raise PCPIError("La imagen PCP-I excede el límite de recursos configurado.")

    alignment = config.sectionalign.get(config.entrysection) or 1
    if alignment <= 0:
        raise PCPIError("La alineación de la imagen PCP-I debe ser positiva.")
    padding_size = (-PCPI_HEADER_SIZE) % alignment
    bitorder = BITORDER_LSB if config.bitorder == "lsb" else BITORDER_MSB
    endianness = ENDIAN_BIG if config.endianness == "big" else ENDIAN_LITTLE
    image = CompiledPCPI(
        version=1,
        image_size=len(image_data),
        padding=b"\x00" * padding_size,
        bitorder=bitorder,
        endianness=endianness,
        image=image_data,
        pits=pits,
    )
    # Round-trip through the strict binary validator before exposing it.
    validated = parse_pcpi(image.to_bytes())
    validated = replace(
        validated,
        pits=tuple(
            PCPIPit(parsed.address, parsed.size, source.name)
            for parsed, source in zip(validated.pits, pits)
        ),
    )
    return PCPISourceCompilation(source_path, selected_rule, validated)


def _write_atomic(path: Path, data: bytes, *, protected: Path) -> Path:
    target = path.expanduser().resolve()
    if target == protected.resolve():
        raise PCPIError("La salida PCP-I no puede sobrescribir la fuente.")
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


def compile_pcpi_source_file(
    source: str | Path,
    output: str | Path | None = None,
    *,
    entry_rule: str | None = None,
) -> Path:
    """Compile textual ``.pci`` source to a binary ``.pcic`` artifact."""

    source_path = Path(source).expanduser().resolve()
    result = compile_pcpi_source(source_path, entry_rule=entry_rule)
    output_path = (
        Path(output).expanduser()
        if output is not None
        else source_path.with_suffix(".pcic")
    )
    return _write_atomic(output_path, result.image.to_bytes(), protected=source_path)


__all__ = [
    "PCPISourceCompilation",
    "compile_pcpi_source",
    "compile_pcpi_source_file",
]
