from __future__ import annotations

import unittest

from Frontend import RIF_LANG_SESSION
from Frontend import globals as rif_globals
from Frontend.processor import process
from Frontend.syntax.items.instructions import RawInstruction


class StackProcessorTests(unittest.TestCase):
    def setUp(self) -> None:
        rif_globals.STACK = None
        rif_globals.STACK_SIZE = None
        rif_globals.DEFINES.clear()
        rif_globals.TABLES.clear()
        rif_globals.RULES.clear()
        rif_globals.CONFIG = None
        rif_globals.LINKER = None
        rif_globals.SUPPORTS.clear()
        rif_globals.ASM_VARIANTS.clear()
        rif_globals.LOADED_SOURCES.clear()
        rif_globals.ACTIVE_SOURCES.clear()
        rif_globals.VARIANT_STACK.clear()

    def tearDown(self) -> None:
        rif_globals.STACK = None
        rif_globals.STACK_SIZE = None
        rif_globals.DEFINES.clear()
        rif_globals.TABLES.clear()
        rif_globals.RULES.clear()
        rif_globals.CONFIG = None
        rif_globals.LINKER = None
        rif_globals.SUPPORTS.clear()
        rif_globals.ASM_VARIANTS.clear()
        rif_globals.LOADED_SOURCES.clear()
        rif_globals.ACTIVE_SOURCES.clear()
        rif_globals.VARIANT_STACK.clear()

    def parse(self, source: str):
        RIF_LANG_SESSION.load()
        tokens = RIF_LANG_SESSION.tokenize(source, "processor.rif")
        return RIF_LANG_SESSION.parse(tokens, "processor.rif")

    def test_stack_creates_shared_empty_dictionary(self) -> None:
        process(self.parse("@stack 50\n"))

        self.assertEqual(rif_globals.STACK, {})
        self.assertEqual(rif_globals.STACK_SIZE, 50)

    def test_second_stack_is_fatal(self) -> None:
        ast = self.parse("@stack 4\n")
        process(ast)

        with self.assertRaises(RuntimeError):
            process(self.parse("@stack 8\n"))

    def test_stack_requires_positive_size(self) -> None:
        with self.assertRaises(RuntimeError):
            process(self.parse("@stack 0\n"))

        with self.assertRaises(RuntimeError):
            process(self.parse("@stack -1\n"))

    def test_define_is_registered_outside_stack(self) -> None:
        process(self.parse("@define mov\n"))

        self.assertEqual(rif_globals.DEFINES, {"mov"})
        self.assertIsNone(rif_globals.STACK)

    def test_defines_are_registered_before_other_nodes(self) -> None:
        process(self.parse("@stack 4\n@define mov\n"))

        self.assertEqual(rif_globals.DEFINES, {"mov"})

    def test_duplicate_define_is_fatal(self) -> None:
        with self.assertRaises(RuntimeError):
            process(self.parse("@define mov\n@define mov\n"))

    def test_table_is_stored_as_matrix_with_constant_column_index(self) -> None:
        process(
            self.parse(
                "@table registers\n"
                "| name | opcode | active |\n"
                "_\n"
                '| mov | 1 | true |\n'
                "_\n"
                '| add | 2 | false |\n'
                "@end\n"
            )
        )

        table = rif_globals.TABLES["registers"]
        self.assertEqual(table.headers, ("name", "opcode", "active"))
        self.assertEqual(table.columns, {"name": 0, "opcode": 1, "active": 2})
        self.assertEqual(table.matrix, [("mov", 1, True), ("add", 2, False)])

    def test_duplicate_table_is_fatal(self) -> None:
        ast = self.parse(
            "@table values\n"
            "| value |\n"
            "_\n"
            "| 1 |\n"
            "@end\n"
        )
        process(ast)

        with self.assertRaises(RuntimeError):
            process(ast)

    def test_rule_is_registered_with_its_instruction_ast(self) -> None:
        process(
            self.parse(
                "@rule mov:\n"
                "-> COMMA\n"
                "-> IDENT\n"
            )
        )

        rule = rif_globals.RULES["mov"]
        self.assertEqual(rule.name, "mov")
        self.assertEqual(len(rule.instructions), 2)
        self.assertIsInstance(rule.instructions[0], RawInstruction)
        self.assertEqual(rule.instructions[0].opcode, "consumer")

    def test_duplicate_rule_is_fatal(self) -> None:
        ast = self.parse("@rule mov:\n-> IDENT\n")
        process(ast)

        with self.assertRaises(RuntimeError):
            process(ast)

    def test_config_is_materialized_and_validated(self) -> None:
        process(
            self.parse(
                "@config:\n"
                '.sectiondef ".section"\n'
                '.make section "data"\n'
                '.make section "text"\n'
                '.make section "bss"\n'
                '.sectionend ":"\n'
                '.entrysection "text"\n'
                '.entrylabel "_start"\n'
                '.comment ";"\n'
                '.labelend ":"\n'
                '.datasection "data"\n'
                '.defaultsection "text"\n'
                '.sectionflags "text" "rx"\n'
                '.sectionflags "data" "rw"\n'
                '.sectionflags "bss" "rw"\n'
                '.sectionalign "text" 4\n'
                '.sectionalign "data" 4\n'
                '.sectionalign "bss" 4\n'
                '.wordsize 32\n'
                '.addresssize 32\n'
                '.endianess "little"\n'
                '.bitorder "lsb"\n'
                '.casesensitive true\n'
                '.symbolprefix "_"\n'
                '.localprefix "."\n'
                '.undefinedsymbols "error"\n'
                '.duplicateSymbols "error"\n'
                '.strict true\n'
                '.allowemptysections false\n'
                "@configend\n"
            )
        )

        self.assertEqual(rif_globals.CONFIG.sectiondef, ".section")
        self.assertEqual(rif_globals.CONFIG.sections, ("data", "text", "bss"))
        self.assertEqual(rif_globals.CONFIG.entrysection, "text")
        self.assertEqual(rif_globals.CONFIG.entrylabel, "_start")
        self.assertEqual(rif_globals.CONFIG.comment, ";")
        self.assertEqual(rif_globals.CONFIG.labelend, ":")
        self.assertEqual(rif_globals.CONFIG.datasection, "data")
        self.assertEqual(rif_globals.CONFIG.bitorder, "lsb")

    def test_config_requires_declared_entry_and_data_sections(self) -> None:
        source = (
            "@config:\n"
            '.sectiondef ".section"\n'
            '.make section "text"\n'
            '.sectionend ":"\n'
            '.entrysection "missing"\n'
            '.entrylabel "_start"\n'
            '.comment ";"\n'
            '.labelend ":"\n'
            '.datasection "text"\n'
            '.defaultsection "text"\n'
            '.wordsize 32\n'
            '.addresssize 32\n'
            '.endianess "little"\n'
            '.casesensitive true\n'
            '.symbolprefix "_"\n'
            '.localprefix "."\n'
            '.undefinedsymbols "error"\n'
            '.duplicateSymbols "error"\n'
            '.strict true\n'
            '.allowemptysections false\n'
            "@configend\n"
        )

        with self.assertRaises(RuntimeError):
            process(self.parse(source))

    def test_config_rejects_duplicate_directives_and_sections(self) -> None:
        source = (
            "@config:\n"
            '.sectiondef ".section"\n'
            '.sectiondef ".segment"\n'
            '.make section "text"\n'
            '.make section "text"\n'
            '.sectionend ":"\n'
            '.entrysection "text"\n'
            '.entrylabel "_start"\n'
            '.comment ";"\n'
            '.labelend ":"\n'
            '.datasection "text"\n'
            '.defaultsection "text"\n'
            '.wordsize 32\n'
            '.addresssize 32\n'
            '.endianess "little"\n'
            '.casesensitive true\n'
            '.symbolprefix "_"\n'
            '.localprefix "."\n'
            '.undefinedsymbols "error"\n'
            '.duplicateSymbols "error"\n'
            '.strict true\n'
            '.allowemptysections false\n'
            "@configend\n"
        )

        with self.assertRaises(RuntimeError):
            process(self.parse(source))

    def test_linker_is_materialized_without_dag(self) -> None:
        process(
            self.parse(
                "@linker:\n"
                '.ext ".asm"\n'
                '.name "main"\n'
                '.searching ""\n'
                "@linkerend\n"
            )
        )

        self.assertEqual(rif_globals.LINKER.ext, ".asm")
        self.assertEqual(rif_globals.LINKER.name, "main")
        self.assertEqual(rif_globals.LINKER.searching, "")

    def test_linker_false_disables_searching(self) -> None:
        process(
            self.parse(
                "@linker:\n"
                '.ext ".asm"\n'
                '.name "main"\n'
                ".searching false\n"
                "@linkerend\n"
            )
        )

        self.assertIs(rif_globals.LINKER.searching, False)


if __name__ == "__main__":
    unittest.main()
