# RIF: capas y nomenclatura

RIF tiene dos representaciones distintas que no deben llamarse igual.

## Definición del target RIF

Es el archivo que describe cómo se compila un lenguaje o ISA:

```text
main.rif
```

Contiene `@define`, `@table`, `@rule`, `@config`, `@linker`, variantes y
archivos `@LOAD`.

Un `.pack` es la versión empaquetada de esta definición. Puede contener los
`.rif` originales, un `funcs.py` opcional y una base SQLite con el target ya
compilado.

## Compiled Rule Set

El resultado de compilar `main.rif` o `main.pack` se llama `CompiledRuleSet`.
Es el único nombre público para esta representación.

Este objeto contiene las Rules RIF compiladas, sus instrucciones internas,
operandos resueltos y referencias a tokens, tablas y otras Rules.

No es el MIR externo del usuario.

## MIR externo

El MIR externo es el programa que será procesado contra una definición RIF:

```text
target.pack + program.mir → program.bin
```

Sus instrucciones representan lo que las Rules del target esperan consumir.
Por ejemplo, una Rule que reconoce `mov IDENT` puede consumir una instrucción
MIR equivalente a:

```text
mov r0
```

El MIR externo ya puede entrar por dos rutas equivalentes:

```python
from MIR import compile_mir_file, compile_mir_tokens, prepare_target

compile_mir_file("target.pack", "program.asm", output="program.bin")
target = prepare_target("target.pack")
compile_mir_tokens(target, tokens)
```

La primera valida la extensión declarada por `.ext`, lee el archivo y lo
tokeniza. La segunda recibe tokens ya producidos por otro compilador y no
vuelve a lexearlos ni a parsearlos. Ambas rutas usan el mismo dispatcher y
producen binario puro de la sección de entrada.

Cuando una Rule usa `CALL` o `#call[...]`, RIF busca `funcs.py` junto a
`main.rif` o en la raíz del `.pack`. El módulo debe exponer:

```python
def handler(name, context):
    return True
```

El contexto entrega vistas vivas de tablas, configuración, Rules, `coder`,
buffer y binario actual. Las funciones solo pueden devolver `True`, `False` o
strings binarios como `"000"`.

## Flujo completo

```text
main.rif
    │
    ├── parseo Gram
    ├── resolución de LOAD, tablas y configuración
    └── CompiledRuleSet

main.pack
    │
    └── SQLite/MIR precompilado → CompiledRuleSet

CompiledRuleSet + MIR externo
    │
    └── MIR externo despachado por RIFMachine
            │
            └── BitBuffer / AssemblyImage → binario puro
```

## Posiciones, padding y trazas

Las Rules pueden emitir zeros de forma explícita o reservarlos para
alineamiento:

```text
-> padding 12
-> alignement 32
```

Ambas operaciones agregan bits cero, pero el runtime las contabiliza como
padding. Los zeros producidos por `emmit`, `put`, `ebit` o `emitfr` no se
marcan como padding. `alignement N` agrega entre cero y `N - 1` bits para que
la posición actual sea múltiplo de `N`.

Cada invocación de una Rule produce un `RuleTrace` con `start`, `bits`, `end`
y `padding_bits`. Las invocaciones anidadas tienen su propio trace; el trace
de la Rule padre cubre también los bits emitidos por sus Rules hijas.

Los valores de posición se pueden usar en cualquier operación que acepte un
`VALUE`:

```text
::SIZE                 ; posición física actual, en bits
::VSIZE                ; posición virtual actual, hoy igual a SIZE
::ALIGNMENT            ; alineamiento configurado de la sección activa
dist "label"           ; distancia física hasta una etiqueta o Rule
vdist "label"          ; distancia virtual, hoy igual a dist
resdir "slot"          ; dirección física de una reserva
resvdir "slot"         ; dirección virtual, hoy igual a resdir
resdist "slot"         ; distancia física hasta una reserva
resvdist "slot"        ; distancia virtual, hoy igual a resdist
```

Las reservas se expresan en el mismo espacio de bits que el buffer. El
contexto entregado a `funcs.py` también expone `rule_traces`,
`last_rule_trace` y `virtual_position`.

## Nombres canónicos

| Concepto | Nombre |
|---|---|
| Archivo de definición | RIF definition |
| Paquete de definición | RIF pack |
| Rules compiladas | `CompiledRuleSet` |
| Reglas compiladas | `CompiledRule` dentro de `CompiledRuleSet` |
| Programa que entra al target | External MIR |
| Resultado final | Pure binary output |
