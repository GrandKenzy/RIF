from __future__ import annotations

from typing import Any


# Se crea al procesar la primera declaración @stack.
STACK: dict[int, Any] | None = None
STACK_SIZE: int | None = None


__all__ = ["STACK", "STACK_SIZE"]
