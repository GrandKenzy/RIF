"""Deterministic local image-to-target-pixel conversion."""

from __future__ import annotations

from pathlib import Path

from .paths import PluginError, local_file, output_limit


SUPPORTED_IMAGE_FORMATS = frozenset({"RGB888", "RGBA8888", "BGRX8888", "BGR555"})


def convert_image(source: str | Path, pixel_format: str = "RGBA8888") -> bytes:
    """Decode one local image to canonical, row-major target pixels.

    ``BGRX8888`` is stored in framebuffer byte order. ``BGR555`` uses the GBA
    packed pixel layout ``0BBBBBGGGGGRRRRR`` and emits little-endian 16-bit
    pixels. Transparent pixels are composited over black because both formats
    have no alpha channel; non-opaque pixels are premultiplied before packing.
    """

    path = local_file(source, "convert_image")
    normalized_format = str(pixel_format).upper()
    modes = {
        "RGB888": "RGB",
        "RGBA8888": "RGBA",
        "BGRX8888": "RGBA",
        "BGR555": "RGBA",
    }
    if normalized_format not in modes:
        raise PluginError(
            "convert_image solo admite RGB888, RGBA8888, BGRX8888 y BGR555."
        )
    try:
        from PIL import Image, UnidentifiedImageError
    except ImportError as exc:
        raise PluginError(
            "convert_image requiere Pillow; instala el plugin con `vnma install pillow`."
        ) from exc

    try:
        with Image.open(path) as image:
            width, height = image.size
            if width <= 0 or height <= 0:
                raise PluginError("convert_image recibió una imagen sin dimensiones.")
            channels = 3 if normalized_format == "RGB888" else 4
            expected_output = width * height * (
                2 if normalized_format == "BGR555" else channels
            )
            if expected_output > output_limit():
                raise PluginError("convert_image excede el límite de salida permitido.")
            mode = modes[normalized_format]
            rgba = image.convert(mode).tobytes("raw", mode)
            if normalized_format in {"BGRX8888", "BGR555"}:
                converted = bytearray()
                for offset in range(0, len(rgba), 4):
                    red, green, blue, alpha = rgba[offset : offset + 4]
                    if alpha != 255:
                        red = (red * alpha + 127) // 255
                        green = (green * alpha + 127) // 255
                        blue = (blue * alpha + 127) // 255
                    if normalized_format == "BGRX8888":
                        converted.extend((blue, green, red, 0))
                    else:
                        red5 = (red * 31 + 127) // 255
                        green5 = (green * 31 + 127) // 255
                        blue5 = (blue * 31 + 127) // 255
                        pixel = red5 | (green5 << 5) | (blue5 << 10)
                        converted.extend(pixel.to_bytes(2, "little"))
                data = bytes(converted)
            else:
                data = rgba
    except PluginError:
        raise
    except (OSError, UnidentifiedImageError) as exc:
        raise PluginError(f"convert_image no pudo decodificar {path.name}.") from exc

    if len(data) != expected_output:
        raise PluginError("convert_image produjo una cantidad de bytes inesperada.")
    return data


__all__ = ["SUPPORTED_IMAGE_FORMATS", "convert_image"]
