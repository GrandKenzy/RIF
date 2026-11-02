"""Deterministic TTF-to-bytes and TTF-to-bitmap conversion."""

from __future__ import annotations

import math
from pathlib import Path

from .paths import PluginError, local_file, output_limit


SUPPORTED_FONT_OUTPUTS = frozenset({"BYTES", "BITMAP"})
SUPPORTED_FONT_PIXEL_FORMATS = frozenset({"MONO1", "GRAY8", "RGBA8888"})
SUPPORTED_FONT_LAYOUTS = frozenset({"GRID"})


def _glyphs(value: str) -> tuple[str, ...]:
    normalized = str(value)
    upper = normalized.upper()
    if upper == "ASCII_PRINTABLE":
        result = tuple(chr(code) for code in range(0x20, 0x7F))
    elif upper == "ASCII":
        result = tuple(chr(code) for code in range(0x00, 0x80))
    else:
        if not normalized:
            raise PluginError("convert_font requiere al menos un glifo.")
        result = tuple(normalized)
    if not result or len(set(result)) != len(result):
        raise PluginError("convert_font requiere glifos únicos y no vacíos.")
    return result


def _pack_mono1(gray: bytes, width: int, height: int) -> bytes:
    stride = (width + 7) // 8
    packed = bytearray(stride * height)
    for y in range(height):
        row = y * width
        output_row = y * stride
        for x in range(width):
            if gray[row + x] >= 128:
                packed[output_row + x // 8] |= 1 << (7 - (x % 8))
    return bytes(packed)


def convert_font(
    source: str | Path,
    output: str = "BYTES",
    *,
    pixel_format: str = "MONO1",
    size: int = 8,
    glyphs: str = "ASCII_PRINTABLE",
    cell_width: int | None = None,
    cell_height: int | None = None,
    layout: str = "GRID",
    columns: int = 16,
) -> bytes:
    """Convert one local TTF into raw bytes or a row-major bitmap atlas."""

    path = local_file(source, "convert_font")
    normalized_output = str(output).upper()
    if normalized_output not in SUPPORTED_FONT_OUTPUTS:
        raise PluginError("convert_font solo admite BYTES o BITMAP.")
    if path.suffix.lower() != ".ttf":
        raise PluginError("convert_font requiere una fuente con extensión .ttf.")
    if normalized_output == "BYTES":
        data = path.read_bytes()
        if len(data) > output_limit():
            raise PluginError("convert_font excede el límite de salida permitido.")
        return data

    normalized_format = str(pixel_format).upper()
    if normalized_format not in SUPPORTED_FONT_PIXEL_FORMATS:
        raise PluginError(
            "convert_font solo admite MONO1, GRAY8 y RGBA8888 para BITMAP."
        )
    normalized_layout = str(layout).upper()
    if normalized_layout not in SUPPORTED_FONT_LAYOUTS:
        raise PluginError("convert_font solo admite layout GRID.")
    if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
        raise PluginError("convert_font requiere un size entero positivo.")
    if isinstance(columns, bool) or not isinstance(columns, int) or columns <= 0:
        raise PluginError("convert_font requiere columns entero positivo.")
    if cell_width is not None and (
        isinstance(cell_width, bool) or not isinstance(cell_width, int) or cell_width <= 0
    ):
        raise PluginError("convert_font requiere cell_width entero positivo.")
    if cell_height is not None and (
        isinstance(cell_height, bool)
        or not isinstance(cell_height, int)
        or cell_height <= 0
    ):
        raise PluginError("convert_font requiere cell_height entero positivo.")

    selected_glyphs = _glyphs(glyphs)
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:
        raise PluginError(
            "convert_font BITMAP requiere Pillow; instala el plugin con `vnma install pillow`."
        ) from exc

    try:
        font = ImageFont.truetype(str(path), size=size)
        ascent, descent = font.getmetrics()
        resolved_height = cell_height or max(1, ascent + descent)
        if cell_width is None:
            resolved_width = max(
                1,
                max(math.ceil(font.getlength(glyph)) for glyph in selected_glyphs),
            )
        else:
            resolved_width = cell_width
        rows = (len(selected_glyphs) + columns - 1) // columns
        atlas_width = resolved_width * columns
        atlas_height = resolved_height * rows
        pixel_count = atlas_width * atlas_height
        channels = 4 if normalized_format == "RGBA8888" else 1
        expected_output = (
            ((atlas_width + 7) // 8) * atlas_height
            if normalized_format == "MONO1"
            else pixel_count * channels
        )
        if expected_output > output_limit():
            raise PluginError("convert_font excede el límite de salida permitido.")

        atlas = Image.new("L", (atlas_width, atlas_height), 0)
        drawer = ImageDraw.Draw(atlas)
        for index, glyph in enumerate(selected_glyphs):
            x = (index % columns) * resolved_width
            y = (index // columns) * resolved_height
            drawer.text((x, y), glyph, font=font, fill=255, anchor="lt")
        gray = atlas.tobytes()
        if normalized_format == "MONO1":
            data = _pack_mono1(gray, atlas_width, atlas_height)
        elif normalized_format == "GRAY8":
            data = gray
        else:
            rgba = Image.new("RGBA", atlas.size, (255, 255, 255, 0))
            rgba.putalpha(atlas)
            data = rgba.tobytes("raw", "RGBA")
    except PluginError:
        raise
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        raise PluginError(f"convert_font no pudo rasterizar {path.name}.") from exc

    if len(data) != expected_output:
        raise PluginError("convert_font produjo una cantidad de bytes inesperada.")
    return data


__all__ = [
    "SUPPORTED_FONT_LAYOUTS",
    "SUPPORTED_FONT_OUTPUTS",
    "SUPPORTED_FONT_PIXEL_FORMATS",
    "convert_font",
]
