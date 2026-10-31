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

## Imágenes perforadas precompiladas (`.pci`)

Una PCP-I es una imagen binaria pura precompilada con posiciones reservadas
(*pits*) que otra fase puede completar sin cambiar el tamaño de la imagen. Es
adecuada para headers de tamaño acotado, como ELF, PE o GBA; no sustituye a un
`.pack`, porque el `.pack` contiene la definición de RIF y la información de
compilación, mientras que una PCP-I contiene una imagen binaria lista para
rellenarse.

La disposición física de una PCP-I v1 es:

```text
[header fijo]
[padding]
[imagen binaria perforada]
[tabla de pits]
```

El header contiene, en orden, la versión del formato, el tamaño de la imagen,
el padding necesario para alinear regiones, el modo de bits, la endianidad y
`pit_count`. En v1, la versión ocupa un byte y el tamaño de la imagen ocupa
ocho bytes. El tamaño y la codificación del descriptor de padding, así como el
ancho fijo de `pit_count`, forman parte del header y deben quedar definidos por
la implementación antes de serializar el formato. Los campos numéricos del
contenedor deben usar una endianidad fija para que el parser pueda leer el
header; el campo de endianidad describe los valores de la imagen binaria, no
los del propio contenedor.

Cada entrada de la tabla usa cuatro bytes:

```text
uint16 address
uint16 size
```

`address` es un desplazamiento relativo al inicio de la imagen binaria. Por
tanto, un pit con `address = 0` comienza en `HEADER + 0`, donde `HEADER` es la
base de esa imagen y no el inicio del archivo `.pci`. `size` indica cuántos
bytes puede escribir la fase que completa la PCP-I. En v1 las entradas no
desplazan bytes: el rango `[address, address + size)` debe caber dentro de la
imagen, y los pits no deben solaparse.

El tamaño del archivo es estricto. Un lector debe rechazar una versión
desconocida, un `pit_count` cuyo número de entradas no coincida con los bytes
restantes, un pit fuera de la imagen o bytes adicionales después de la tabla.
El padding también debe tener un tamaño explícito y un valor de relleno
determinista para que la misma PCP-I produzca siempre el mismo layout.

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
