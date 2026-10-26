from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field, replace
from typing import Any


@dataclass
class TableData:
    """Matriz con índices de columna y claves construidos solo al consultarse."""

    name: str
    headers: tuple[str, ...]
    matrix: list[tuple[Any, ...]]
    columns: dict[str, int]
    indexes: dict[str, dict[Any, int]] = field(default_factory=dict)

    def index_for(self, column: str) -> dict[Any, int]:
        """Return a unique-key index for one selected column."""
        if column not in self.columns:
            raise KeyError(f"La columna '{column}' no existe en la tabla '{self.name}'.")
        if column not in self.indexes:
            index: dict[Any, int] = {}
            for row_number, row in enumerate(self.matrix):
                value = row[self.columns[column]]
                try:
                    duplicate = value in index
                except TypeError as exc:
                    raise ValueError(f"El valor de '{self.name}.{column}' no es indexable.") from exc
                if duplicate:
                    raise ValueError(
                        f"La columna '{column}' de la tabla '{self.name}' contiene "
                        f"la clave duplicada {value!r}."
                    )
                index[value] = row_number
            self.indexes[column] = index
        return self.indexes[column]


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
    sectionvaddr: dict[str, int] = field(default_factory=dict)


@dataclass(frozen=True)
class InsertData:
    """Declarative binary prelude to apply to one output section."""

    section: str
    kind: str
    value: Any
    source_path: str | None = None


@dataclass(frozen=True)
class BeforePatchData:
    """Declarative final patch evaluated after all MIR lines finish."""

    offset: int
    width: int | None
    expression: Any
    source_path: str | None = None


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


@dataclass(frozen=True)
class TargetContext:
    """Self-contained target state captured after processing a RIF project.

    The frontend still uses module globals while it visits a source tree, but
    compiled programs must never consult those mutable globals.  Keeping the
    snapshot on the compiled Rule set makes prepared targets independent and
    safe to reuse in the same Python process.
    """

    config: ConfigData | None = None
    linker: LinkerData | None = None
    defines: frozenset[str] = frozenset()
    stack_size: int | None = None
    tables: dict[str, TableData] = field(default_factory=dict)
    supports: dict[str, SupportData] = field(default_factory=dict)
    asm_variants: dict[str, AsmVariantData] = field(default_factory=dict)
    loaded_sources: dict[str, str] = field(default_factory=dict)


def snapshot_target_context() -> TargetContext:
    """Return a detached copy of the target currently built by visitors."""

    config = CONFIG
    if config is not None:
        config = replace(
            config,
            sectionflags=dict(config.sectionflags),
            sectionalign=dict(config.sectionalign),
            sectionvaddr=dict(config.sectionvaddr),
        )
    tables = {
        name: TableData(
            name=table.name,
            headers=tuple(table.headers),
            matrix=deepcopy(table.matrix),
            columns=dict(table.columns),
            indexes=deepcopy(table.indexes),
        )
        for name, table in TABLES.items()
    }
    return TargetContext(
        config=config,
        linker=LINKER,
        defines=frozenset(DEFINES),
        stack_size=STACK_SIZE,
        tables=tables,
        supports=dict(SUPPORTS),
        asm_variants=dict(ASM_VARIANTS),
        loaded_sources=dict(LOADED_SOURCES),
    )


def activate_target_context(context: TargetContext) -> None:
    """Expose a snapshot through legacy frontend globals.

    This is kept only for processor/introspection compatibility. Runtime code
    reads ``CompiledRuleSet.context`` directly and is therefore unaffected by
    later calls to this helper.
    """

    global STACK, STACK_SIZE, CONFIG, LINKER
    STACK_SIZE = context.stack_size
    STACK = {} if STACK_SIZE is not None else None
    CONFIG = context.config
    LINKER = context.linker
    DEFINES.clear()
    DEFINES.update(context.defines)
    TABLES.clear()
    TABLES.update(deepcopy(context.tables))
    SUPPORTS.clear()
    SUPPORTS.update(context.supports)
    ASM_VARIANTS.clear()
    ASM_VARIANTS.update(context.asm_variants)
    LOADED_SOURCES.clear()
    LOADED_SOURCES.update(context.loaded_sources)
    VARIANT_STACK.clear()


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

# Proveedor opcional de fuentes empaquetadas. Permite que @LOAD y las
# variantes lean desde un .pack sin volver al filesystem.
SOURCE_PROVIDER: Any | None = None

# Binary preludes and final patches are deliberately kept separate from Rules.
# They are compiled into the target plan but are not executed while a .pack is
# being created.
INSERTS: list[InsertData] = []
BEFORE: list[BeforePatchData] = []

__all__ = [
    "STACK",
    "STACK_SIZE",
    "DEFINES",
    "TableData",
    "TABLES",
    "RuleData",
    "RULES",
    "ConfigData",
    "InsertData",
    "BeforePatchData",
    "CONFIG",
    "LinkerData",
    "LINKER",
    "SupportData",
    "SUPPORTS",
    "AsmVariantData",
    "ASM_VARIANTS",
    "VariantFrame",
    "TargetContext",
    "snapshot_target_context",
    "activate_target_context",
    "LOADED_SOURCES",
    "ACTIVE_SOURCES",
    "VARIANT_STACK",
    "SOURCE_PROVIDER",
    "INSERTS",
    "BEFORE",
]
