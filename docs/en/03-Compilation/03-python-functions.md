# Python Functions

RIF loads an optional `funcs.py` beside `main.rif`, or from the root of a
`.pack`. The module must define one handler:

```python
def handler(name, context):
    if name == "should_jump":
        return True
    if name == "get_bits":
        return "00001000"
    if name == "make_payload":
        return b"\x7fELF"
    return False
```

The handler receives the function name from `#call[name]` and a live
`RIFFunctionContext`.

## Return Contract

Only these results are accepted:

- `True`
- `False`
- a non-empty binary string containing only `0` and `1`
- `bytes`, `bytearray`, or `memoryview` when called by an `@insert .call` or
  native final expression

Integers, arbitrary strings, `None`, and other objects are rejected. This
keeps external functions explicit about whether they return a condition or a
bit field.

## Calling Functions

As a value:

```rif
@rule emit_value:
-> emmit #call[get_value]
```

As a condition:

```rif
@rule conditional:
-> jmpif target, #call[should_jump]
```

As a standalone instruction:

```rif
@rule invoke:
-> CALL #call[notify]
```

## Context

The context exposes live views of:

```python
context.config
context.linker
context.defines
context.tables
context.rules
context.stack
context.datastack
context.coder
context.buffer
context.binary
context.image_binary
context.final_binary
context.file_offset
context.virtual_base
context.tokens
context.position
context.rule_traces
context.virtual_position
context.virtual_regions
context.current_token
context.last_token
context.storage
context.selected_rows
```

`context.coder` is the active `BitEmitter`. `context.binary` is a view of the
current output buffer, so a function can inspect the output already produced
by previous instructions. `context.image_binary` and `context.final_binary`
return the complete sectioned file image currently laid out. Binary payload
calls reject booleans and arbitrary strings; they accept bytes-like values or
binary strings.

## Loading Rules

The function module is loaded once per prepared target. Errors while loading
the module, missing handlers, handler exceptions, and invalid return values are
reported as RIF function errors with the source origin attached.
