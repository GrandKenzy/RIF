# Datastack

El datastack es una pila LIFO de valores compartida por las Rules durante una
compilación MIR. Es independiente del stack de tokens de `@stack`.

## Push y pop

```rif
@rule prepare:
-> dsave 64

@rule encode:
-> fits dload
```

`dsave VALUE` evalúa y apila. `dload` usado como `VALUE` extrae el valor
superior. `dpeek` lo consulta sin extraerlo; `dpop` lo descarta y `::DDEPTH`
devuelve la profundidad.

`fits dload` valida el ancho y solo lo extrae después de un ajuste exitoso. Un
`iffits` fallido conserva el ancho para que una Rule pueda recuperarlo.

## Carga desde tablas

```rif
-> dload ::registers.names : bits
```

La forma de instrucción de `dload`:

1. Lee el valor del token actual.
2. Lo busca en `registers.names`.
3. Apila el campo `bits` de la fila encontrada.
4. Consume el token actual.

La columna selectora necesita claves únicas. Si no encuentra el token, la Rule
falla sin consumirlo ni modificar la pila.

## Duración del estado

`RIFMachine.execute` inicia una ejecución aislada y limpia el datastack.
`execute_line` conserva datastack, reservas y demás estado entre líneas MIR.
Las funciones Python pueden leer la lista viva con `context.datastack`.
