# MIR externo

El MIR externo es un programa lineal cuyo primer token selecciona una Rule:

```text
mov rax, 1
add rbx, 2
```

Los tokens restantes son consumidos por la Rule. Si una línea deja tokens sin
consumir, la compilación falla.

## Directivas de metaprogramación

El MIR externo puede contener marcadores reservados para integrar artefactos
binarios administrados por RIF:

```text
::RIF_PCPI SET "header.pcic"
::RIF_PCPI PIT 0
::RIF_PCPI PIT 0 SECTION text
::RIF_STORE "imagenes.bin" miImage 1 0
mov rax, 1
```

`::RIF_PCPI SET` debe ser la primera línea no vacía. Carga un `.pcic` y copia
el contenedor completo en la sección actual. `::RIF_PCPI PIT` no genera bytes:
consulta la dirección absoluta del payload reservado, contando desde el offset
`0` del archivo final. La forma `SECTION text` usa el offset real de esa
sección. Las consultas quedan en `MIRCompilation.pcpi_pit_addresses` y la CLI
las muestra.

`::RIF_STORE`
recibe `ENDIANNESS` (`1` little, `2` big) y `BITORDER` (`0` LSB, `1` MSB),
resuelve la ruta relativa al archivo MIR, abre el `storage.bin`, extrae el raw
por label y lo inserta en la sección actual. Para no repetir una ruta se puede
declarar un alias una vez y usarlo después:

```text
::RIF_STORE AS gba "build/gba.storage.bin"
gba.ORDER 1
gba.ENDIANNESS 1
::RIF_STORE gba titulo
::RIF_STORE gba ancho
```

El alias es local a esa compilación MIR y debe declararse antes de usarse. El
alias configura el orden de bits (`ORDER`, `0` LSB o `1` MSB) y el orden de
bytes (`ENDIANNESS`, `1` little o `2` big) para los valores tipados. Los
payloads raw, imágenes, audio y archivos se copian sin transformación. La
forma antigua con ruta y los cuatro argumentos numéricos sigue siendo válida.

`::RIF_INCLUDE` inserta un archivo en la posición actual, permitiendo separar
un MIR grande en partes ordenadas sin depender de las rutas de búsqueda del
linker. El archivo incluido debe usar la extensión declarada por el linker;
`.gbaa` es válido cuando el linker declara `.gbaa`:

```text
::RIF_INCLUDE "parts/init.gbaa"
::RIF_INCLUDE "parts/copy_cube.gbaa"
::RIF_INCLUDE "parts/controls.gbaa"
::RIF_INCLUDE "parts/tests.gbaa"
::RIF_INCLUDE "parts/data.gbaa"
```

Las rutas son relativas al archivo que contiene la directiva, se admiten
includes anidados, se rechaza salir de esa carpeta y los ciclos o una
profundidad excesiva fallan antes de ejecutar Rules.

`::RIF_CHECKSUM` se ejecuta después de Rules, de materializar STORE/PCP-I, de
resolver relocaciones y de aplicar patches. Pone en cero todos los campos de
checksum mientras calcula, por lo que el resultado no depende de sí mismo ni
de otro checksum:

```text
::RIF_CHECKSUM CRC32 IMAGE WRITE 0x1C
::RIF_CHECKSUM CRC16 SECTION rom WRITE 0x10
::RIF_CHECKSUM SUM8 IMAGE RANGE 0x100 0x200 WRITE 0x20
::RIF_CHECKSUM GBA_HEADER IMAGE WRITE 0xBD
```

`IMAGE` usa un offset absoluto dentro del archivo final. `SECTION` calcula solo
esa sección y usa un offset relativo a ella. `RANGE` usa offsets relativos al
ámbito seleccionado y su final es exclusivo. Sin `RANGE`, se usa todo el ámbito.
`CRC32` es IEEE CRC-32, `CRC16` es CRC-16/CCITT-FALSE y `SUM8` emite la suma
módulo 256. `GBA_HEADER` aplica la fórmula de complemento de GBA a los bytes
`0xA0..0xBC` y escribe un byte en `0xBD`. El resultado usa el endianness
configurado por el target. El destino debe caber dentro de la imagen emitida;
reserva sus bytes con una Rule, `RIF_INSERT`, STORE o PCP-I.

## Línea de comandos

```powershell
vnma run main.py main.rif program.asm
vnma run main.py main.pack program.asm
vnma run main.py main.rif program.asm -o build/program.bin
```

`main.py` es la entrada canónica. Si la raíz del repositorio está en `PATH`,
`rif.cmd` puede usarse como atajo y reenvía la misma operación a VNMA.

La extensión debe coincidir con `extension` en `@block linker`. Sin `-o`, la salida usa la
misma ruta del MIR con extensión `.bin`.

## API directa

```python
from MIR import compile_mir_source

result = compile_mir_source("main.rif", "mov rax\n")
binary_data = result.binary
```

Para reutilizar el target:

```python
from MIR import compile_mir_source, prepare_target

target = prepare_target("main.pack")
first = compile_mir_source(target, "mov rax\n")
second = compile_mir_source(target, "add rbx\n")
```

Para archivo o tokens ya producidos por otro compilador:

```python
from MIR import compile_mir_file, compile_mir_tokens, tokenize_mir

result = compile_mir_file("main.rif", "program.asm")
tokens = tokenize_mir("mov rax\n", "generated.asm")
result = compile_mir_tokens("main.pack", tokens)
```

`compile_mir_tokens` evita volver a tokenizar y parsear el MIR.

## Secciones

La sección predeterminada es `default`. Una API directa puede elegir otra
sección configurada:

```python
result = compile_mir_source(target, source, section="text")
```

`MIRCompilation` expone `binary`, `image`, `executions`, `program`, `context`,
`section_binary`, `symbols` y el nombre de la sección seleccionada. `symbols`
contiene las direcciones virtuales absolutas de los símbolos definidos por
`mark` durante la compilación. `compile_mir` acepta texto o un iterable de
tokens.

Las Rules pueden registrar relocaciones con `fixup pc8`, `fixup pc16`,
`fixup pc32`, `fixup pc64`, `fixup abs8`, `fixup abs16`, `fixup abs32` o
`fixup abs64`. El target también puede declarar clases adicionales en
`@block relocations`; el runtime las resuelve después de todas las líneas MIR
y antes de aplicar `::RIF_PATCH`.

La directiva `::RIF_SECTION nombre` selecciona otra sección de la misma
`AssemblyImage` y conserva los emisores, símbolos y relocaciones de cada una.

También está disponible el pipeline de bajo nivel:

```python
from MIR import compile_definition, compile_project, execute_rule

program = compile_definition("main.rif")
project = compile_project("main.rif")
execution = execute_rule(project, "mov", tokens)
```

`parse_source` expone el parseo de Gram y `compile_source` devuelve el target
resuelto sin crear una imagen de salida.
