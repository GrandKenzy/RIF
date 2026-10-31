"""Compiler and runtime representation for PCP-I binary images."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import struct

from rif_limits import resolve_limits


MAX_PCPI_BYTES = 128 << 20
PCPI_VERSION = 1
_HEADER = struct.Struct("<BQIBBI")
_PIT = struct.Struct("<HH")
PCPI_HEADER_SIZE = _HEADER.size

BITORDER_LSB = 0
BITORDER_MSB = 1
ENDIAN_LITTLE = 0
ENDIAN_BIG = 1


class PCPIError(ValueError):
    """A PCP-I container is malformed or cannot be compiled."""


@dataclass(frozen=True)
class PCPIPit:
    """A fixed-size byte range in the PCP-I image."""

    address: int
    size: int
    name: str | None = None

    @property
    def end(self) -> int:
        return self.address + self.size


@dataclass(frozen=True)
class CompiledPCPI:
    """Validated PCP-I data ready for filling or serialization."""

    version: int
    image_size: int
    padding: bytes
    bitorder: int
    endianness: int
    image: bytes
    pits: tuple[PCPIPit, ...]

    def fill(self, index: int, value: bytes | bytearray | memoryview) -> bytes:
        """Return the image with one pit replaced by an exact byte payload."""

        try:
            pit = self.pits[index]
        except IndexError as exc:
            raise PCPIError(f"No existe el pit {index}.") from exc
        replacement = bytes(value)
        if len(replacement) != pit.size:
            raise PCPIError(
                f"El pit {index} requiere {pit.size} bytes; "
                f"se recibieron {len(replacement)}."
            )
        output = bytearray(self.image)
        output[pit.address : pit.end] = replacement
        return bytes(output)

    def render(self, values: dict[int, bytes] | None = None) -> bytes:
        """Return padding plus image, optionally filling pits by index."""

        output = bytearray(self.image)
        for index, value in (values or {}).items():
            try:
                pit = self.pits[index]
            except IndexError as exc:
                raise PCPIError(f"No existe el pit {index}.") from exc
            replacement = bytes(value)
            if len(replacement) != pit.size:
                raise PCPIError(
                    f"El pit {index} requiere {pit.size} bytes; "
                    f"se recibieron {len(replacement)}."
                )
            output[pit.address : pit.end] = replacement
        return self.padding + bytes(output)

    def to_bytes(self) -> bytes:
        """Serialize the validated image in the fixed v1 layout."""

        header = _HEADER.pack(
            self.version,
            self.image_size,
            len(self.padding),
            self.bitorder,
            self.endianness,
            len(self.pits),
        )
        table = b"".join(_PIT.pack(pit.address, pit.size) for pit in self.pits)
        return header + self.padding + self.image + table


def _maximum_bytes() -> int:
    return resolve_limits().cap(MAX_PCPI_BYTES)


def _ensure_size(value: int, label: str, maximum: int) -> None:
    if value < 0 or value > maximum:
        raise PCPIError(f"{label} excede el límite de recursos configurado.")


def _validate_pits(pits: tuple[PCPIPit, ...], image_size: int) -> None:
    ordered = sorted(pits, key=lambda pit: pit.address)
    previous: PCPIPit | None = None
    for index, pit in enumerate(pits):
        if pit.size == 0:
            raise PCPIError(f"El pit {index} no puede tener tamaño cero.")
        if pit.end > image_size:
            raise PCPIError(
                f"El pit {index} termina fuera de la imagen "
                f"({pit.end} > {image_size})."
            )
    for pit in ordered:
        if previous is not None and previous.end > pit.address:
            raise PCPIError("Los pits no pueden solaparse.")
        previous = pit


def parse_pcpi(data: bytes | bytearray | memoryview) -> CompiledPCPI:
    """Parse and strictly validate a binary PCP-I container."""

    raw = bytes(data)
    maximum = _maximum_bytes()
    _ensure_size(len(raw), "La PCP-I", maximum)
    if len(raw) < _HEADER.size:
        raise PCPIError("La PCP-I no contiene un header completo.")

    version, image_size, padding_size, bitorder, endianness, pit_count = (
        _HEADER.unpack_from(raw)
    )
    if version != PCPI_VERSION:
        raise PCPIError(f"Versión PCP-I no soportada: {version}.")
    if bitorder not in {BITORDER_LSB, BITORDER_MSB}:
        raise PCPIError(f"Modo de bits PCP-I no válido: {bitorder}.")
    if endianness not in {ENDIAN_LITTLE, ENDIAN_BIG}:
        raise PCPIError(f"Endianidad PCP-I no válida: {endianness}.")
    if image_size > 0x10000:
        raise PCPIError("La imagen excede el espacio direccionable por pits de 16 bits.")

    _ensure_size(image_size, "La imagen", maximum)
    _ensure_size(padding_size, "El padding", maximum)
    if pit_count > (maximum // _PIT.size):
        raise PCPIError("La tabla de pits excede el límite de recursos configurado.")

    image_start = _HEADER.size + padding_size
    image_end = image_start + image_size
    table_size = pit_count * _PIT.size
    expected_size = image_end + table_size
    if expected_size != len(raw):
        raise PCPIError(
            "El tamaño de la PCP-I no coincide con el header y pit_count "
            f"(esperado {expected_size}, recibido {len(raw)})."
        )

    padding = raw[_HEADER.size:image_start]
    image = raw[image_start:image_end]
    pits = tuple(
        PCPIPit(address, size)
        for address, size in struct.iter_unpack(
            "<HH", raw[image_end:]
        )
    )
    _validate_pits(pits, image_size)
    return CompiledPCPI(
        version=version,
        image_size=image_size,
        padding=padding,
        bitorder=bitorder,
        endianness=endianness,
        image=image,
        pits=pits,
    )


def load_pcpi_file(source: str | Path) -> CompiledPCPI:
    """Load and validate either a source ``.pci`` or compiled ``.pcic`` file."""

    source_path = Path(source)
    if not source_path.is_file():
        raise FileNotFoundError(f"No se encontró la PCP-I: {source_path}")
    maximum = _maximum_bytes()
    if source_path.stat().st_size > maximum:
        raise PCPIError("La PCP-I excede el límite de recursos configurado.")
    return parse_pcpi(source_path.read_bytes())


__all__ = [
    "BITORDER_LSB",
    "BITORDER_MSB",
    "CompiledPCPI",
    "ENDIAN_BIG",
    "ENDIAN_LITTLE",
    "MAX_PCPI_BYTES",
    "PCPI_HEADER_SIZE",
    "PCPIError",
    "PCPIPit",
    "PCPI_VERSION",
    "load_pcpi_file",
    "parse_pcpi",
]
