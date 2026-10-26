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
::VSIZE                ; posición virtual actual, en bits
::ALIGNMENT            ; alineamiento configurado de la sección activa
dist "label"           ; distancia física hasta una etiqueta o Rule
vdist "label"          ; distancia virtual desde una Rule o reserva
resdir "slot"          ; dirección física de una reserva
resvdir "slot"         ; dirección virtual de una reserva
resdist "slot"         ; distancia física hasta una reserva
resvdist "slot"        ; distancia virtual hasta una reserva
reswidth "slot"        ; ancho físico de una reserva
vreswidth "slot"       ; ancho virtual de una reserva
```

Las reservas se expresan en el mismo espacio de bits que el buffer. El
contexto entregado a `funcs.py` también expone `rule_traces`,
`last_rule_trace` y `virtual_position`.

## Inmediatos ajustados

`fits` consume el token MIR actual y lo escribe en un ancho explícito:

```text
-> fits 16
-> fits $registers.names[rax].bits
```

La segunda forma resuelve una fila estática de una tabla. El selector `rax`
no consume tokens MIR; solo el inmediato actual se consume. Los anchos deben
ser positivos y múltiplos de dos. `fits` conserva los bits menos significativos
cuando el valor excede el ancho.

`iffits` hace la misma emisión sin truncar y falla si el valor no cabe.
`ifnfits` comprueba la condición opuesta, consume el token sin emitirlo cuando
no cabe y falla si sí cabe.

Los dos espacios se comportan así:

```text
-> vpadding 16
-> vreserve "scratch" 32
```

Las operaciones de emisión normales avanzan `SIZE` y `VSIZE`. `vpadding` y
`vreserve` avanzan únicamente `VSIZE`; la reserva virtual no crea bytes ni un
`BitSpan` físico.

`valignement N` avanza solo `VSIZE` hasta el próximo múltiplo de `N` y cuenta
ese avance como padding virtual. Una reserva física creada después de
`vpadding` conserva offsets físico y virtual distintos.

## Datastack y consultas de tablas

`datastack` es una pila LIFO de valores compartida por las Rules de una misma
compilación. Es independiente de los slots declarados con `@stack`. Persiste
entre líneas del MIR externo y se reinicia al iniciar una ejecución aislada
con `RIFMachine.execute`.

```text
-> dsave 64                         ; apila un VALUE
-> fits dload                      ; usa y extrae el ancho 64
-> dload ::registers.names : bits  ; busca el token actual en names,
                                   ; apila bits y consume el token
-> fits dload                      ; usa el ancho obtenido de la tabla
-> dpop                            ; descarta el valor superior
```

`dpeek` consulta el valor superior sin extraerlo y `::DDEPTH` devuelve el
número de valores apilados. La búsqueda de `dload` requiere claves únicas
en la columna selectora. Las otras columnas pueden repetir valores. El índice
de la columna selectora se construye solo cuando se utiliza.

## Acceso directo a bits

```text
-> emitbits 5 3                    ; emite 101 en tres bits
-> readbits 0 3                   ; apila el entero leído del rango [0, 3)
-> patchbits 0 3 2                ; reescribe ese rango con 010
-> emitbits dload 3               ; emite el valor previamente leído
```

Los offsets y anchos están en bits. `emitbits` avanza ambos cursores;
`readbits` y `patchbits` no avanzan ninguno. Los rangos de lectura y
reescritura deben estar ya asignados, y una reescritura fuera de rango falla
sin alterar bytes anteriores. Los campos de ancho múltiplo de ocho respetan
`.endianess` y `.bitorder`, igual que la emisión normal. `reswidth` y
`vreswidth` permiten calcular anchos de reservas sin codificarlos dos veces.
`funcs.py` también puede consultar la pila viva mediante `context.datastack`.

## Nombres canónicos

| Concepto | Nombre |
|---|---|
| Archivo de definición | RIF definition |
| Paquete de definición | RIF pack |
| Rules compiladas | `CompiledRuleSet` |
| Reglas compiladas | `CompiledRule` dentro de `CompiledRuleSet` |
| Programa que entra al target | External MIR |
| Resultado final | Pure binary output |
