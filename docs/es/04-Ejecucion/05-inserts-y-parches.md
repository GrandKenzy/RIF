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
usa `defaultsection`. `.bytes` recibe bytes hexadecimales, `.binary` recibe
bits, `.file` lee un archivo binario relativo al proyecto y `.call` pide un
payload binario a `funcs.py`.

Los paquetes copian los archivos de `.file` dentro de entradas opacas en
`assets/` y registran sus hashes. Empaquetar nunca ejecuta un insert ni un
payload Python; el asset se resuelve al compilar usando el `.pack`.

## Fuentes e imágenes perforadas precompiladas (`.pci`)

Una PCP-I final es una imagen binaria con posiciones reservadas (*pits*) que
otra fase puede completar sin cambiar el tamaño de la imagen. Es adecuada para
headers de tamaño acotado, como ELF, PE o GBA.

El archivo que recibe `--comp-pcpi` es una fuente RIF textual. RIF genera la
imagen mediante sus instrucciones normales y el adaptador PCP-I empaqueta el
header, el padding y la tabla de pits. La salida compilada usa `.pcic` por
defecto; no se copia una PCP-I binaria hacia otra PCP-I binaria.

La disposición física de una PCP-I v1 es:

```text
[header fijo]
[padding]
[imagen binaria perforada]
[tabla de pits]
```

El header fijo de v1 ocupa 19 bytes y usa little-endian para sus campos
numéricos:

| Campo | Tamaño | Valores |
| :--- | ---: | :--- |
| Versión | 1 byte | `1` |
| Tamaño de imagen | 8 bytes | `uint64` |
| Tamaño de padding | 4 bytes | `uint32` |
| Modo de bits | 1 byte | `0` LSB, `1` MSB |
| Endianidad de la imagen | 1 byte | `0` little, `1` big |
| `pit_count` | 4 bytes | `uint32` |

La endianidad de la imagen describe los valores que se escribirán en el
header ELF, PE o GBA; no cambia la codificación del contenedor PCP-I.

Cada entrada de la tabla usa cuatro bytes:

```text
uint16 address
uint16 size
```

`address` es un desplazamiento relativo al inicio de la imagen binaria. Por
tanto, un pit con `address = 0` comienza en `HEADER + 0`, donde `HEADER` es la
base de esa imagen y no el inicio del archivo `.pcic`. `size` indica cuántos
bytes puede escribir la fase que completa la PCP-I. En v1 las entradas no
desplazan bytes: el rango `[address, address + size)` debe caber dentro de la
imagen, y los pits no deben solaparse.

El tamaño del archivo es estricto. Un lector debe rechazar una versión
desconocida, un `pit_count` cuyo número de entradas no coincida con los bytes
restantes, un pit fuera de la imagen o bytes adicionales después de la tabla.
El padding también debe tener un tamaño explícito y un valor de relleno
determinista para que la misma PCP-I produzca siempre el mismo layout.

### Compilación

Una fuente `.pci` debe compilarse antes de usarse:

```powershell
rif --comp-pcpi image.pci
rif --comp-pcpi image.pci -o build/image.pcic
```

Sin `-o`, la salida se deriva como `image.pcic`. La compilación conserva el
padding, la imagen y la tabla de pits. El compilador rechaza tamaños
inconsistentes, pits vacíos, solapamientos, rangos fuera de la imagen y
entradas adicionales.

### Sintaxis RIF

La fuente debe contener una `@block config` normal y una Rule llamada `pcpi` o
`image`. Si solo existe una Rule, se usa automáticamente. Las instrucciones
RIF construyen la imagen; cada `reserve` físico alineado a bytes se convierte
en un pit:

```rif
@rule pcpi:
-> emitfr "01111111" "01000100"
-> emitfrend
-> reserve "entry_point" 16
```

`reserve "entry_point" 16` emite dos bytes en cero y registra un pit de dos
bytes. `vreserve` solo reserva espacio virtual y no genera un pit PCP-I. Los
`@insert`, `@before`, `padding` y alineamientos existentes de RIF siguen siendo
válidos; `sectionalign` también determina el padding del contenedor antes de
la imagen.

Si la fuente contiene varias Rules, puede seleccionarse una explícitamente:

```powershell
rif --comp-pcpi image.pci --pcpi-entry header
```

La API puede cargar una PCP-I compilada y rellenar un pit sin desplazar bytes:

```python
from pcpi import load_pcpi_file

image = load_pcpi_file("image.pcic")
payload = image.fill(0, b"\x01\x02\x03\x04")
```

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

El layout físico usa el orden de `make section`. `sectionalign` alinea en
bytes y `sectionvaddr` permite fijar una base virtual. `::SIZE` y `::VSIZE`
siguen siendo cursores locales de cada Rule; las queries nativas inspeccionan
la imagen completa.

El [ejemplo ELF64](../../../examples/ELF64/README.md) usa una plantilla ELF,
Rules normales para el código máquina y estas queries para construir un
ejecutable Linux mínimo.
