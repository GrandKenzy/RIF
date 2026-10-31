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
    load_pcpi_file,
    parse_pcpi,
)
from pcpi_compiler import compile_pcpi_source, compile_pcpi_source_file
from rif import main as rif_main


HEADER = struct.Struct("<BQIBBI")
PIT = struct.Struct("<HH")


SOURCE = '''\
@block config:
sectiondef ".section"
make section "text"
sectionend ":"
entrysection "text"
entrylabel "_start"
comment ";"
labelend ":"
datasection "text"
defaultsection "text"
wordsize 8
addresssize 64
endianness "little"
casesensitive true
symbolprefix "_"
localprefix "."
undefinedsymbols "error"
duplicatesymbols "error"
strict true
allowemptysections false
@end

@rule pcpi:
-> emitfr "01111111" "01000100"
-> emitfrend
-> reserve "entry" 16
'''


def make_binary_pcpi(
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
    def test_rif_source_emits_image_and_reservation_pit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "header.pci"
            source.write_text(SOURCE, encoding="utf-8")

            result = compile_pcpi_source(source)

            self.assertEqual(result.entry_rule, "pcpi")
            self.assertEqual(result.image.image, b"\x7fD\x00\x00")
            self.assertEqual(result.image.pits, (PCPIPit(2, 2, "entry"),))

    def test_cli_compiles_text_source_to_derived_pcic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "header.pci"
            source.write_text(SOURCE, encoding="utf-8")

            self.assertEqual(rif_main(["--comp-pcpi", str(source)]), 0)
            output = source.with_suffix(".pcic")
            self.assertTrue(output.is_file())
            self.assertEqual(load_pcpi_file(output).image, b"\x7fD\x00\x00")

    def test_source_compiler_accepts_explicit_entry_and_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "header.pci"
            output = Path(directory) / "build" / "header.pci"
            source.write_text(SOURCE, encoding="utf-8")

            result = compile_pcpi_source_file(source, output, entry_rule="pcpi")

            self.assertEqual(result, output.resolve())
            self.assertTrue(output.is_file())

    def test_binary_validator_remains_strict_backend(self) -> None:
        compiled = parse_pcpi(make_binary_pcpi())

        self.assertEqual(compiled.pits, (PCPIPit(0, 2), PCPIPit(4, 2)))
        self.assertEqual(compiled.fill(0, b"AB"), b"AB\x00\x00\x00\x00")
        with self.assertRaisesRegex(PCPIError, "solaparse"):
            parse_pcpi(make_binary_pcpi(pits=((0, 3), (2, 2))))

    def test_rejects_non_byte_aligned_pit(self) -> None:
        source = SOURCE.replace('reserve "entry" 16', 'reserve "entry" 12')
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.pci"
            path.write_text(source, encoding="utf-8")

            with self.assertRaisesRegex(PCPIError, "alineado"):
                compile_pcpi_source(path)


if __name__ == "__main__":
    unittest.main()
