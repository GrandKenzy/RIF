# RIF 1.0.1

## RIF Frontend

RIF opcodes, keywords, token names, and syntax operations can no longer be
shadowed by Rules, tables, generic blocks, definitions, or variants. Names are
checked case-insensitively, while target-specific names such as `move` remain
available.

## STORE

STORE version 2 now supports inline hexadecimal binary blocks with
`@BINARY LABEL` and `@END`. The block stores all declared bytes as one opaque
payload, accepts optional commas and `0x` prefixes, and does not invoke media
plugins.

## PLUGINS

The image plugin now supports GBA `BGR555` output: packed
`0BBBBBGGGGGRRRRR` pixels emitted as little-endian 16-bit bytes, with
transparent pixels composited over black.

## External MIR

External MIR now supports `::RIF_INCLUDE "parts/file.gbaa"` for ordered,
relative inclusion of assembly fragments. The included file must use the
extension declared by the target linker; `.gbaa` is only an example. Nested
includes are supported, while path traversal, cycles, and excessive nesting
are rejected before Rule execution.

`::RIF_CHECKSUM` now writes final-image checksums after STORE, PCP-I,
relocations, and patches. CRC32, CRC16/CCITT-FALSE, SUM8, and the GBA header
complement are supported for the whole image or an individual section, with
optional ranges and checksum fields excluded while the value is calculated.

STORE version 2 now accepts local TTF fonts through `@FONT`. A font can be
stored as its original bytes or rasterized into a deterministic `MONO1`,
`GRAY8`, or `RGBA8888` grid atlas.

## Rule bit primitives

The closed Rule operation ABI now exposes target-neutral scalar bit
primitives: left and right shifts, bit-field extraction, and bit-field
insertion. These operations do not encode ARM, Thumb, registers, opcodes, or
endianness; targets remain responsible for declaring their own instruction
fields and emission order. The same primitives are available to Rules as
datastack transformations that can be chained before `bits`.

## Relocations

Relocations are now target-declared recipes. Simple `pc` and `abs` classes keep
the compact `@block relocations` form, while `relocations` and
`relocation_fields` tables describe bias, scaling, alignment, signedness,
templates, and split output fields. ISA-specific relocation modes were removed
from the RIF core, and the experimental GBA target was removed from the
examples and headers. The former ARM immediate helper instructions were also
removed from the core instruction vocabulary.
