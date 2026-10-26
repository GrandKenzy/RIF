"""Sectioned output backend for the RIF bit buffers."""

from __future__ import annotations

from dataclasses import dataclass

from Frontend import globals

from .bitbuffer import BitBuffer, BitLayout
from .emitter import BitEmitter


@dataclass
class AssemblySection:
    name: str
    buffer: BitBuffer
    flags: str = ""
    alignment: int | None = None


class AssemblyImage:
    """Own one bit buffer per configured assembler section."""

    def __init__(self, config: globals.ConfigData) -> None:
        self.config = config
        layout = BitLayout(
            bit_order=config.bitorder,
            byte_order=config.endianness,
        )
        self.sections: dict[str, AssemblySection] = {
            name: AssemblySection(
                name=name,
                buffer=BitBuffer(layout),
                flags=config.sectionflags.get(name, ""),
                alignment=config.sectionalign.get(name),
            )
            for name in config.sections
        }
        self.current = config.defaultsection

    def select(self, name: str) -> AssemblySection:
        try:
            section = self.sections[name]
        except KeyError as exc:
            raise KeyError(f"La sección '{name}' no existe en CONFIG.") from exc
        self.current = name
        return section

    def section(self, name: str | None = None) -> AssemblySection:
        return self.select(name or self.current)

    def emitter(self, name: str | None = None) -> BitEmitter:
        section = self.section(name)
        return BitEmitter(
            buffer=section.buffer,
            wordsize=self.config.wordsize,
        )

    def binary(self, name: str | None = None) -> bytes:
        return self.section(name).buffer.to_bytes()

    def render(self) -> str:
        """Render a conservative, target-neutral assembly representation."""

        lines: list[str] = []
        for name in self.config.sections:
            section = self.sections[name]
            if not section.buffer.bit_length and not self.config.allowemptysections:
                continue

            lines.append(f"{self.config.sectiondef} {name}{self.config.sectionend}")
            if section.alignment is not None:
                lines.append(f".align {section.alignment}")
            if name == self.config.entrysection:
                lines.append(f"{self.config.entrylabel}{self.config.labelend}")

            data = section.buffer.to_bytes()
            if section.buffer.bit_length % 8:
                lines.append(
                    f"{self.config.comment} RIF bits={section.buffer.bit_length}"
                )
            for start in range(0, len(data), 16):
                chunk = data[start : start + 16]
                lines.append(".byte " + ", ".join(f"0x{value:02x}" for value in chunk))

        return "\n".join(lines) + ("\n" if lines else "")


__all__ = ["AssemblySection", "AssemblyImage"]
