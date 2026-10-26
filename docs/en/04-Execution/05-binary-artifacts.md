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
