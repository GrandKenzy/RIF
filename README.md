# RIF (Retargetable ISA Foundry)

> **Versión:** `1.0.0`  
> **Runtime:** Python 3.10+  
> **Dependencias:** [Gram](https://github.com/GrandKenzy/Gram)

**RIF (Retargetable ISA Foundry)** es un framework retargetable para describir conjuntos de instrucciones (ISAs), formatos de ensamblador y layouts binarios arbitrarios. A partir de una especificación `.rif`, RIF procesa instrucciones de un programa MIR externo (ya sea desde archivo o como stream de tokens) y emite binario puro de alta fidelidad.

---

## Características principales

- **Control a nivel de bit:** Emisión precisa mediante buffers direccionables bit a bit (`BitBuffer`, `BitEmitter`), soportando instrucciones de longitud variable, campos no alineados a byte y directivas como `put`, `ebit`, `emmit` y `emitfr`.
- **Compilador y Runtime desacoplados:**
  - **Frontend:** Tokeniza y analiza gramaticalmente las definiciones `.rif` con [Gram](https://github.com/GrandKenzy/Gram), resolviendo tablas, directivas de linker y reglas en un `CompiledRuleSet`.
  - **Runtime (`RIFMachine`):** Despacha y ejecuta las reglas sobre el MIR externo para ensamblar el binario final.
- **Paquetes reproducibles (`.pack`):** Empaqueta fuentes RIF, tablas, dependencias y assets en un archivo ZIP reproducible con opción de precompilación SQLite para tiempos de carga casi instantáneos.
- **Soporte de Variantes de ISA:** Soporte de dialectos o modos de instrucción (p. ej. ARM / Thumb) mediante `@SUPPORTS` y `@ASMVARIANT`, manteniendo un contexto global compartido.
- **Preámbulos y parches finales:** Bloques `@insert` para cabeceras y plantillas binarias (como headers ELF/PE) y `@before` con `.rplc` para parches y cálculo de offsets antes de entregar la imagen.
- **Interoperabilidad con Python:** Funciones dinámicas y consultas complejas vía `#call[...]` conectadas con módulos `funcs.py`.

---

## Flujo de trabajo

```text
Definición RIF (main.rif / target.pack)
                  │
                  ▼
         Frontend (Gram parser)
                  │
                  ▼
           CompiledRuleSet
                  │
                  ├────────◄ Programa MIR externo (.asm o tokens)
                  ▼
         Runtime (RIFMachine)
                  │
                  ▼
             program.bin
```

---

## Uso rápido

### 1. Requisitos e instalación

RIF utiliza **Gram** como motor léxico y sintáctico. Puedes gestionarlo con VNMA:

```powershell
vnma install
vnma sync-ide
```

### 2. Uso desde la línea de comandos (`rif`)

El CLI `rif` permite compilar programas ensamblador directamente o crear paquetes `.pack`:

```powershell
# Compilar directamente una definición .rif con un programa ensamblador
python rif.py main.rif program.asm -o program.bin

# Crear un paquete portable .pack precompilado
python rif.py --pack main.rif -o amd64.pack

# Compilar un programa usando el paquete generado
python rif.py amd64.pack program.asm -o program.bin
```

### 3. Uso desde Python

```python
from MIR import compile_mir_file, compile_mir_tokens, prepare_target

# Compilación directa desde archivo
compile_mir_file("amd64.pack", "program.asm", output="program.bin")

# O en memoria usando tokens directos de tu propio compilador
target = prepare_target("amd64.pack")
compile_mir_tokens(target, tokens, output="program.bin")
```

---

## Documentación

La documentación completa del proyecto está disponible en español e inglés:

* 🇪🇸 **[Documentación en Español](docs/es/index.md)**
  * [01. Introducción](docs/es/01-Introduccion/index.md) (Qué es RIF, Instalación, Arquitectura)
  * [02. Lenguaje](docs/es/02-Lenguaje/index.md) (Estructura, Configuración, Tablas, Rules y Valores)
  * [03. Compilación](docs/es/03-Compilacion/index.md) (MIR externo, Paquetes `.pack`, Funciones Python)
  * [04. Ejecución](docs/es/04-Ejecucion/index.md) (Memoria de bits, Datastack, Variantes, Trazas e Inserts/Parches)
* 🇬🇧 **[English Documentation](docs/en/index.md)**
  * [01. Introduction](docs/en/01-Introduction/index.md)
  * [02. Language](docs/en/02-Language/index.md)
  * [03. Compilation](docs/en/03-Compilation/index.md)
  * [04. Execution](docs/en/04-Execution/index.md)
* 🏛️ **[Especificación de Arquitectura](ARCHITECTURE.md)**: Nomenclatura y capas de separación.
* 📦 **[Ejemplos funcionales](examples/README.md)**: Targets reales para AMD64 y ELF64.
* 📝 **[Registro de Cambios](changelog/README.md)**: Historial de versiones y notas de la versión `1.0.0`.
