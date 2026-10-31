# MIR externo

El MIR externo es un programa lineal cuyo primer token selecciona una Rule:

```text
mov rax, 1
add rbx, 2
```

Los tokens restantes son consumidos por la Rule. Si una línea deja tokens sin
consumir, la compilación falla.

## Línea de comandos

```powershell
rif main.rif program.asm
rif main.pack program.asm
rif main.rif program.asm -o build/program.bin
```

La extensión debe coincidir con `ext` en `@block linker`. Sin `-o`, la salida usa la
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

La sección predeterminada es `entrysection`. Una API directa puede elegir otra
sección configurada:

```python
result = compile_mir_source(target, source, section="text")
```

`MIRCompilation` expone `binary`, `image`, `executions`, `program`, `context`,
`section_binary` y el nombre de la sección seleccionada. `compile_mir` acepta texto o un
iterable de tokens.

También está disponible el pipeline de bajo nivel:

```python
from MIR import compile_definition, compile_project, execute_rule

program = compile_definition("main.rif")
project = compile_project("main.rif")
execution = execute_rule(project, "mov", tokens)
```

`parse_source` expone el parseo de Gram y `compile_source` devuelve el target
resuelto sin crear una imagen de salida.
