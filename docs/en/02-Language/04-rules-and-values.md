# Rules and Values

Rule bodies are line-oriented instruction sequences. The current instruction
families are grouped below.

## Token Consumers

```rif
. IDENT
. KW "ret"
. [NUMBER, STRING]
```

`IDENT`, `NUMBER`, and other canonical `Token` names consume a matching token.
`KW` consumes a keyword with an exact string value. The bracket form stores the
first matching token from its candidates.

## Rule Control

```rif
. JUMP mov
. JUMPIF mov, true
. BREAK
. ERROR, "invalid instruction"
```

`JUMP` invokes another Rule and returns when it finishes. `JUMPIF` invokes it only
when its boolean condition is true. `BREAK` stops the current Rule flow.
`#call[...]` is reserved for closed native operations. It does not load a
Python callback, and an unregistered name is rejected. Prefer the declarative
Rule primitives and table values described on this page.

Token storage is separate from the datastack:

```rif
. save "current"
. load "current"
```

`save` records the current token under a label. `load` requires the current
token to match that saved token and then consumes it.

## Emission

```rif
. nibbles 0000 0000
. emit 0 1 0 1 0 1 0 1
. eword 83847483
. frame 0000 0
00000000
0000
. frameend
```

`nibbles` emits two four-bit fields. `emit` emits eight one-bit fields. `eword`
uses `word_size`. `frame` emits a multiline frame and accepts any `VALUE` in
its rows.

## Tables, Reservations, and Positions

```rif
. reserve "slot" 16
. write_res "slot" 0000000000000000
. emit_res "slot"
. drop_res "slot"
. eword &slot
. eword ::SIZE
. eword ::VSIZE
```

`&slot` reads a reservation as a value. `reserve` creates a zero-filled named
region, `write_res` patches it, `emit_res` copies it into the current output, and
`drop_res` removes its name without clearing its previous bits.

## Reusable Target Primitives

Rules can combine these primitives without making the RIF core know an ISA:

- `table_matcher` and `dget` select rows from any extensible table and capture
  fields; tables are not limited to registers.
- `bits`, `nibbles`, `emit`, `eword`, and `frame` emit fields and values.
- `fit`, `fit_exact`, `fit_not`, and the `fit_signed*` variants validate and
  emit immediates using target-declared widths and ranges.
- `reserve`, `write_res`, `emit_res`, and `drop_res` compose deferred fields.
- `mark` and `fixup` connect symbols to relocations after layout.

The generic primitive checks used by fitting and relocation encoding have a
stable C/AOT contract. Target-specific instruction meaning remains in Rules
and tables.

The built-in relocation classes are `pc8`, `pc16`, `pc32`, `pc64` for signed
displacements from the next instruction and `abs8`, `abs16`, `abs32`, `abs64`
for absolute virtual addresses. Targets can add target-neutral classes through
an extensible block:

```rif
@block relocations:
    rel24 24 pc
    addr48 48 abs
@end
```

They are then used as `. fixup rel24 "slot"`. All relocations are validated and
planned before any patch is committed.

For a non-contiguous or scaled encoding, targets can declare a recipe in the
`relocations` table and its output fields in `relocation_fields`. A recipe can
declare `pc_bias`, `scale`, `alignment`, `signed`, and a fixed `template`; each
field declares `source_shift`, `width`, and `target_shift`. This keeps split
fields and instruction templates in target data while the core only performs
generic arithmetic and bit placement.

For example, a target can describe a 16-bit field with an 11-bit signed
displacement without naming the encoding in RIF:

```rif
@table relocations
| name | width | mode | pc_bias | scale | alignment | signed | template |
__
| short_branch | 16 | pc | 2 | 2 | 2 | true | 0xE000 |
@end

@table relocation_fields
| relocation | source_shift | width | target_shift |
__
| short_branch | 0 | 11 | 0 |
@end
```

The Rule then only refers to `. fixup short_branch "slot"`. The same recipe
model supports several fields sourced from one scaled value.

Memory forms, registers, and prefixes remain target data and Rules; RIF only
provides the generic machinery to select, validate, and emit them.

## Generic bit transformations

Rules can compose scalar bit operations through the datastack:

```rif
. dpush 0xD4
. shift_right dget 2
. extract_bits dget 0 4
. bits dget 4
```

`shift_left` and `shift_right` take `value, amount`; `extract_bits` takes
`value, offset, width`; and `insert_bits` takes `base, value, offset, width`.
Each operation validates its inputs and pushes one result. `dget` consumes the
result when it is ready to emit. These instructions manipulate scalar fields
only; they do not know about an ISA, instruction templates, or byte order.

## Immediate Fitting

```rif
. fit 8
. fit_exact 8
. fit_not 8
. fit_signed 8
. fit_signed_exact 8
. fit_signed_not 8
. fit $registers.name[rax].bits
```

These instructions operate on the current MIR token. `fit` emits the low bits
when the value is too wide. `fit_exact` emits only when the value fits exactly.
`fit_not` consumes a value only when it does not fit. The `fit_signed` variants
accept signed immediates such as `-1` and emit two's-complement bits;
`fit_signed_exact` requires the signed range, while `fit_signed_not` consumes a
value only when it falls outside that range.

Widths can be values obtained from a table, a reservation, or the datastack.

## Value Forms

RIF values include numeric and string literals, booleans, table accesses,
reservation accesses, and position queries:

```rif
$registers.bits
$registers.name[rax].bits
&slot
::SIZE
::VSIZE
::ALIGNMENT
dist "mov"
vdist "mov"
resdir "slot"
resvdir "slot"
resdist "slot"
resvdist "slot"
reswidth "slot"
vreswidth "slot"
```

Token references inside consumers use canonical names from `gram.lexer.Token`
or their numeric enum value. The `token_names` keyword group is populated from
the complete enum at frontend initialization.

Binary strings preserve their written width, including leading zeroes. This is
why `0000`, `"0000"`, and a numeric value are useful in different contexts:
the first form retains a source width for fixed fields, while a quoted binary
string is validated as a complete bit sequence at runtime.
