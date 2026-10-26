from __future__ import annotations

import sys
from pathlib import Path

from Frontend import RIF_LANG_SESSION
from Frontend.processor import process


def main() -> int:
    if len(sys.argv) < 2:
        print(f"Uso: {Path(sys.argv[0]).name} <ruta>", file=sys.stderr)
        return 2

    source_path = Path(sys.argv[1])
    if not source_path.is_file():
        print(f"Archivo no encontrado: {source_path}", file=sys.stderr)
        return 2

    source = source_path.read_text(encoding="utf-8")
    RIF_LANG_SESSION.load()
    tokens = RIF_LANG_SESSION.tokenize(source, str(source_path))
    ast = RIF_LANG_SESSION.parse(tokens, str(source_path))
    process(ast)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
