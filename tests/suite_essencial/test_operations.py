from __future__ import annotations

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

from MIR.operations import (
    execute_operation,
    operation_abi,
    operation_c_header,
    operation_c_source,
    operation_specs,
)


class RuleOperationTests(unittest.TestCase):
    def test_operation_abi_is_closed_and_c_compatible(self) -> None:
        names = [spec.name for spec in operation_specs()]
        self.assertEqual(names, sorted(names))
        self.assertEqual(operation_abi()["version"], "1.2")
        header = operation_c_header()
        self.assertIn("rif_op_fit_unsigned", header)
        self.assertIn("rif_op_fit_signed", header)
        self.assertIn("rif_op_encode_relocation", header)
        self.assertIn("rif_op_encode_relocation(uint64_t value", header)
        self.assertIn("rif_op_shift_left", header)
        self.assertIn("rif_op_shift_right", header)
        self.assertIn("rif_op_extract_bits", header)
        self.assertIn("rif_op_insert_bits", header)
        self.assertIn('#include "rif_rule_operation_abi.h"', operation_c_source())

    def test_rule_primitives_cover_unsigned_signed_and_relocation_ranges(self) -> None:
        self.assertEqual(execute_operation("fit_unsigned", 0x1FF, 8, True), 0xFF)
        self.assertEqual(execute_operation("fit_signed", -1, 8, False), 0xFF)
        self.assertEqual(execute_operation("encode_relocation", -2, 8, "pc"), 0xFE)
        self.assertEqual(
            execute_operation("encode_relocation", 0xFFFFFFFFFFFFFFFF, 64, "abs"),
            0xFFFFFFFFFFFFFFFF,
        )
        with self.assertRaises(ValueError):
            execute_operation("fit_signed", 128, 8, False)
        with self.assertRaises(ValueError):
            execute_operation("encode_relocation", 256, 8, "abs")

    def test_rule_primitives_manipulate_scalar_bit_fields(self) -> None:
        self.assertEqual(execute_operation("shift_left", 0x12, 4), 0x120)
        self.assertEqual(execute_operation("shift_right", 0x120, 4), 0x12)
        self.assertEqual(execute_operation("extract_bits", 0b11010100, 2, 4), 0b0101)
        self.assertEqual(
            execute_operation("insert_bits", 0xFFFF, 0b0010, 4, 4),
            0xFF2F,
        )
        with self.assertRaises(ValueError):
            execute_operation("shift_left", 1, 64)
        with self.assertRaises(ValueError):
            execute_operation("extract_bits", 0, 0, 0)
        with self.assertRaises(ValueError):
            execute_operation("insert_bits", 0, 0x10, 0, 4)

    def test_c_abi_preserves_absolute_u64_and_relative_twos_complement(self) -> None:
        compiler = shutil.which("clang") or shutil.which("gcc")
        if compiler is None:
            self.skipTest("clang/gcc no está disponible")
        with tempfile.TemporaryDirectory(prefix="rif-operation-abi-") as directory:
            root = Path(directory)
            (root / "rif_rule_operation_abi.h").write_text(
                operation_c_header(), encoding="utf-8"
            )
            (root / "operations.c").write_text(
                operation_c_source(), encoding="utf-8"
            )
            (root / "main.c").write_text(
                """
#include <stdint.h>
#include "rif_rule_operation_abi.h"

int main(void) {
    uint64_t out = 0;
    if (rif_op_shift_left(UINT64_C(0x12), 4, &out) != 0 || out != UINT64_C(0x120)) return 5;
    if (rif_op_shift_right(UINT64_C(0x120), 4, &out) != 0 || out != UINT64_C(0x12)) return 6;
    if (rif_op_extract_bits(UINT64_C(0xD4), 2, 4, &out) != 0 || out != UINT64_C(5)) return 7;
    if (rif_op_insert_bits(UINT64_C(0xFFFF), UINT64_C(2), 4, 4, &out) != 0 || out != UINT64_C(0xFF2F)) return 8;
    if (rif_op_encode_relocation(UINT64_MAX, 64, 0, &out) != 0) return 1;
    if (out != UINT64_MAX) return 2;
    if (rif_op_encode_relocation(UINT64_MAX, 8, 1, &out) != 0) return 3;
    if (out != UINT64_C(255)) return 4;
    return 0;
}
""",
                encoding="utf-8",
            )
            executable = root / ("operations.exe" if os.name == "nt" else "operations")
            built = subprocess.run(
                [compiler, str(root / "operations.c"), str(root / "main.c"), "-o", str(executable)],
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertEqual(built.returncode, 0, built.stderr)
            executed = subprocess.run([str(executable)], check=False)
            self.assertEqual(executed.returncode, 0)


if __name__ == "__main__":
    unittest.main()
