from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class TableData:
    """Tabla materializada como matriz con índice constante de columnas."""

    name: str
    headers: tuple[str, ...]
    matrix: list[tuple[Any, ...]]
    columns: dict[str, int]


@dataclass
class RuleData:
    """Regla registrada, conservando sus instrucciones sin ejecutarlas."""

    name: str
    node: Any
    instructions: tuple[Any, ...]
    source_path: str | None = None


@dataclass(frozen=True)
class ConfigData:
    """Configuración del formato ensamblador objetivo."""

    sectiondef: str
    sections: tuple[str, ...]
    sectionend: str
    entrysection: str
    entrylabel: str
    comment: str
    labelend: str
    datasection: str
    defaultsection: str
    sectionflags: dict[str, str]
    sectionalign: dict[str, int]
    wordsize: int
    addresssize: int
    endianness: str
    casesensitive: bool
    symbolprefix: str
    localprefix: str
    undefinedsymbols: str
    duplicatesymbols: str
    strict: bool
    allowemptysections: bool
    bitorder: str = "msb"


@dataclass(frozen=True)
class LinkerData:
    """Configuración de descubrimiento de archivos del linker."""

    ext: str
    name: str
    searching: str | bool


@dataclass(frozen=True)
class SupportData:
    """Variante declarada y su archivo RIF esperado."""

    name: str
    path: str


@dataclass(frozen=True)
class AsmVariantData:
    """Reglas de entrada/salida y modo de delegación de una variante."""

    name: str
    mode: str
    enter_rule: str
    exit_rule: str
    path: str


@dataclass(frozen=True)
class VariantFrame:
    """Contexto sintáctico activo; el estado semántico permanece global."""

    variant: AsmVariantData
    source_path: str
    return_rule: str | None
    token_position: int


# Se crea al procesar la primera declaración @stack.
STACK: dict[int, Any] | None = None
STACK_SIZE: int | None = None

# Nombres declarados con @define. Son etiquetas del lenguaje, no slots del
# stack ni valores runtime.
DEFINES: set[str] = set()

# Las tablas se localizan por nombre en O(1). Cada TableData conserva la
# matriz original y un índice de columnas para resolver accesos sin recorrer
# los encabezados.
TABLES: dict[str, TableData] = {}

# Reglas localizadas por nombre. Su AST se conserva para la fase de ejecución.
RULES: dict[str, RuleData] = {}

# Configuración única del ensamblador objetivo.
CONFIG: ConfigData | None = None

# Configuración única del linker.
LINKER: LinkerData | None = None

# Variantes y archivos cargados comparten el mismo contexto semántico.
SUPPORTS: dict[str, SupportData] = {}
ASM_VARIANTS: dict[str, AsmVariantData] = {}
LOADED_SOURCES: dict[str, str] = {}
ACTIVE_SOURCES: list[str] = []
VARIANT_STACK: list[VariantFrame] = []

__all__ = [
    "STACK",
    "STACK_SIZE",
    "DEFINES",
    "TableData",
    "TABLES",
    "RuleData",
    "RULES",
    "ConfigData",
    "CONFIG",
    "LinkerData",
    "LINKER",
    "SupportData",
    "SUPPORTS",
    "AsmVariantData",
    "ASM_VARIANTS",
    "VariantFrame",
    "LOADED_SOURCES",
    "ACTIVE_SOURCES",
    "VARIANT_STACK",
]
