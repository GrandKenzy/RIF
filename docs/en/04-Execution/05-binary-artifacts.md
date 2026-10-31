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

## Precompiled punched-image sources and artifacts (`.pci`)

A final PCP-I is a binary image with reserved positions (*pits*) that a later
phase can fill without changing the image size. It is suitable for bounded
headers such as ELF, PE, or GBA.

The file passed to `--comp-pcpi` is textual RIF source. RIF produces the image
through its normal instructions, and the PCP-I adapter packages the header,
padding, and pit table. The compiled output uses `.pcic` by default; the
compiler does not copy one binary PCP-I into another binary PCP-I.

The physical layout of a PCP-I v1 is:

```text
[fixed header]
[padding]
[punched binary image]
[pit table]
```

The v1 fixed header is 19 bytes and uses little-endian for its numeric fields:

| Field | Size | Values |
| :--- | ---: | :--- |
| Version | 1 byte | `1` |
| Image size | 8 bytes | `uint64` |
| Padding size | 4 bytes | `uint32` |
| Bit mode | 1 byte | `0` LSB, `1` MSB |
| Image endianness | 1 byte | `0` little, `1` big |
| `pit_count` | 4 bytes | `uint32` |

Image endianness describes values written into the ELF, PE, or GBA header; it
does not change the PCP-I container encoding.

Each pit-table entry is four bytes:

```text
uint16 address
uint16 size
```

`address` is an offset relative to the start of the binary image. Therefore, a
pit with `address = 0` starts at `HEADER + 0`, where `HEADER` is the base of
that image rather than the beginning of the `.pcic` file. `size` specifies how
many bytes the filling phase may write. In v1, entries do not shift bytes: the
range `[address, address + size)` must fit inside the image, and pits must not
overlap.

The file size is strict. A reader must reject an unknown version, a
`pit_count` whose entries do not exactly consume the remaining bytes, a pit
outside the image, or bytes after the table. Padding must also have an explicit
size and deterministic fill value so the same PCP-I always produces the same
layout.

### Compilation

A `.pci` source must be compiled before use:

```powershell
rif --comp-pcpi image.pci
rif --comp-pcpi image.pci -o build/image.pcic
```

Without `-o`, the output is derived as `image.pcic`. Compilation preserves the
padding, image, and pit table. The compiler rejects inconsistent sizes, empty
pits, overlaps, ranges outside the image, and trailing entries.

### RIF syntax

The source must contain a normal `@config` and a Rule named `pcpi` or `image`.
If there is only one Rule, it is selected automatically. RIF instructions build
the image; each byte-aligned physical `reserve` becomes a pit:

```rif
@rule pcpi:
-> emitfr "01111111" "01000100"
-> emitfrend
-> reserve "entry_point" 16
```

`reserve "entry_point" 16` emits two zero bytes and records a two-byte pit.
`vreserve` only reserves virtual space and does not create a PCP-I pit. Existing
RIF `@insert`, `@before`, `padding`, and alignment features remain valid;
`.sectionalign` also determines the container padding before the image.

When a source contains multiple Rules, select one explicitly:

```powershell
rif --comp-pcpi image.pci --pcpi-entry header
```

The API can load a compiled PCP-I and fill a pit without shifting bytes:

```python
from pcpi import load_pcpi_file

image = load_pcpi_file("image.pcic")
payload = image.fill(0, b"\x01\x02\x03\x04")
```

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
