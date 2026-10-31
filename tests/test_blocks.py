from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from MIR import compile_source
from pack import create_pack


CONFIG_BLOCK = '''\
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
endianess "little"
casesensitive true
symbolprefix "_"
localprefix "."
undefinedsymbols "error"
duplicateSymbols "error"
strict true
allowemptysections false
bitorder "msb"
@end

@block metadata:
kind "pcpi" "source"
version 1
@end

@rule sample:
-> emmit 1
'''


class GenericBlockTests(unittest.TestCase):
    def test_generic_config_and_unknown_blocks_are_materialized(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "generic.rif"
            source.write_text(CONFIG_BLOCK, encoding="utf-8")

            program = compile_source(source)

            self.assertIsNotNone(program.context.config)
            self.assertEqual(program.context.config.wordsize, 8)
            self.assertEqual(
                program.context.blocks["metadata"][0].entries[0].name,
                "kind",
            )
            self.assertEqual(
                [value.value for value in program.context.blocks["metadata"][0].entries[0].values],
                ["pcpi", "source"],
            )

    def test_generic_block_rejects_more_than_two_values(self) -> None:
        source = CONFIG_BLOCK.replace(
            'kind "pcpi" "source"',
            'kind "pcpi" "source" "extra"',
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.rif"
            path.write_text(source, encoding="utf-8")

            with self.assertRaisesRegex(RuntimeError, "como máximo dos valores"):
                compile_source(path)

    def test_generic_blocks_survive_precompiled_pack_loading(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "generic.rif"
            package = Path(directory) / "generic.pack"
            source.write_text(CONFIG_BLOCK, encoding="utf-8")

            create_pack(source, package, precompile=True)
            loaded = compile_source(package)

            self.assertEqual(
                loaded.context.blocks["metadata"][0].entries[1].values[0].value,
                1,
            )


if __name__ == "__main__":
    unittest.main()
