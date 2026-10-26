# Inserts binarios y parches finales

RIF puede colocar material binario alrededor de la fase del MIR externo. Los
dos bloques son de nivel raíz y lineales; `@end` termina cualquiera de ellos.

## `@insert`

`@insert` es un preámbulo. Sus payloads se agregan antes de iniciar el MIR,
respetando el orden de declaración:

```rif
@insert:
.section "text"
.bytes "7f454c46"
.binary "01010101"
.file "elf64.template.bin"
.call #call[make_payload]
@end
```

`.section` selecciona la sección de los payloads siguientes. Si se omite, se
usa `.defaultsection`. `.bytes` recibe bytes hexadecimales, `.binary` recibe
bits, `.file` lee un archivo binario relativo al proyecto y `.call` pide un
payload binario a `funcs.py`.

Los paquetes copian los archivos de `.file` dentro de entradas opacas en
`assets/` y registran sus hashes. Empaquetar nunca ejecuta un insert ni un
payload Python; el asset se resuelve al compilar usando el `.pack`.

## `@before` y `.rplc`

`@before` corre después de todas las líneas MIR y antes de devolver el binario
final:

```rif
@before:
.rplc 24, 8, #:calc(4194304 + #:qlsize(0, "_start"))
.rplc 96, 8, #:qssize(0, "text")
.rplc 104, 8, #:calc(#:qvssize(0, "text") - 4194304)
@end
```

Los offsets y anchos opcionales están expresados en bytes. Si no se indica un
ancho, se usa el ancho intrínseco del payload. Los parches no desplazan la
imagen; todos se validan primero y se aplican de forma transaccional, por lo
que un parche inválido no deja cambios parciales.

Las expresiones nativas son:

| Expresión | Resultado |
| :--- | :--- |
| `#:query(offset, size)` | Copia un rango de bytes de la imagen final. |
| `#:qssize(base, "section")` | Fin físico de una sección relativo a `base`. |
| `#:qlsize(base, "label")` | Offset físico del label en el archivo. |
| `#:qvsize(base, "label")` | Dirección virtual del label. |
| `#:qvssize(base, "section")` | Fin virtual de una sección relativo a `base`. |
| `#:calc(a + b)` / `#:calc(a - b)` | Suma o resta entera. |

El layout físico usa el orden de `.make section`. `.sectionalign` alinea en
bytes y `.sectionvaddr` permite fijar una base virtual. `::SIZE` y `::VSIZE`
siguen siendo cursores locales de cada Rule; las queries nativas inspeccionan
la imagen completa.

El [ejemplo ELF64](../../../examples/ELF64/README.md) usa una plantilla ELF,
Rules normales para el código máquina y estas queries para construir un
ejecutable Linux mínimo.
