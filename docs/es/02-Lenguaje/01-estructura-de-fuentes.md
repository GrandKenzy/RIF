# Estructura de fuentes

El archivo raíz suele llamarse `main.rif`. Puede declarar objetos del target
en cualquier orden; el procesador registra primero configuración, linker,
definiciones y soportes, y después resuelve tablas y Rules.

## Comentarios y saltos de línea

```rif
; comentario RIF
@define mov ; comentario al final
```

Los saltos de línea son significativos dentro de una Rule:

```rif
@rule mov:
-> IDENT
-> emmit 1
```

No existe una gramática de indentación para Rules.

## Declaraciones por alcance

La raíz puede contener `@block config`, `@block linker`, `@table`, `@stack`, `@SUPPORTS`,
`@ASMVARIANT`, `@define`, `@rule` y `@LOAD`.

Un archivo cargado con `@LOAD` solo puede contener `@define`, `@table`, `@rule`
y más `@LOAD`. Un archivo de variante solo puede contener `@define` y `@rule`.

Así una fuente cargada no reemplaza silenciosamente la memoria ni la política
del target.

## Bloques genéricos

La forma genérica de declarar datos por bloques es:

```rif
@block config:
sectiondef ".section"
make section "text"
wordsize 8
@end
```

Cada línea contiene un nombre y cero, uno o dos valores antes del salto de
línea. No se aceptan prefijos de punto ni las antiguas cabeceras
`@config`/`@linker`; una línea con más de dos valores es inválida.

Los bloques `config` y `linker` alimentan directamente la semántica existente de RIF.
Los bloques con otros nombres se conservan como datos estructurados en
`program.context.blocks`, para que los consumidores especializados puedan
interpretarlos sin añadir una nueva regla al parser.

## Definiciones

```rif
@define mov
@define add
```

Una definición es una palabra registrada; no reserva slots, no emite bits y no
crea un valor runtime.

## Rules

```rif
@rule mov:
-> IDENT
-> put 0000 0000
```

Una línea MIR que empieza con `mov` se despacha a esta Rule.

## Stack de tokens

```rif
@stack 50
```

Solo puede existir un `@stack`. Sus instrucciones `save` y `load` trabajan con
tokens y es distinto del `datastack` de valores temporales.
