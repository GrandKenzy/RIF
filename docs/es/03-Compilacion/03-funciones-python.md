# Funciones Python

RIF carga un `funcs.py` junto a `main.rif` o en la raíz de un `.pack`. Debe
definir un handler:

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

Recibe el nombre usado por `#call[name]` y un `RIFFunctionContext` vivo.

## Valores permitidos

En Rules se aceptan `True`, `False` o un string binario no vacío compuesto por
`0` y `1`. En un `.call` de `@insert` y en expresiones nativas finales también
se aceptan `bytes`, `bytearray` y `memoryview`. Enteros, strings arbitrarios y
`None` producen error.

## Invocación

```rif
-> emmit #call[get_value]
-> jmpif target, #call[should_jump]
-> CALL #call[notify]
```

## Contexto

El contexto expone vistas de:

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

`context.coder` es el `BitEmitter` activo y `context.binary` refleja el buffer
actual. `context.image_binary` y `context.final_binary` exponen la imagen
completa por secciones ya organizada. El módulo se carga una sola vez por
target preparado; fallos de carga, handler o retorno inválido se reportan con
su origen.
