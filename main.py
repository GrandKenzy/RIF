from __future__ import annotations

import sys
from pathlib import Path

from pack import create_pack


def main() -> int:
    arguments = sys.argv[1:]
    if arguments and arguments[0] == "--pack":
        if len(arguments) not in {2, 4}:
            print(
                f"Uso: {Path(sys.argv[0]).name} --pack <main.rif> [-o <archivo.pack>]",
                file=sys.stderr,
            )
            return 2
        output = None
        if len(arguments) == 4:
            if arguments[2] not in {"-o", "--output"}:
                print("Opción desconocida para --pack.", file=sys.stderr)
                return 2
            output = arguments[3]
        try:
            print(create_pack(arguments[1], output, precompile=True))
        except (FileNotFoundError, OSError, ValueError) as exc:
            print(f"Error al crear el paquete: {exc}", file=sys.stderr)
            return 1
        return 0

    if len(arguments) < 1:
        print(f"Uso: {Path(sys.argv[0]).name} <ruta> o --pack <main.rif>", file=sys.stderr)
        return 2

    source_path = Path(arguments[0])
    if not source_path.is_file():
        print(f"Archivo no encontrado: {source_path}", file=sys.stderr)
        return 2

    # El modo de empaquetado debe funcionar sin importar Gram ni el backend.
    # El compilador solo se carga para la ruta normal de análisis.
    from MIR import compile_source

    compile_source(source_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
