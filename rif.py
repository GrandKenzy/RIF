"""Command-line entrypoint for RIF project tools."""

from __future__ import annotations

import vendor.__bootstrap__  # From VNMA.

import argparse
import os
import sys
from pathlib import Path

from pack import create_pack
from rif_limits import ENV_KEY, parse_mib, write_mib


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rif", description="Herramientas del compilador RIF")
    parser.add_argument(
        "--pack",
        metavar="MAIN.RIF",
        help="empaqueta todos los archivos .rif del proyecto",
    )
    parser.add_argument(
        "--plimit",
        metavar="MiB",
        type=parse_mib,
        help="límite de recursos por operación en MiB; también se guarda en .env",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="ARCHIVO.PACK",
        help="ruta de salida del paquete o binario; por defecto se deriva del input",
    )
    parser.add_argument(
        "definition",
        nargs="?",
        help="definición objetivo .rif o .pack",
    )
    parser.add_argument(
        "mir",
        nargs="?",
        help="archivo MIR con la extensión declarada por .ext",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.plimit is not None:
        try:
            write_mib(args.plimit)
            os.environ[ENV_KEY] = str(args.plimit)
        except (OSError, ValueError) as exc:
            print(f"rif: error: {exc}", file=sys.stderr)
            return 1
    if not args.pack:
        if not args.definition or not args.mir:
            parser.error(
                "debes indicar una definición y un MIR, por ejemplo: rif main.rif main.asm"
            )
        output = args.output
        if output is None:
            output = str(Path(args.mir).with_suffix(".bin"))
        try:
            from MIR import compile_mir_file

            compile_mir_file(args.definition, args.mir, output=output)
        except (FileNotFoundError, OSError, ValueError, RuntimeError) as exc:
            print(f"rif: error: {exc}", file=sys.stderr)
            return 1
        print(output)
        return 0

    if args.definition or args.mir:
        parser.error("--pack no puede combinarse con una definición MIR")

    try:
        output = create_pack(Path(args.pack), args.output, precompile=True)
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"rif: error: {exc}", file=sys.stderr)
        return 1

    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
