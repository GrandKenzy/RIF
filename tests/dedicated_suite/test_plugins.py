from __future__ import annotations

import importlib.util
import struct
import tempfile
import unittest
import wave
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from plugins import PluginError, convert_audio, convert_font, convert_image


HAS_PILLOW = importlib.util.find_spec("PIL") is not None
HAS_AUDIO = (
    importlib.util.find_spec("soundfile") is not None
    and importlib.util.find_spec("numpy") is not None
)
FONT_CANDIDATES = (
    Path("C:/Windows/Fonts/arial.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
)
FONT_FIXTURE = next((path for path in FONT_CANDIDATES if path.is_file()), None)


class PluginInputTests(unittest.TestCase):
    def test_plugins_reject_urls_and_bytes(self) -> None:
        with self.assertRaises(PluginError):
            convert_image("https://example.com/image.png")
        with self.assertRaises(PluginError):
            convert_audio(b"local.wav")

    def test_font_bytes_copies_ttf_without_a_rasterizer(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "font.ttf"
            source.write_bytes(b"ttf-bytes")
            self.assertEqual(convert_font(source, "BYTES"), b"ttf-bytes")


@unittest.skipUnless(HAS_PILLOW, "Pillow no está instalado")
class ImagePluginTests(unittest.TestCase):
    def test_image_is_converted_to_row_major_rgba8888(self) -> None:
        from PIL import Image

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "pixel.png"
            Image.new("RGBA", (2, 1), (1, 2, 3, 4)).save(source)
            result = convert_image(source)

        self.assertIsInstance(result, bytes)
        self.assertEqual(result, bytes((1, 2, 3, 4)) * 2)

    def test_image_is_converted_to_bgrx8888_with_transparency_over_black(self) -> None:
        from PIL import Image

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "pixel.png"
            Image.new("RGBA", (2, 1), (10, 20, 30, 128)).save(source)
            result = convert_image(source, "BGRX8888")

        self.assertEqual(result, bytes((15, 10, 5, 0)) * 2)

    def test_image_is_converted_to_gba_bgr555_little_endian(self) -> None:
        from PIL import Image

        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "pixel.png"
            image = Image.new("RGBA", (3, 1))
            image.putdata(((255, 0, 0, 255), (0, 255, 0, 255), (0, 0, 255, 255)))
            image.save(source)
            result = convert_image(source, "BGR555")

        self.assertEqual(result, bytes.fromhex("1f00e003007c"))


@unittest.skipUnless(HAS_PILLOW and FONT_FIXTURE is not None, "Pillow o una fuente TTF no están instalados")
class FontPluginTests(unittest.TestCase):
    def test_font_bitmap_mono1_is_a_grid_atlas(self) -> None:
        result = convert_font(
            FONT_FIXTURE,
            "BITMAP",
            pixel_format="MONO1",
            size=8,
            glyphs="AB",
            cell_width=8,
            cell_height=8,
            columns=2,
        )

        self.assertEqual(len(result), 16)
        self.assertTrue(any(result))


@unittest.skipUnless(HAS_AUDIO, "soundfile/numpy no están instalados")
class AudioPluginTests(unittest.TestCase):
    def test_audio_is_converted_to_interleaved_pcm16le(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "tone.wav"
            with wave.open(str(source), "wb") as stream:
                stream.setnchannels(1)
                stream.setsampwidth(2)
                stream.setframerate(8000)
                stream.writeframes(struct.pack("<hh", -2, 3))
            result = convert_audio(source)

        self.assertIsInstance(result, bytes)
        self.assertEqual(result, struct.pack("<hh", -2, 3))

    def test_audio_rejects_containers_outside_wav_flac_and_ogg(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "audio.bin"
            source.write_bytes(b"placeholder")
            info = SimpleNamespace(format="MP3", frames=1, channels=1, samplerate=8000)
            with patch("soundfile.info", return_value=info):
                with self.assertRaisesRegex(PluginError, "WAV, FLAC u OGG"):
                    convert_audio(source)


if __name__ == "__main__":
    unittest.main()
