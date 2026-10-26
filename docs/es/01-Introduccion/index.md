# 01. Introducción

Esta sección explica qué compila RIF, cómo separa sus representaciones y cómo
instalar un proyecto que usa Gram como dependencia local.

| Guía | Resumen |
| :--- | :--- |
| [01. Qué es RIF](./01-que-es-rif.md) | Propósito, términos y modelo de procesamiento. |
| [02. Instalación](./02-instalacion.md) | Configuración con VNMA y estructura esperada. |
| [03. Arquitectura](./03-arquitectura.md) | Camino desde la definición hasta el binario puro. |

## Las tres representaciones principales

1. **Definición RIF:** `main.rif` o `main.pack`; describe el target y sus Rules.
2. **Compiled Rule Set:** representación interna con Rules, tokens, tablas y
   referencias resueltas.
3. **MIR externo:** programa consumido por las Rules, por ejemplo
   `program.asm`.

El MIR externo no es el Compiled Rule Set. Esta separación permite reutilizar
un target para compilar muchos programas MIR.
