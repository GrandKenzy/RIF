from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .visitors.stack import visit as visit_stack


def process(result: Iterable[Any] | None) -> None:
    """Recorre y despacha cada nodo producido por el parser."""
    if result is None:
        return

    for node in result:
        name = getattr(node, "name", type(node).__name__)
        if name == "STACK":
            visit_stack(node)
        else:
            print("falta por procesar", name)


__all__ = ["process"]
