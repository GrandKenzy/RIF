from __future__ import annotations

import struct
import tempfile
import unittest
from pathlib import Path

from pcpi import (
    BITORDER_LSB,
    ENDIAN_LITTLE,
    PCPIError,
    PCPIPit,
    compile_pcpi,
    compile_pcpi_file,
    load_pcpi_file,
)
from rif import main as rif_main


HEADER = struct.Struct("<BQIBBI")
PIT = struct.Struct("<HH")


def make_pcpi(
    image: bytes = b"\x00\x00\x00\x00\x00\x00",
    padding: bytes = b"\x00\x00",
    pits: tuple[tuple[int, int], ...] = ((0, 2), (4, 2)),
    *,
    version: int = 1,
) -> bytes:
    header = HEADER.pack(
        version,
        len(image),
        len(padding),
        BITORDER_LSB,
        ENDIAN_LITTLE,
        len(pits),
    )
    return header + padding + image + b"".join(PIT.pack(*pit) for pit in pits)


class PCPITests(unittest.TestCase):
    def test_compiles_and_fills_fixed_size_pits(self) -> None:
        compiled = compile_pcpi(make_pcpi())

        self.assertEqual(compiled.image_size, 6)
        self.assertEqual(compiled.pits, (PCPIPit(0, 2), PCPIPit(4, 2)))
        self.assertEqual(compiled.fill(0, b"AB"), b"AB\x00\x00\x00\x00")
        self.assertEqual(
            compiled.render({0: b"AB", 1: b"CD"}), b"\x00\x00AB\x00\x00CD"
        )

    def test_compiles_to_pcic_and_loads_compiled_magic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "header.pci"
            output = Path(directory) / "header.pcic"
            source.write_bytes(make_pcpi())

            result = compile_pcpi_file(source, output)

            self.assertEqual(result, output)
            self.assertEqual(output.read_bytes()[0], 1)
            self.assertEqual(load_pcpi_file(output).image, b"\x00" * 6)

    def test_cli_compiles_to_derived_pcic_path(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "header.pci"
            source.write_bytes(make_pcpi())

            self.assertEqual(rif_main(["--comp-pcpi", str(source)]), 0)
            self.assertTrue(source.with_suffix(".pcic").is_file())

    def test_rejects_invalid_layout_and_pits(self) -> None:
        cases = (
            (make_pcpi(version=2), "Versión PCP-I"),
            (make_pcpi(pits=((5, 2),)), "termina fuera"),
            (make_pcpi(pits=((0, 3), (2, 2))), "solaparse"),
            (make_pcpi() + b"x", "tamaño"),
        )
        for data, message in cases:
            with self.subTest(message=message):
                with self.assertRaisesRegex(PCPIError, message):
                    compile_pcpi(data)

    def test_does_not_overwrite_input(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "header.pci"
            source.write_bytes(make_pcpi())

            with self.assertRaisesRegex(PCPIError, "sobrescribir"):
                compile_pcpi_file(source, source)


if __name__ == "__main__":
    unittest.main()
