# 02. Lenguaje

RIF es lineal. Gram conserva los tokens `NEWLINE` y las Rules usan una
instrucción por línea. Los comentarios comienzan con `;`.

| Guía | Resumen |
| :--- | :--- |
| [01. Estructura de fuentes](./01-estructura-de-fuentes.md) | Declaraciones raíz, orden, comentarios y forma básica. |
| [02. Configuración y linker](./02-configuracion-y-linker.md) | Secciones, formato de salida y descubrimiento de MIR. |
| [03. Tablas y cargas](./03-tablas-y-cargas.md) | Matrices, índices perezosos, `@LOAD` y alcances. |
| [04. Rules y valores](./04-rules-y-valores.md) | Instrucciones, tokens, tablas y expresiones de valor. |

## Forma mínima

```rif
@config:
; directivas del target
@configend

@linker:
; directivas del linker
@linkerend

@table registers
| name | bits |
_
| rax | 64 |
@end

@rule mov:
-> IDENT
-> fits $registers.bits
```

Para compilar MIR, el bloque `@config` debe incluir todas sus directivas
obligatorias.
