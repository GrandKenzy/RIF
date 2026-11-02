from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from Frontend.globals import TableData, TargetContext
from MIR import compile_definition
from MIR.relocations import RelocationField, RelocationSpec
from MIR.relocations import relocation_specs


class RelocationRecipeTests(unittest.TestCase):
    def test_recipe_applies_bias_scale_and_signed_field(self) -> None:
        spec = RelocationSpec(
            "short_branch",
            16,
            "pc",
            pc_bias=2,
            scale=2,
            alignment=2,
            template=0xE000,
            fields=(RelocationField(0, 11, 0),),
        )

        self.assertEqual(spec.encode(8), 0xE003)
        self.assertEqual(spec.encode(-2), 0xE7FE)

    def test_recipe_can_split_one_value_into_multiple_output_fields(self) -> None:
        spec = RelocationSpec(
            "wide_call",
            32,
            "pc",
            signed=True,
            alignment=2,
            template=0xF8000000 | 0xF000,
            fields=(
                RelocationField(12, 11, 0),
                RelocationField(1, 11, 16),
            ),
        )

        self.assertEqual(spec.encode(4), 0xF802F000)
        self.assertEqual(spec.encode(-4), 0xFFFEF7FF)

    def test_recipe_rejects_alignment_and_range_errors(self) -> None:
        branch = RelocationSpec(
            "short_branch",
            16,
            "pc",
            pc_bias=2,
            scale=2,
            alignment=2,
            template=0xE000,
            fields=(RelocationField(0, 11, 0),),
        )
        call = RelocationSpec(
            "wide_call",
            32,
            "pc",
            signed=True,
            alignment=2,
            template=0xF8000000 | 0xF000,
            fields=(
                RelocationField(12, 11, 0),
                RelocationField(1, 11, 16),
            ),
        )

        with self.assertRaises(ValueError):
            branch.encode(3)
        with self.assertRaises(ValueError):
            branch.encode(2 + (1 << 11))
        with self.assertRaises(ValueError):
            call.encode(1)
        with self.assertRaises(ValueError):
            call.encode(1 << 22)

    def test_target_tables_materialize_generic_recipe_and_fields(self) -> None:
        context = TargetContext(
            tables={
                "relocations": TableData(
                    "relocations",
                    (
                        "name",
                        "width",
                        "mode",
                        "pc_bias",
                        "scale",
                        "alignment",
                        "signed",
                        "template",
                    ),
                    (("short_branch", 16, "pc", 2, 2, 2, True, 0xE000),),
                    {
                        "name": 0,
                        "width": 1,
                        "mode": 2,
                        "pc_bias": 3,
                        "scale": 4,
                        "alignment": 5,
                        "signed": 6,
                        "template": 7,
                    },
                ),
                "relocation_fields": TableData(
                    "relocation_fields",
                    ("relocation", "source_shift", "width", "target_shift"),
                    (("short_branch", 0, 11, 0),),
                    {"relocation": 0, "source_shift": 1, "width": 2, "target_shift": 3},
                ),
            }
        )

        specs = relocation_specs(context)
        self.assertEqual(specs["short_branch"].encode(8), 0xE003)

    def test_rif_tables_are_loaded_as_recipes(self) -> None:
        source = (
            "@table relocations\n"
            "| name | width | mode | pc_bias | scale | alignment | signed | template |\n"
            "__\n"
            "| short_branch | 16 | pc | 2 | 2 | 2 | true | 0xE000 |\n"
            "@end\n"
            "@table relocation_fields\n"
            "| relocation | source_shift | width | target_shift |\n"
            "__\n"
            "| short_branch | 0 | 11 | 0 |\n"
            "@end\n"
        )
        with TemporaryDirectory() as directory:
            target = Path(directory) / "main.rif"
            target.write_text(source, encoding="utf-8")
            program = compile_definition(target)

        self.assertEqual(
            relocation_specs(program.context)["short_branch"].encode(8),
            0xE003,
        )


if __name__ == "__main__":
    unittest.main()
