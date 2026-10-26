# Datastack

The datastack is a LIFO value stack shared by Rules during one external MIR
compilation. It is independent from the token stack declared with `@stack`.

## Push and Pop

```rif
@rule prepare:
-> dsave 64

@rule encode:
-> fits dload
```

`dsave VALUE` evaluates a value and pushes it. `dload` used where a `VALUE` is
expected pops the top value. `dpeek` reads the top value without removing it.
`dpop` discards the top value. `::DDEPTH` returns the current stack depth.

The following flow is common:

```rif
-> dsave 64
-> fits dload
```

The first Rule line can push a width for a later emission. `fits dload` checks
the width and removes it only after a successful fit. A failed `iffits` leaves
the value available for recovery logic.

## Table-Driven Loads

The instruction form of `dload` queries a table using the current MIR token:

```rif
-> dload ::registers.names : bits
```

It performs these operations atomically from the language point of view:

1. Read the current token value.
2. Find it in `registers.names`.
3. Push the matching row's `bits` value.
4. Consume the current token.

The selector column must contain unique keys. If the token is absent, the Rule
fails without consuming the token or pushing a value.

## State Lifetime

`RIFMachine.execute` starts an isolated run and clears the datastack.
`execute_line` processes one external MIR line while preserving the datastack,
reservations, and other cross-line state. This is what allows one MIR line to
prepare a value for a later line.

Python functions can inspect or manipulate the live list through:

```python
context.datastack
```

Target authors should keep stack ownership clear: use the datastack for
temporary values and the token storage instructions for token identity.
