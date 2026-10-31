# Configuración y linker

`@block config` describe el formato de salida. `@block linker` describe la entrada MIR.

## Configuración

```rif
@block config:
sectiondef ".section"
make section "data"
make section "text"
make section "bss"
sectionend ":"
entrysection "text"
entrylabel "_start"
comment ";"
labelend ":"
datasection "data"
defaultsection "text"
sectionflags "text" "rx"
sectionalign "text" 4
sectionvaddr "text" 4194304
wordsize 32
addresssize 32
endianness "little"
casesensitive true
symbolprefix "_"
localprefix "."
undefinedsymbols "error"
duplicatesymbols "error"
strict true
allowemptysections false
bitorder "msb"
@end
```

Las directivas obligatorias son:

| Directiva | Significado |
| :--- | :--- |
| `sectiondef` | Prefijo al renderizar una sección. |
| `make section` | Declara una sección válida; puede repetirse. |
| `sectionend` | Termina la cabecera renderizada. |
| `entrysection` | Sección de salida predeterminada. |
| `entrylabel` | Label de entrada. |
| `comment` | Marcador de comentarios renderizados. |
| `labelend` | Terminador de labels. |
| `datasection` | Sección de símbolos de datos. |
| `defaultsection` | Sección por defecto. |
| `wordsize` | Ancho de `emmit`, en bits. |
| `addresssize` | Ancho de direcciones, en bits. |
| `endianness` | `"little"` o `"big"`. |
| `casesensitive` | Sensibilidad al resolver nombres de Rules MIR. |
| `symbolprefix` | Prefijo de símbolos renderizados. |
| `localprefix` | Prefijo de símbolos locales. |
| `undefinedsymbols` | `error`, `warn` o `ignore`. |
| `duplicatesymbols` | `error`, `warn` o `ignore`. |
| `strict` | Política estricta del target. |
| `allowemptysections` | Permite renderizar secciones vacías. |

También existen `sectionflags`, `sectionalign`, `sectionvaddr` y
`bitorder`. `sectionalign` controla la alineación física y virtual
automática en bytes; `sectionvaddr` asigna una base virtual explícita a una
sección. `bitorder` acepta `"msb"` o `"lsb"`.

## Linker

```rif
@block linker:
ext ".asm"
name "main"
searching ""
@end
```

`ext` es la extensión permitida para el MIR. `name` identifica el nombre
principal. `searching` puede ser `""` para buscar junto al archivo, una
carpeta relativa o `false` para desactivar la búsqueda automática.

La API de compilación valida la extensión del MIR antes de procesarlo.
