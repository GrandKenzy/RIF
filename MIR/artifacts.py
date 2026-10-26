"""Runtime application of binary preludes and final image patches."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from Frontend import globals

from .bitbuffer import BitBuffer, BitLayout
from .emitter import BitEmitter
from .functions import FunctionModule
from .output import AssemblyImage
from .runtime import RIFMachine


class ArtifactError(RuntimeError):
    """An insert or final patch could not be resolved safely."""


@dataclass(frozen=True)
class BinaryValue:
    data: bytes
    bit_width: int


@dataclass(frozen=True)
class ScalarValue:
    value: int
    width: int


def _hex_to_bytes(value: str) -> bytes:
    normalized = value.removeprefix("0x").replace(" ", "").replace("_", "")
    if not normalized or len(normalized) % 2 or any(char not in "0123456789abcdefABCDEF" for char in normalized):
        raise ArtifactError(".bytes requiere una cadena hexadecimal de bytes completos.")
    return bytes.fromhex(normalized)


def _binary_value(value: str, config: globals.ConfigData) -> BinaryValue:
    if not isinstance(value, str):
        raise ArtifactError("El payload binario debe ser un string.")
    if not value or any(bit not in "01" for bit in value):
        raise ArtifactError("El payload binario debe contener solamente 0 y 1.")
    if len(value) % 8:
        return BinaryValue(b"", len(value))
    buffer = BitBuffer(
        BitLayout(bit_order=config.bitorder, byte_order=config.endianness)
    )
    BitEmitter(buffer=buffer, wordsize=config.wordsize).emit(value, len(value))
    return BinaryValue(buffer.to_bytes(), len(value))


def _file_payload(
    path_value: str,
    source_path: str | None,
    assets: Mapping[str, bytes],
) -> bytes:
    normalized = path_value.replace("\\", "/")
    requested = Path(normalized)
    if requested.is_absolute() or ".." in requested.parts:
        raise ArtifactError(f"El asset '{path_value}' usa una ruta no permitida.")
    asset_key = normalized
    packaged_source = False
    if source_path and source_path.startswith("pack://") and "::" in source_path:
        packaged_source = True
        source_key = source_path.rsplit("::", 1)[1].replace("\\", "/")
        if source_key.startswith("sources/"):
            asset_key = str(Path(source_key.removeprefix("sources/")).parent / Path(normalized)).replace("\\", "/")
    elif source_path and source_path.startswith("sources/"):
        packaged_source = True
        asset_key = str(Path(source_path.removeprefix("sources/")).parent / Path(normalized)).replace("\\", "/")
    if asset_key in assets:
        return bytes(assets[asset_key])
    if packaged_source:
        raise ArtifactError(f"El asset '{path_value}' no está incluido en el paquete.")
    base = Path(source_path).expanduser().resolve().parent if source_path else Path.cwd()
    candidate = (base / path_value).resolve(strict=False)
    try:
        candidate.relative_to(base)
    except ValueError as exc:
        raise ArtifactError(f"El asset '{path_value}' intenta salir del proyecto.") from exc
    if not candidate.is_file():
        raise FileNotFoundError(f"No se encontró el asset binario: {candidate}")
    return candidate.read_bytes()


def apply_inserts(
    image: AssemblyImage,
    inserts: tuple[Any, ...],
    *,
    function_module: FunctionModule | None,
    context: Any,
    assets: Mapping[str, bytes] | None = None,
) -> None:
    """Apply all preludes in declaration order before external MIR runs."""

    config = image.config
    asset_map = assets or {}
    for insert in inserts:
        section_name = insert.section or config.defaultsection
        emitter = image.emitter(section_name)
        if insert.kind == "binary":
            binary = _binary_value(str(insert.value), config)
            emitter.emit(str(insert.value), binary.bit_width)
        elif insert.kind == "bytes":
            for byte in _hex_to_bytes(str(insert.value)):
                emitter.emit(byte, 8)
        elif insert.kind == "file":
            for byte in _file_payload(str(insert.value), insert.source_path, asset_map):
                emitter.emit(byte, 8)
        elif insert.kind == "call":
            if function_module is None:
                raise ArtifactError(
                    f"El insert requiere funcs.py para llamar a '{insert.value}'."
                )
            result = function_module.invoke_payload(str(insert.value), context)
            if isinstance(result, str):
                binary = _binary_value(result, config)
                emitter.emit(result, binary.bit_width)
            else:
                for byte in result:
                    emitter.emit(byte, 8)
        else:
            raise ArtifactError(f"Tipo de insert desconocido: {insert.kind}.")
    image.invalidate_layout()


def _as_int(value: Any, label: str) -> int:
    if isinstance(value, ScalarValue):
        return value.value
    raise ArtifactError(f"{label} requiere un valor numérico.")


def _literal_value(
    expression: dict[str, Any], config: globals.ConfigData
) -> BinaryValue | ScalarValue:
    token = expression.get("token")
    value = expression.get("value")
    if token in {"NUMBER", "DECIMAL"}:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise ArtifactError("El escalar nativo no es numérico.")
        if isinstance(value, float):
            if not value.is_integer():
                raise ArtifactError("Los parches solo aceptan números enteros.")
            value = int(value)
        return ScalarValue(int(value), 1)
    if token == "BOOL":
        raise ArtifactError("Un booleano no puede insertarse como escalar.")
    if token == "STRING":
        if not isinstance(value, str):
            raise ArtifactError("El string nativo no es válido.")
        if value and set(value) <= {"0", "1"}:
            return _binary_value(value, config)
        raise ArtifactError("Un string directo de .rplc debe ser binario.")
    raise ArtifactError("El valor no es válido para una expresión nativa.")


def _label_offsets(machine: RIFMachine, *, virtual: bool = False) -> dict[str, int]:
    labels: dict[str, int] = {}
    rule_addresses = (
        machine.virtual_rule_addresses if virtual else machine.rule_addresses
    )
    regions = (
        machine.emitter.virtual_regions
        if virtual
        else machine.emitter.buffer.regions
    )
    for name, offset in rule_addresses.items():
        labels.setdefault(name, offset // 8)
    for name, span in regions.items():
        labels.setdefault(name, span.offset // 8)
    return labels


def evaluate_expression(
    expression: dict[str, Any],
    *,
    image: AssemblyImage,
    machine: RIFMachine,
    function_module: FunctionModule | None,
    context: Any,
    working: bytes,
) -> BinaryValue | ScalarValue:
    kind = expression.get("kind")
    if kind == "literal":
        return _literal_value(expression, image.config)
    if kind == "calc":
        left = evaluate_expression(
            expression["left"], image=image, machine=machine,
            function_module=function_module, context=context, working=working,
        )
        right = evaluate_expression(
            expression["right"], image=image, machine=machine,
            function_module=function_module, context=context, working=working,
        )
        left_value = _as_int(left, "calc")
        right_value = _as_int(right, "calc")
        value = left_value + right_value if expression["operator"] == "+" else left_value - right_value
        width = max(
            left.width if isinstance(left, ScalarValue) else 1,
            right.width if isinstance(right, ScalarValue) else 1,
        )
        return ScalarValue(value, width)
    if kind == "call":
        if function_module is None:
            raise ArtifactError("La expresión requiere funcs.py para ejecutar CALL.")
        result = function_module.invoke_payload(str(expression["name"]), context)
        if isinstance(result, str):
            return _binary_value(result, image.config)
        return BinaryValue(result, len(result) * 8)
    args = expression.get("args", ())
    if kind == "query":
        offset = _as_int(evaluate_expression(args[0], image=image, machine=machine, function_module=function_module, context=context, working=working), "query")
        size = _as_int(evaluate_expression(args[1], image=image, machine=machine, function_module=function_module, context=context, working=working), "query")
        if offset < 0 or size < 0 or offset + size > len(working):
            raise ArtifactError("#:query está fuera del binario final.")
        return BinaryValue(bytes(working[offset : offset + size]), size * 8)

    image.layout()
    base = _as_int(evaluate_expression(args[0], image=image, machine=machine, function_module=function_module, context=context, working=working), kind)
    target = args[1].get("value") if isinstance(args[1], dict) else None
    if not isinstance(target, str):
        raise ArtifactError(f"#:{kind} requiere un nombre string.")
    address_width = max(1, image.config.addresssize // 8)
    if kind == "qssize":
        try:
            section = image.sections[target]
        except KeyError as exc:
            raise ArtifactError(f"No existe la sección '{target}'.") from exc
        return ScalarValue(base + section.file_offset + section.file_size, address_width)
    if kind in {"qlsize", "qvsize"}:
        labels = _label_offsets(machine, virtual=kind == "qvsize")
        if target not in labels:
            raise ArtifactError(f"No existe el label '{target}'.")
        section_name = machine.section_name or image.config.defaultsection
        section = image.sections[section_name]
        relative = labels[target]
        if kind == "qlsize":
            return ScalarValue(base + section.file_offset + relative, address_width)
        return ScalarValue(base + section.virtual_base + relative, address_width)
    if kind == "qvssize":
        try:
            section = image.sections[target]
        except KeyError as exc:
            raise ArtifactError(f"No existe la sección '{target}'.") from exc
        return ScalarValue(base + section.virtual_base + section.virtual_size, address_width)
    raise ArtifactError(f"Query nativa desconocida: {kind}.")


def _encode_value(
    value: BinaryValue | ScalarValue,
    width: int | None,
    config: globals.ConfigData,
) -> bytes:
    if isinstance(value, BinaryValue):
        if value.bit_width % 8:
            raise ArtifactError(".rplc requiere un payload alineado a bytes.")
        data = value.data
        if width is not None and len(data) != width:
            raise ArtifactError("El ancho del payload no coincide con .rplc.")
        return data
    selected_width = width or value.width
    if selected_width <= 0 or value.value < 0 or value.value >= (1 << (selected_width * 8)):
        raise ArtifactError("El escalar no cabe en el ancho del parche.")
    return value.value.to_bytes(selected_width, config.endianness, signed=False)


def apply_before(
    image: AssemblyImage,
    machine: RIFMachine,
    patches: tuple[Any, ...],
    *,
    function_module: FunctionModule | None,
    context: Any,
) -> bytes:
    """Evaluate and commit all final patches transactionally."""

    working = bytearray(image.layout())
    for patch in patches:
        value = evaluate_expression(
            patch.expression,
            image=image,
            machine=machine,
            function_module=function_module,
            context=context,
            working=bytes(working),
        )
        payload = _encode_value(value, patch.width, image.config)
        end = patch.offset + len(payload)
        if patch.offset < 0 or end > len(working):
            raise ArtifactError(".rplc está fuera del binario final.")
        working[patch.offset:end] = payload
    image.set_final_bytes(bytes(working))
    return bytes(working)


__all__ = ["ArtifactError", "BinaryValue", "ScalarValue", "apply_inserts", "apply_before", "evaluate_expression"]
