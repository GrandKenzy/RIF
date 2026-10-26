"""Sectioned output backend for the RIF bit buffers."""

from __future__ import annotations

from dataclasses import dataclass

from Frontend import globals

from .bitbuffer import BitBuffer, BitLayout
from .emitter import BitEmitter


MAX_IMAGE_BYTES = 512 << 20


@dataclass
class AssemblySection:
    name: str
    buffer: BitBuffer
    flags: str = ""
    alignment: int | None = None
    virtual_base: int = 0
    file_offset: int = 0
    virtual_size: int = 0

    @property
    def file_size(self) -> int:
        return self.buffer.byte_length


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
                virtual_base=config.sectionvaddr.get(name, 0),
            )
            for name in config.sections
        }
        self.current = config.defaultsection
        self._emitters: dict[str, BitEmitter] = {}
        self._file_bytes = b""
        self._finalized = False

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
        emitter = self._emitters.get(section.name)
        if emitter is None:
            emitter = BitEmitter(
                buffer=section.buffer,
                wordsize=self.config.wordsize,
            )
            self._emitters[section.name] = emitter
        return emitter

    def binary(self, name: str | None = None) -> bytes:
        return self.section(name).buffer.to_bytes()

    def final_binary(self, name: str | None = None) -> bytes:
        """Return the finalized image or one finalized section."""

        data = self.file_bytes()
        if name is None:
            return data
        section = self.sections[name]
        return data[section.file_offset : section.file_offset + section.file_size]

    @staticmethod
    def _align(value: int, alignment: int | None) -> int:
        if not alignment or alignment <= 1:
            return value
        return ((value + alignment - 1) // alignment) * alignment

    def layout(self) -> bytes:
        """Lay out all sections and return one contiguous file image."""

        if self._finalized:
            return self._file_bytes

        file_cursor = 0
        virtual_cursor = 0
        chunks: list[bytes] = []
        for name in self.config.sections:
            section = self.sections[name]
            data = section.buffer.to_bytes()
            section.file_offset = self._align(file_cursor, section.alignment)
            if section.file_offset + len(data) > MAX_IMAGE_BYTES:
                raise ValueError(
                    f"La imagen excede el límite de {MAX_IMAGE_BYTES} bytes."
                )
            if name in self.config.sectionvaddr:
                section.virtual_base = self.config.sectionvaddr[name]
            else:
                section.virtual_base = self._align(virtual_cursor, section.alignment)
            section.virtual_size = (self.emitter(name).virtual_position + 7) // 8
            if section.file_offset > file_cursor:
                chunks.append(b"\x00" * (section.file_offset - file_cursor))
            chunks.append(data)
            file_cursor = section.file_offset + len(data)
            virtual_cursor = section.virtual_base + section.virtual_size

        self._file_bytes = b"".join(chunks)
        return self._file_bytes

    def file_bytes(self) -> bytes:
        """Return the final concatenated image in configured section order."""

        return self.layout()

    def set_final_bytes(self, data: bytes) -> None:
        """Commit a finalized file image after transactional patches."""

        finalized = bytes(data)
        expected = len(self.layout())
        if len(finalized) != expected:
            raise ValueError(
                f"La imagen final contiene {len(finalized)} bytes; se esperaban {expected}."
            )
        for section in self.sections.values():
            start = section.file_offset
            end = start + section.file_size
            section.buffer.replace_bytes(finalized[start:end])
        self._file_bytes = finalized
        self._finalized = True

    def invalidate_layout(self) -> None:
        self._finalized = False

    def section_offset(self, name: str) -> int:
        self.layout()
        return self.section(name).file_offset

    def section_virtual_base(self, name: str) -> int:
        self.layout()
        return self.section(name).virtual_base

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


__all__ = ["MAX_IMAGE_BYTES", "AssemblySection", "AssemblyImage"]
