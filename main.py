from __future__ import annotations

import sys

def main() -> int:
    from rif import main as rif_main

    return rif_main(sys.argv[1:])


if __name__ == "__main__":
    raise SystemExit(main())
