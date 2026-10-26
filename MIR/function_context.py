"""Live context exposed to RIF Python functions."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from Frontend import globals

from .bitbuffer import BitBuffer
from .emitter import BitEmitter
from .instructions import CompiledRuleSet
from .output import AssemblyImage, AssemblySection

if TYPE_CHECKING:
    from .runtime import RIFMachine


class RIFFunctionContext:
    """Live view of the current target, machine, and output state.

    Collections are deliberately returned by reference. The ``coder`` and
    ``image`` objects are the active runtime objects, while ``binary`` is a
    fresh memoryview over the same backing byte storage on each access.
    """

    def __init__(
        self,
        *,
        program: CompiledRuleSet,
        machine: "RIFMachine",
        image: AssemblyImage | None,
        section: AssemblySection | None,
        target_path: Path | None = None,
        mir_path: Path | None = None,
    ) -> None:
        self.program = program
        self.machine = machine
        self.image = image
        self.section = section
        self.target_path = target_path
        self.mir_path = mir_path

    @property
    def config(self) -> globals.ConfigData | None:
        return globals.CONFIG

    @property
    def linker(self) -> globals.LinkerData | None:
        return globals.LINKER

    @property
    def defines(self) -> set[str]:
        return globals.DEFINES

    @property
    def tables(self) -> dict[str, globals.TableData]:
        return globals.TABLES

    @property
    def rules(self) -> dict[str, Any]:
        return self.program.rules

    @property
    def stack(self) -> dict[int, Any] | None:
        return globals.STACK

    @property
    def stack_size(self) -> int | None:
        return globals.STACK_SIZE

    @property
    def supports(self) -> dict[str, globals.SupportData]:
        return globals.SUPPORTS

    @property
    def asm_variants(self) -> dict[str, globals.AsmVariantData]:
        return globals.ASM_VARIANTS

    @property
    def loaded_sources(self) -> dict[str, str]:
        return globals.LOADED_SOURCES

    @property
    def variant_stack(self) -> list[globals.VariantFrame]:
        return globals.VARIANT_STACK

    @property
    def source_provider(self) -> Any | None:
        return globals.SOURCE_PROVIDER

    @property
    def coder(self) -> BitEmitter:
        return self.machine.emitter

    @property
    def buffer(self) -> BitBuffer:
        return self.machine.emitter.buffer

    @property
    def binary(self) -> memoryview:
        return self.buffer.view()

    @property
    def tokens(self) -> tuple[Any, ...]:
        return self.machine.tokens

    @property
    def position(self) -> int:
        return self.machine.position

    @property
    def rule_traces(self) -> list[Any]:
        return self.machine.rule_traces

    @property
    def last_rule_trace(self) -> Any | None:
        return self.machine.last_rule_trace

    @property
    def virtual_position(self) -> int:
        return self.machine.emitter.buffer.bit_length

    @property
    def current_token(self) -> Any | None:
        if self.position >= len(self.tokens):
            return None
        return self.tokens[self.position]

    @property
    def last_token(self) -> Any | None:
        return self.machine.last_token

    @property
    def stored_token(self) -> Any | None:
        return self.machine.stored_token

    @property
    def storage(self) -> dict[str, Any]:
        return self.machine.storage

    @property
    def selected_rows(self) -> dict[str, int]:
        return self.machine.selected_rows


__all__ = ["RIFFunctionContext"]
