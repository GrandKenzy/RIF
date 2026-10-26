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
        return self.program.context.config

    @property
    def linker(self) -> globals.LinkerData | None:
        return self.program.context.linker

    @property
    def defines(self) -> frozenset[str]:
        return self.program.context.defines

    @property
    def tables(self) -> dict[str, globals.TableData]:
        return self.program.context.tables

    @property
    def rules(self) -> dict[str, Any]:
        return self.program.rules

    @property
    def stack(self) -> dict[int, Any] | None:
        return self.machine.stack

    @property
    def stack_size(self) -> int | None:
        return self.program.context.stack_size

    @property
    def supports(self) -> dict[str, globals.SupportData]:
        return self.program.context.supports

    @property
    def asm_variants(self) -> dict[str, globals.AsmVariantData]:
        return self.program.context.asm_variants

    @property
    def loaded_sources(self) -> dict[str, str]:
        return self.program.context.loaded_sources

    @property
    def variant_stack(self) -> list[globals.VariantFrame]:
        return list(getattr(self.machine, "variant_stack", ()))

    @property
    def source_provider(self) -> Any | None:
        return None

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
    def image_binary(self) -> bytes:
        """Return the current complete file image across all sections."""

        if self.image is None:
            return b""
        return self.image.file_bytes()

    @property
    def final_binary(self) -> bytes:
        """Alias for the complete image visible to finalization functions."""

        return self.image_binary

    @property
    def file_offset(self) -> int:
        """Physical file offset of the active section after layout."""

        if self.image is None or self.section is None:
            return 0
        return self.image.section_offset(self.section.name)

    @property
    def virtual_base(self) -> int:
        """Virtual base of the active section after layout."""

        if self.image is None or self.section is None:
            return 0
        return self.image.section_virtual_base(self.section.name)

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
        return self.machine.emitter.virtual_position

    @property
    def virtual_regions(self) -> dict[str, Any]:
        return self.machine.emitter.virtual_regions

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
    def datastack(self) -> list[Any]:
        return self.machine.datastack

    @property
    def selected_rows(self) -> dict[str, int]:
        return self.machine.selected_rows


__all__ = ["RIFFunctionContext"]
