# Rules y valores

El cuerpo de una Rule es una secuencia de instrucciones, una por línea.

## Consumidores de tokens

```rif
-> IDENT
-> KW "ret"
-> [NUMBER, STRING]
```

Los nombres canónicos como `IDENT` y `NUMBER` consumen el token esperado. `KW`
exige un keyword con valor exacto. La forma entre corchetes guarda el primer
token candidato que coincida.

## Control de Rules

```rif
-> JMP mov
-> jmpif mov, true
-> jmpif mov, #call[should_jump]
-> CALL #call[emit_value]
-> break
-> error, "instrucción inválida"
```

`JMP` llama otra Rule y regresa al terminar. `jmpif` la llama solo si la
condición es verdadera. `CALL` invoca Python y `break` termina el flujo actual.

El almacenamiento de tokens es distinto del datastack:

```rif
-> save "current"
-> load "current"
```

`save` guarda el token actual bajo un label. `load` exige que el token actual
coincida con el guardado y después lo consume.

## Emisión

```rif
-> put 0000 0001
-> ebit 1 0 1 0 1 0 1 0
-> emmit 4660
-> emitfr 0000 0
00000000
0000
-> emitfrend
```

`put` emite dos campos de cuatro bits; `ebit`, ocho campos de un bit; `emmit`,
una palabra de `wordsize`; y `emitfr`, un frame multilinea con cualquier
`VALUE`.

## Tablas, reservas y posiciones

```rif
-> reserve "slot" 16
-> ldres "slot" 0000000011111111
-> gtres "slot"
-> dlres "slot"
-> emmit &slot
-> emmit ::SIZE
-> emmit ::VSIZE
```

`&slot` lee una reserva. `reserve` crea bits en cero, `ldres` los parchea,
`gtres` copia la reserva al cursor y `dlres` quita su nombre sin limpiar los
bits ya emitidos.

## Ajuste de inmediatos

```rif
-> fits 8
-> iffits 8
-> ifnfits 8
-> fits $registers.name[rax].bits
```

Estas instrucciones usan el token MIR actual. `fits` conserva los bits bajos
si el valor es demasiado grande. `iffits` falla si no cabe. `ifnfits` consume
solo cuando no cabe.

## Formas de `VALUE`

Se aceptan literales numéricos y string, booleanos, accesos a tablas, reservas,
llamadas y consultas de posición:

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

Los consumidores aceptan nombres canónicos de `gram.lexer.Token` o el número
de su enum. El grupo `token_names` se rellena con todos los miembros del enum
al iniciar el frontend.

Los strings binarios conservan sus ceros iniciales. Por eso `0000`, `"0000"`
y un número pueden ser útiles en contextos distintos: la primera forma conserva
el ancho escrito para campos fijos y el string se valida como una secuencia
completa de bits en runtime.
