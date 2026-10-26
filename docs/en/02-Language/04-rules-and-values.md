# Rules and Values

Rule bodies are line-oriented instruction sequences. The current instruction
families are grouped below.

## Token Consumers

```rif
-> IDENT
-> KW "ret"
-> [NUMBER, STRING]
```

`IDENT`, `NUMBER`, and other canonical `Token` names consume a matching token.
`KW` consumes a keyword with an exact string value. The bracket form stores the
first matching token from its candidates.

## Rule Control

```rif
-> JMP mov
-> jmpif mov, true
-> jmpif mov, #call[should_jump]
-> CALL #call[emit_value]
-> break
-> error, "invalid instruction"
```

`JMP` invokes another Rule and returns when it finishes. `jmpif` invokes it only
when its boolean condition is true. `CALL` invokes a Python function. `break`
stops the current Rule flow.

Token storage is separate from the datastack:

```rif
-> save "current"
-> load "current"
```

`save` records the current token under a label. `load` requires the current
token to match that saved token and then consumes it.

## Emission

```rif
-> put 0000 0000
-> ebit 0 1 0 1 0 1 0 1
-> emmit 83847483
-> emitfr 0000 0
00000000
0000
-> emitfrend
```

`put` emits two four-bit fields. `ebit` emits eight one-bit fields. `emmit`
uses `.wordsize`. `emitfr` emits a multiline frame and accepts any `VALUE` in
its rows.

## Tables, Reservations, and Positions

```rif
-> reserve "slot" 16
-> ldres "slot" 0000000000000000
-> gtres "slot"
-> dlres "slot"
-> emmit &slot
-> emmit ::SIZE
-> emmit ::VSIZE
```

`&slot` reads a reservation as a value. `reserve` creates a zero-filled named
region, `ldres` patches it, `gtres` copies it into the current output, and
`dlres` removes its name without clearing its previous bits.

## Immediate Fitting

```rif
-> fits 8
-> iffits 8
-> ifnfits 8
-> fits $registers.name[rax].bits
```

These instructions operate on the current MIR token. `fits` emits the low bits
when the value is too wide. `iffits` emits only when the value fits exactly.
`ifnfits` consumes a value only when it does not fit.

Widths can be values obtained from a table, a Python function, a reservation,
or the datastack.

## Value Forms

RIF values include numeric and string literals, booleans, table accesses,
reservation accesses, calls, and position queries:

```rif
$registers.bits
$registers.name[rax].bits
&slot
#call[get_bits]
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
