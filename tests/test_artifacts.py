from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

from Frontend import RIF_LANG_SESSION
from MIR import compile_mir_source


TARGET = '''\
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

@block linker:
ext ".asm"
name "main"
searching ""
@end

@insert:
.bytes "aa"
@end

@before:
.rplc 0, 1, 187
@end

@rule mov:
-> IDENT
'''


class ArtifactSyntaxTests(unittest.TestCase):
    def test_insert_and_before_blocks_are_captured(self) -> None:
        source = (
            "@insert:\n"
            '.section "text"\n'
            '.bytes "7f454c46"\n'
            '.binary "00000000"\n'
            '.file "payload.bin"\n'
            '.call #call[make_payload]\n'
            "@end\n"
            "@before:\n"
            ".rplc 24, 8, #:calc(4194304 + #:qlsize(0, \"_start\"))\n"
            ".rplc 96, #:qssize(0, \"text\")\n"
            "@end\n"
        )
        RIF_LANG_SESSION.load()
        tokens = RIF_LANG_SESSION.tokenize(source, "artifacts.rif")
        ast = RIF_LANG_SESSION.parse(tokens, "artifacts.rif")

        self.assertEqual([node.name for node in ast], ["INSERT", "BEFORE"])
        self.assertEqual(len(ast[0].lines), 5)
        self.assertEqual(len(ast[1].lines), 2)

    def test_insert_runs_before_mir_and_before_patches_final_image(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "main.rif"
            target.write_text(TARGET, encoding="utf-8")
            RIF_LANG_SESSION.load()
            parsed = RIF_LANG_SESSION.parse(
                RIF_LANG_SESSION.tokenize(TARGET, str(target)), str(target)
            )
            self.assertIn("INSERT", [node.name for node in parsed])
            result = compile_mir_source(target, "mov\n")
            self.assertEqual(len(result.program.inserts), 1)
            self.assertEqual(result.binary, b"\xbb")

    def test_native_queries_cover_physical_and_virtual_layout(self) -> None:
        source = (
            TARGET.replace('.bytes "aa"', '.bytes "aabbccdd"')
            .replace('endianness "little"', 'endianness "little"\nsectionvaddr "text" 4096')
            .replace(
                '@before:\n.rplc 0, 1, 187\n@end',
                '@before:\n'
                '.rplc 0, 1, #:qssize(0, "text")\n'
                '.rplc 1, 1, #:qlsize(0, "mov")\n'
                '.rplc 2, 2, #:qvsize(0, "mov")\n'
                '.rplc 4, 1, #:calc(#:qvssize(0, "text") - 4096)\n'
                '.rplc 0, 1, #:query(4, 1)\n'
                '@end',
            )
            .replace('-> IDENT\n', '-> IDENT\n-> emmit 5\n')
        )
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "main.rif"
            target.write_text(source, encoding="utf-8")

            result = compile_mir_source(target, "mov\n")

            self.assertEqual(result.binary, b"\x05\x04\x04\x10\x05")
            self.assertEqual(result.image.section_offset("text"), 0)
            self.assertEqual(result.image.section_virtual_base("text"), 4096)
            self.assertEqual(result.image.sections["text"].virtual_size, 5)
            self.assertEqual(result.image.file_bytes(), result.binary)
            self.assertEqual(result.section_binary, result.binary)

    def test_insert_call_can_return_a_binary_payload(self) -> None:
        source = TARGET.replace('.bytes "aa"', '.call #call[make_payload]').replace(
            '@before:\n.rplc 0, 1, 187\n@end\n\n', ''
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "main.rif"
            target.write_text(source, encoding="utf-8")
            (root / "funcs.py").write_text(
                'def handler(name, context):\n'
                '    assert name == "make_payload"\n'
                '    assert context.image is not None\n'
                '    return b"\\xde\\xad"\n',
                encoding="utf-8",
            )

            result = compile_mir_source(target, "")

            self.assertEqual(result.binary, b"\xde\xad")


if __name__ == "__main__":
    unittest.main()
