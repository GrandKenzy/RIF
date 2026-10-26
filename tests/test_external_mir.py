from __future__ import annotations

import tempfile
import unittest
import zipfile
from pathlib import Path

from Frontend import globals as rif_globals
from MIR import (
    MIRInputError,
    RIFFunctionError,
    compile_definition,
    compile_mir_file,
    compile_mir_source,
    compile_mir_tokens,
    prepare_target,
    tokenize_mir,
)
from pack import PackReader, create_pack, read_pack
from rif import main as rif_main


TARGET = '''\
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

@linker:
.ext ".asm"
.name "main"
.searching ""
@linkerend

@rule mov:
-> IDENT
-> emmit 1
'''


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
    rif_globals.SOURCE_PROVIDER = None


class ExternalMIRTests(unittest.TestCase):
    def setUp(self) -> None:
        reset_globals()

    def tearDown(self) -> None:
        reset_globals()

    def test_direct_source_and_pre_tokenized_input_produce_same_binary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "main.rif"
            target.write_text(TARGET, encoding="utf-8")

            program = compile_definition(target)
            direct = compile_mir_source(program, "mov\nmov\n")
            tokens = tokenize_mir("mov\nmov\n", "direct.asm")
            token_direct = compile_mir_tokens(program, tokens)

            self.assertEqual(direct.binary, b"\x01\x01")
            self.assertEqual(token_direct.binary, direct.binary)
            self.assertEqual(len(direct.executions), 2)

    def test_file_entry_validates_linker_extension_and_writes_pure_binary(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "main.rif"
            source = root / "program.asm"
            output = root / "program.bin"
            target.write_text(TARGET, encoding="utf-8")
            source.write_text("mov\n", encoding="utf-8")

            result = compile_mir_file(target, source, output=output)

            self.assertEqual(result.binary, b"\x01")
            self.assertEqual(output.read_bytes(), b"\x01")

            wrong = root / "program.txt"
            wrong.write_text("mov\n", encoding="utf-8")
            with self.assertRaises(MIRInputError):
                compile_mir_file(target, wrong)

    def test_file_entry_accepts_a_precompiled_pack(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "main.rif"
            package = root / "target.pack"
            source = root / "program.asm"
            target.write_text(TARGET, encoding="utf-8")
            source.write_text("mov\n", encoding="utf-8")
            create_pack(target, package, precompile=True)

            result = compile_mir_file(package, source)

            self.assertEqual(result.binary, b"\x01")

    def test_precompiled_pack_resolves_insert_file_assets(self) -> None:
        target_source = TARGET.replace(
            '@rule mov:',
            '@insert:\n.file "payload.bin"\n@end\n\n@rule mov:',
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "main.rif"
            package = root / "target.pack"
            source = root / "program.asm"
            target.write_text(target_source, encoding="utf-8")
            (root / "payload.bin").write_bytes(b"\x10\x20")
            source.write_text("mov\n", encoding="utf-8")
            create_pack(target, package, precompile=True)

            with PackReader(package) as reader:
                self.assertEqual(reader.assets(), {"payload.bin": b"\x10\x20"})
            result = compile_mir_file(package, source)

            self.assertEqual(result.binary, b"\x10\x20\x01")

    def test_precompiled_pack_preserves_indexed_fits_and_virtual_space(self) -> None:
        target_source = TARGET.replace(
            '@rule mov:\n-> IDENT\n-> emmit 1\n',
            '@table registers\n'
            '| names | bits |\n'
            '_\n'
            '| rax | 16 |\n'
            '@end\n\n'
            '@rule mov:\n'
            '-> IDENT\n'
            '-> fits $registers.names[rax].bits\n'
            '-> vpadding 8\n',
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "main.rif"
            package = root / "target.pack"
            source = root / "program.asm"
            target.write_text(target_source, encoding="utf-8")
            source.write_text("mov 1282\n", encoding="utf-8")
            create_pack(target, package, precompile=True)

            result = compile_mir_file(package, source)

            self.assertEqual(result.binary, b"\x02\x05")
            self.assertEqual(result.context.virtual_position, 24)

    def test_datastack_capture_survives_mir_lines_and_precompiled_pack(self) -> None:
        target_source = TARGET.replace(
            '@rule mov:\n-> IDENT\n-> emmit 1\n',
            '@table registers\n'
            '| names | bits |\n'
            '_\n'
            '| rax | 8 |\n'
            '_\n'
            '| rbx | 8 |\n'
            '@end\n\n'
            '@rule capture:\n'
            '-> IDENT\n'
            '-> dload ::registers.names : bits\n'
            '@rule emit:\n'
            '-> IDENT\n'
            '-> fits dload\n',
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "main.rif"
            package = root / "target.pack"
            source = root / "program.asm"
            target.write_text(target_source, encoding="utf-8")
            source.write_text("capture rax\nemit 258\n", encoding="utf-8")

            direct = compile_mir_source(compile_definition(target), source.read_text(encoding="utf-8"))
            self.assertEqual(direct.binary, b"\x02")
            self.assertEqual(direct.context.datastack, [])
            self.assertEqual(direct.program.context.tables["registers"].indexes.keys(), {"names"})

            create_pack(target, package, precompile=True)
            packed = compile_mir_file(package, source)
            self.assertEqual(packed.binary, direct.binary)
            self.assertEqual(packed.context.datastack, [])

    def test_funcs_py_is_loaded_from_a_precompiled_pack(self) -> None:
        target_source = TARGET.replace(
            '@rule mov:\n-> IDENT\n-> emmit 1\n',
            '@rule mov:\n-> IDENT\n-> emmit #call[value]\n',
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "main.rif"
            package = root / "target.pack"
            source = root / "program.asm"
            target.write_text(target_source, encoding="utf-8")
            (root / "funcs.py").write_text(
                'def handler(name, context):\n'
                '    return "00000001"\n',
                encoding="utf-8",
            )
            source.write_text("mov\n", encoding="utf-8")
            create_pack(target, package, precompile=True)

            manifest = read_pack(package)
            self.assertIsNotNone(manifest.functions)
            with PackReader(package) as reader:
                self.assertEqual(reader.function_source(), (root / "funcs.py").read_bytes().decode("utf-8"))

            result = compile_mir_file(package, source)

            self.assertEqual(result.binary, b"\x01")

    def test_pack_rejects_tampered_funcs_py(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "main.rif"
            package = root / "target.pack"
            tampered = root / "tampered.pack"
            target.write_text(TARGET, encoding="utf-8")
            (root / "funcs.py").write_text(
                'def handler(name, context):\n'
                '    return "00000001"\n',
                encoding="utf-8",
            )
            create_pack(target, package, precompile=True)

            with zipfile.ZipFile(package, "r") as source_archive, zipfile.ZipFile(
                tampered, "w", compression=zipfile.ZIP_DEFLATED
            ) as target_archive:
                for info in source_archive.infolist():
                    data = source_archive.read(info.filename)
                    if info.filename == "funcs.py":
                        data += b"\n# tampered\n"
                    target_archive.writestr(info, data)

            with self.assertRaisesRegex(ValueError, "Hash inválido para funcs.py"):
                read_pack(tampered)

    def test_funcs_handler_receives_live_context_and_drives_calls(self) -> None:
        target_source = TARGET.replace(
            '@rule mov:\n-> IDENT\n-> emmit 1\n',
            '@rule mov:\n-> IDENT\n-> emmit #call[value]\n'
            '@rule callrule:\n-> IDENT\n-> CALL #call[emit]\n'
            '@rule branch:\n-> IDENT\n-> jmpif target, #call[condition]\n'
            '@rule target:\n-> emmit 1\n',
        )
        target_source = target_source.replace(
            '@rule mov:',
            '@table registers\n| name |\n_\n| "mov" |\n@end\n\n@rule mov:',
        )
        function_source = '''\
calls = []

def handler(name, context):
    calls.append((name, context))
    assert context.config.wordsize == 8
    assert context.coder is context.machine.emitter
    from Frontend import globals as rif_globals
    assert context.tables is not rif_globals.TABLES
    assert context.tables["registers"].matrix[0][0] == "mov"
    if name == "value":
        return "00000010"
    if name == "emit":
        context.coder.emmit("00000011")
        return "0"
    if name == "condition":
        return True
    raise RuntimeError(name)
'''
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "main.rif"
            target.write_text(target_source, encoding="utf-8")
            (root / "funcs.py").write_text(function_source, encoding="utf-8")

            prepared = prepare_target(target)
            result = compile_mir_source(prepared, "mov\ncallrule\nbranch\n")

            self.assertEqual(result.binary, b"\x02\x03\x01")
            calls = prepared.function_module.module.calls
            self.assertEqual([name for name, _context in calls], ["value", "emit", "condition"])
            self.assertIs(calls[0][1], result.context)

    def test_funcs_handler_rejects_invalid_return_and_numeric_conditions(self) -> None:
        target_source = TARGET.replace(
            '@rule mov:\n-> IDENT\n-> emmit 1\n',
            '@rule mov:\n-> IDENT\n-> emmit #call[invalid]\n'
            '@rule branch:\n-> IDENT\n-> jmpif target, #call[zero]\n'
            '@rule target:\n-> emmit 1\n',
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "main.rif"
            target.write_text(target_source, encoding="utf-8")
            (root / "funcs.py").write_text(
                'def handler(name, context):\n'
                '    return 1 if name == "invalid" else "000"\n',
                encoding="utf-8",
            )
            prepared = prepare_target(target)

            with self.assertRaisesRegex(RuntimeError, "solo se permiten"):
                compile_mir_source(prepared, "mov\n")
            with self.assertRaisesRegex(RuntimeError, "debe devolver True o False"):
                compile_mir_source(prepared, "branch\n")

    def test_funcs_module_requires_handler(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "main.rif"
            target.write_text(TARGET, encoding="utf-8")
            (root / "funcs.py").write_text("VALUE = True\n", encoding="utf-8")

            prepared = prepare_target(target)
            self.assertFalse(prepared.function_module.loaded)
            with self.assertRaises(RIFFunctionError):
                _ = prepared.function_module.handler

    def test_cli_uses_the_same_binary_entrypoint(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "main.rif"
            source = root / "program.asm"
            output = root / "program.bin"
            target.write_text(TARGET, encoding="utf-8")
            source.write_text("mov\nmov\n", encoding="utf-8")

            status = rif_main([str(target), str(source), "-o", str(output)])

            self.assertEqual(status, 0)
            self.assertEqual(output.read_bytes(), b"\x01\x01")


if __name__ == "__main__":
    unittest.main()
