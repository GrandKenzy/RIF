from __future__ import annotations

import unittest

from Frontend import RIF_LANG_SESSION


class DeclarationTests(unittest.TestCase):
    def parse(self, source: str):
        RIF_LANG_SESSION.load()
        tokens = RIF_LANG_SESSION.tokenize(source, "declarations.rif")
        return RIF_LANG_SESSION.parse(tokens, "declarations.rif")

    def test_define_and_rule_declarations(self) -> None:
        ast = self.parse(
            "@define mov\n"
            "@define add\n"
            "@rule mov:\n"
            "      -> $registros.name, DOT\n"
            "-> COMMA\n"
            "-> AT\n"
            "-> IDENT\n"
            "-> [NUMBER, STRING]\n"
            "@rule add:\n"
            "-> $registros.name, AT\n"
            "-> $registros.name, 7\n"
            "-> put 0000 0000\n"
            "-> put $register.opcode 0000\n"
            "-> ebit 0 0 0 0 0 0 0 0\n"
            "-> ebit $register.bits 0 0 0 0 0 0 0\n"
            "-> emmit 83847483\n"
            "-> emmit $register.value\n"
            '-> KW "ret"\n'
            "-> jmpif add, true\n"
            "-> jmpif add, True\n"
            "-> jmpif add, #call[mifuncion]\n"
            "-> emmit #call[mifuncion]\n"
            "-> CALL #call[mifuncion]\n"
            "-> break\n"
            '-> error, "cualquier cosa"\n'
            "-> JMP add\n"
            '-> save "name"\n'
            '-> load "name"\n'
            '-> reserve "buffer" 16\n'
            '-> ldres "buffer" 0028383\n'
            '-> ldres "buffer" $register.value\n'
            '-> ldres "buffer" &buffer\n'
            "-> put &buffer 0000\n"
            "-> emmit &buffer\n"
            '-> dlres "buffer"\n'
            '-> gtres "buffer"\n'
            "-> emitfr 0000 $register.word #call[mifuncion]\n"
            "0\n"
            "&buffer\n"
            "\n"
            "0000\n"
            "0\n"
            "0000\n"
            "0000000\n"
            "0000\n"
            "-> emitfrend\n"
            "@stack 50\n"
        )

        self.assertIsNotNone(ast)
        self.assertEqual(len(ast), 5)

    def test_declarations_and_table_can_share_entrypoint(self) -> None:
        ast = self.parse(
            "@define mov\n"
            "@rule mov:\n"
            "@table example\n"
            "| name | age |\n"
            "_\n"
            '| "Ken" | 23 |\n'
            "@end\n"
        )

        self.assertIsNotNone(ast)
        self.assertEqual(len(ast), 3)


if __name__ == "__main__":
    unittest.main()
