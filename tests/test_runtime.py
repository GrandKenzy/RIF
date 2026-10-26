from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from Frontend import RIF_LANG_SESSION
from Frontend import globals as rif_globals
from Frontend.processor import process
from MIR import BitEmitter, MIRSemanticError, RIFMachine, compile_rules


CONFIG_SOURCE = """\
@config:
.sectiondef ".section"
.make section "text"
.sectionend ":"
.entrysection "text"
.entrylabel "_start"
.comment ";"
.labelend ":"
.datasection "text"
.defaultsection "text"
.sectionalign "text" 8
.wordsize 8
.addresssize 8
.endianess "little"
.casesensitive true
.symbolprefix "_"
.localprefix "."
.undefinedsymbols "error"
.duplicateSymbols "error"
.strict true
.allowemptysections false
@configend
"""


def reset_globals() -> None:
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


class RuntimeTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_globals()

    def tearDown(self) -> None:
        reset_globals()

    def compile(self, source: str, path: Path):
        path.write_text(source, encoding="utf-8")
        RIF_LANG_SESSION.load()
        tokens = RIF_LANG_SESSION.tokenize(source, str(path))
        ast = RIF_LANG_SESSION.parse(tokens, str(path))
        process(ast, source_path=path)
        return compile_rules(resolve=True)

    def tokenize(self, source: str, name: str = "input.rif"):
        RIF_LANG_SESSION.load()
        return RIF_LANG_SESSION.tokenize(source, name)

    def test_consumer_table_matcher_and_put_use_the_bit_buffer(self) -> None:
        source = (
            "@table registers\n"
            "| name | bits |\n"
            "_\n"
            '| "mov" | "1010" |\n'
            "@end\n"
            "@rule sample:\n"
            "-> $registers.name, IDENT\n"
            "-> put $registers.bits 0000\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            program = self.compile(source, Path(directory) / "main.rif")
            machine = RIFMachine(program)
            result = machine.execute("sample", self.tokenize("mov"))

            self.assertEqual(result.position, 1)
            self.assertEqual(result.buffer, b"\xA0")
            self.assertEqual(machine.selected_rows["registers"], 0)

    def test_store_consumes_the_first_matching_token(self) -> None:
        source = "@rule sample:\n-> [NUMBER, STRING]\n"
        with tempfile.TemporaryDirectory() as directory:
            program = self.compile(source, Path(directory) / "main.rif")
            machine = RIFMachine(program)
            result = machine.execute("sample", self.tokenize('"hello"'))

            self.assertEqual(result.position, 1)
            self.assertIsNotNone(result.stored_token)
            self.assertEqual(result.stored_token.value, "hello")

    def test_emmit_uses_the_emitter_word_size(self) -> None:
        source = "@rule sample:\n-> emmit 4660\n"
        with tempfile.TemporaryDirectory() as directory:
            program = self.compile(source, Path(directory) / "main.rif")
            machine = RIFMachine(program, emitter=BitEmitter(wordsize=16))
            result = machine.execute("sample", ())

            self.assertEqual(result.buffer, b"4\x12")

    def test_dynamic_reservations_rewrite_copy_and_remove_names(self) -> None:
        source = (
            '@rule sample:\n'
            '-> reserve "slot" 8\n'
            '-> ldres "slot" "10101010"\n'
            '-> gtres "slot"\n'
            '-> dlres "slot"\n'
        )
        with tempfile.TemporaryDirectory() as directory:
            program = self.compile(source, Path(directory) / "main.rif")
            machine = RIFMachine(program)
            result = machine.execute("sample", ())

            self.assertEqual(result.buffer, b"\xAA\xAA")
            self.assertNotIn("slot", machine.emitter.buffer.regions)

    def test_emitfr_keeps_rows_and_jmpif_can_use_boolean(self) -> None:
        source = (
            "@rule target:\n"
            "-> emmit 1\n"
            "@rule sample:\n"
            "-> emitfr 0000 0\n"
            "00000000\n"
            "0000\n"
            "-> emitfrend\n"
            "-> jmpif target, true\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            program = self.compile(source, Path(directory) / "main.rif")
            machine = RIFMachine(program, emitter=BitEmitter(wordsize=8))
            result = machine.execute("sample", ())

            # The frame occupies 17 bits, so the following 8-bit word starts
            # unaligned and its final one-bit lands at the MSB of the last byte.
            self.assertEqual(result.buffer, b"\x00\x00\x00\x80")

    def test_padding_alignment_and_position_values_are_traced(self) -> None:
        source = CONFIG_SOURCE + (
            "@rule sample:\n"
            "-> emmit 00000000\n"
            "-> padding 3\n"
            "-> alignement 8\n"
            "-> emmit ::SIZE\n"
            "-> emmit ::VSIZE\n"
            "-> emmit ::ALIGNMENT\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            program = self.compile(source, Path(directory) / "positions.rif")
            machine = RIFMachine(program, emitter=BitEmitter(wordsize=8))
            result = machine.execute("sample", ())

            self.assertEqual(result.buffer, b"\x00\x00\x10\x18\x08")
            self.assertEqual(machine.last_rule_trace.start, 0)
            self.assertEqual(machine.last_rule_trace.bits, 40)
            self.assertEqual(machine.last_rule_trace.end, 40)
            self.assertEqual(machine.last_rule_trace.padding_bits, 8)

    def test_reservation_and_label_distances_are_values(self) -> None:
        source = (
            "@rule sample:\n"
            '-> reserve "slot" 8\n'
            "-> emmit 00000000\n"
            '-> emmit resdir "slot"\n'
            '-> emmit resdist "slot"\n'
            '-> emmit dist "sample"\n'
            '-> emmit vdist "sample"\n'
            '-> emmit resvdir "slot"\n'
        )
        with tempfile.TemporaryDirectory() as directory:
            program = self.compile(source, Path(directory) / "addresses.rif")
            machine = RIFMachine(program, emitter=BitEmitter(wordsize=8))
            result = machine.execute("sample", ())

            self.assertEqual(result.buffer, b"\x00\x00\x00\x18\x20\x28\x00")
            self.assertEqual(machine.emitter.buffer.regions["slot"].offset, 0)

    def test_nested_rule_traces_keep_child_and_parent_spans(self) -> None:
        source = (
            "@rule child:\n"
            "-> emmit 1\n"
            "-> padding 2\n"
            "@rule parent:\n"
            "-> emmit 2\n"
            "-> JMP child\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            program = self.compile(source, Path(directory) / "nested.rif")
            machine = RIFMachine(program, emitter=BitEmitter(wordsize=8))
            machine.execute("parent", ())

            self.assertEqual(
                [(trace.name, trace.start, trace.bits, trace.end, trace.padding_bits)
                 for trace in machine.rule_traces],
                [("child", 8, 10, 18, 2), ("parent", 0, 18, 18, 0)],
            )

    def test_padding_and_alignment_require_positive_sizes(self) -> None:
        for opcode in ("padding", "alignement"):
            source = f"@rule sample:\n-> {opcode} 0\n"
            with self.subTest(opcode=opcode), tempfile.TemporaryDirectory() as directory:
                with self.assertRaises(MIRSemanticError):
                    self.compile(source, Path(directory) / "invalid.rif")
            reset_globals()


if __name__ == "__main__":
    unittest.main()
