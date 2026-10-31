# Binary Artifacts and Final Patches

RIF can place binary material around the external MIR phase. The two blocks
are top-level and line-oriented; `@end` terminates either block.

## `@insert`

`@insert` is a prelude. Its payloads are appended before the external MIR
starts, in declaration order:

```rif
@insert:
.section "text"
.bytes "7f454c46"
.binary "01010101"
.file "elf64.template.bin"
.call #call[make_payload]
@end
```

`.section` selects the following payload section. If omitted, the configured
`.defaultsection` is used. `.bytes` consumes hexadecimal bytes, `.binary`
consumes a bit string, `.file` reads a project-relative binary file, and
`.call` asks `funcs.py` for a binary payload.

Packages copy files referenced by `.file` into opaque `assets/` entries and
record their hashes. Packaging never executes an insert or a Python payload;
the asset is resolved when the `.pack` is used for compilation.

## Precompiled punched images (`.pci`)

A PCP-I is a precompiled pure-binary image with reserved positions (*pits*)
that a later phase can fill without changing the image size. It is suitable
for bounded headers such as ELF, PE, or GBA; it does not replace a `.pack`,
because a `.pack` contains the RIF definition and compilation data, while a
PCP-I contains a binary image ready to be filled.

The physical layout of a PCP-I v1 is:

```text
[fixed header]
[padding]
[punched binary image]
[pit table]
```

The header contains, in order, the format version, image size, padding needed
to align regions, bit mode, endianness, and `pit_count`. In v1, the version
occupies one byte and the image size occupies eight bytes. The size and
encoding of the padding descriptor, together with the fixed width of
`pit_count`, are part of the header and must be defined by the implementation
before serializing the format. Numeric fields in the container must use a fixed
endianness so the parser can read the header; the endianness field describes
values in the binary image, not values in the container itself.

Each pit-table entry is four bytes:

```text
uint16 address
uint16 size
```

`address` is an offset relative to the start of the binary image. Therefore, a
pit with `address = 0` starts at `HEADER + 0`, where `HEADER` is the base of
that image rather than the beginning of the `.pci` file. `size` specifies how
many bytes the filling phase may write. In v1, entries do not shift bytes: the
range `[address, address + size)` must fit inside the image, and pits must not
overlap.

The file size is strict. A reader must reject an unknown version, a
`pit_count` whose entries do not exactly consume the remaining bytes, a pit
outside the image, or bytes after the table. Padding must also have an explicit
size and deterministic fill value so the same PCP-I always produces the same
layout.

## `@before` and `.rplc`

`@before` runs after every MIR line and before the final binary is returned:

```rif
@before:
.rplc 24, 8, #:calc(4194304 + #:qlsize(0, "_start"))
.rplc 96, 8, #:qssize(0, "text")
.rplc 104, 8, #:calc(#:qvssize(0, "text") - 4194304)
@end
```

Offsets and optional widths are bytes. Without a width, the payload's
intrinsic byte width is used. Patches never shift the image; all patches are
validated first and committed transactionally, so an invalid patch leaves the
image unchanged.

Native expressions are:

| Expression | Result |
| :--- | :--- |
| `#:query(offset, size)` | Copies a final-image byte range. |
| `#:qssize(base, "section")` | Physical end of a section relative to `base`. |
| `#:qlsize(base, "label")` | Physical file offset of a Rule label. |
| `#:qvsize(base, "label")` | Virtual address of a Rule label. |
| `#:qvssize(base, "section")` | Virtual end of a section relative to `base`. |
| `#:calc(a + b)` / `#:calc(a - b)` | Integer addition or subtraction. |

Physical layout is built from sections in `.make section` order. Use
`.sectionalign` for byte alignment and `.sectionvaddr` when the target needs a
specific virtual base. `::SIZE` and `::VSIZE` remain Rule-local cursors; the
native queries inspect the complete sectioned image.

The [ELF64 example](../../../examples/ELF64/README.md) uses an inline ELF
template, normal Rules for machine code, and these final queries to construct
a minimal Linux executable.
