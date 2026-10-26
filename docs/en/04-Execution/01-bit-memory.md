# Bit Memory

RIF writes bits directly into `BitBuffer`. The buffer is not restricted to
whole bytes, so a field can begin or end at any bit offset.

## Physical Cursor

Normal emission advances the physical cursor, exposed as `::SIZE`:

```rif
-> put 0000 0001
-> ebit 1 0 1 0 1 0 1 0
-> emmit 4660
-> emitbits 5 3
```

`emmit` uses `.wordsize`. `put` and `ebit` have fixed widths. `emitbits` takes
an explicit value and width and is useful for arbitrary fields.

## Rewriting Existing Bits

```rif
-> readbits 0 8
-> patchbits 0 8 255
```

`readbits OFFSET WIDTH` reads a physical range and pushes its integer value to
the datastack. `patchbits OFFSET WIDTH VALUE` rewrites an allocated range and
does not advance either cursor. An out-of-range operation fails before changing
the buffer.

For widths divisible by eight, the configured `.endianess` is used. Other
widths are read and written according to `.bitorder`.

## Padding and Alignment

```rif
-> padding 3
-> alignement 16
```

Both emit zero bits and advance physical and virtual positions. `padding` adds
the exact width. `alignement N` adds the number of bits required to reach the
next multiple of `N`. These bits are recorded as padding in the active
`RuleTrace`.

Virtual-only operations are useful when the target has a separate address
layout:

```rif
-> vpadding 8
-> valignement 32
```

They advance only the virtual cursor, exposed as `::VSIZE`. Their widths are
recorded as virtual padding.

## Reservations

```rif
-> reserve "header" 16
-> ldres "header" 0000000011111111
-> gtres "header"
-> dlres "header"
```

Physical reservations append zero-filled bits and keep a named span. `ldres`
rewrites that span, `gtres` copies its current value to the output cursor, and
`dlres` removes the name while leaving already emitted bits untouched.

Virtual reservations do not write physical bits:

```rif
-> vreserve "scratch" 64
```

`resdir`, `resvdir`, `reswidth`, and `vreswidth` query reservation metadata.
`resdist` and `resvdist` calculate the distance from the current cursor.

## Rule Traces

Every Rule invocation produces a `RuleTrace` containing physical and virtual
start, width, end, and padding fields. Nested Rules receive independent traces;
the parent span includes the output produced by its children.

## Low-Level Buffer API

Python callers that need direct memory control can use `BitBuffer`:

```python
query = buffer.query("header")
bits = buffer.read_bit_sequence(0, 12)
checkpoint = buffer.checkpoint()

with buffer.transaction():
    buffer.write_bits(0, 3, 2)
```

`rollback(checkpoint)` restores storage, bit length, and named regions.
`transaction()` rolls back automatically when its body raises. `to_bytes()`
returns a masked serialized copy; `view()` returns a live byte-level view.
`BitQuery` exposes the integer value, individual bits, span, and aligned raw
bytes when the queried range covers complete bytes.

`AssemblyImage.render()` can render configured sections using `.sectiondef`,
`.sectionend`, `.entrylabel`, `.labelend`, `.comment`, and section alignment.
