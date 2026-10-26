"""Command-line entrypoint for RIF project tools."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from pack import create_pack


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="rif", description="Herramientas del compilador RIF")
    parser.add_argument(
        "--pack",
        metavar="MAIN.RIF",
        help="empaqueta todos los archivos .rif del proyecto",
    )
    parser.add_argument(
        "-o",
        "--output",
        metavar="ARCHIVO.PACK",
        help="ruta de salida del paquete; por defecto usa el nombre del entrypoint",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.pack:
        parser.error("debes indicar una operación, por ejemplo: rif --pack main.rif")

    try:
        output = create_pack(Path(args.pack), args.output)
    except (FileNotFoundError, OSError, ValueError) as exc:
        print(f"rif: error: {exc}", file=sys.stderr)
        return 1

    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
