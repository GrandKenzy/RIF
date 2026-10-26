from __future__ import annotations

import unittest

from Frontend import RIF_LANG_SESSION
from Frontend import globals as rif_globals
from Frontend.processor import process


class StackProcessorTests(unittest.TestCase):
    def setUp(self) -> None:
        rif_globals.STACK = None
        rif_globals.STACK_SIZE = None

    def tearDown(self) -> None:
        rif_globals.STACK = None
        rif_globals.STACK_SIZE = None

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


if __name__ == "__main__":
    unittest.main()
