# Mapa del proyecto

Guía de orientación, no sustituto del código. Consulta solo las secciones
relevantes y verifica el comportamiento en los archivos y pruebas. Actualiza
este mapa cuando cambien responsabilidades o conexiones principales.

## Flujo de compilación

`rif.py` recibe una definición `.rif` o `.pack` y delega en `MIR/pipeline.py`.
El pipeline tokeniza con Gram, procesa los nodos mediante
`Frontend/processor/`, captura el estado en `Frontend/globals.py`, resuelve
Rules y construye un `CompiledRuleSet`. El runtime `MIR/runtime.py` ejecuta
las Rules sobre `BitBuffer`/`BitEmitter`; `MIR/output.py` y `MIR/artifacts.py`
construyen imágenes, inserts y parches finales.

Para PCP-I, `rif.py --comp-pcpi` usa `pcpi_compiler.py`: compila una fuente
`.pci` con la misma gramática de RIF, ejecuta la Rule de entrada y serializa el
resultado con `pcpi.py`. PCP-I es una salida especializada; no añade una
segunda gramática al frontend.

## Bloques genéricos

La única sintaxis de bloques es:

```rif
@block nombre:
campo valor "opcional"
@end
```

`Frontend/syntax/items/blocks.py` conserva el cuerpo sin imponer semántica.
`Frontend/processor/visitors/block.py` normaliza cada línea a
`BlockEntryData` con cero, uno o dos valores y registra `BlockData` en el
contexto. `config` y `linker` se materializan directamente desde sus visitors;
otros nombres se preservan en `TargetContext.blocks` para consumidores
especializados. No se mantienen `@config`, `@linker`, terminadores dedicados,
ni prefijos de punto como aliases.

## Directorios y archivos

- `rif.py`: CLI para compilar definiciones, ejecutar MIR y producir PCP-I.
- `Frontend/syntax/`: sesión Gram, keywords y reglas de entrada; `blocks.py`
  contiene el bloque genérico.
- `Frontend/processor/`: orden de pasadas y visitors para config, linker,
  tablas, Rules, variantes, inserts y bloques.
- `Frontend/globals.py`: dataclasses y estado temporal de frontend; el estado
  se copia a `TargetContext` para que programas compilados sean independientes.
- `MIR/pipeline.py`: reseteo de contexto, parseo, procesamiento y compilación.
  `MIR/compiled.py` serializa contextos y programas en bases SQLite de packs.
- `MIR/runtime.py`, `MIR/emitter.py`, `MIR/bitbuffer.py` y `MIR/output.py`:
  ejecución de Rules, emisión bit a bit y layout de secciones.
- `MIR/external.py`: consumo de entradas MIR externas y validación del linker.
- `pcpi.py` y `pcpi_compiler.py`: formato PCP-I y adaptación de fuentes `.pci`.
- `pack.py`: creación y lectura segura de paquetes `.pack`.
- `tests/`: pruebas rápidas de parser, semántica, runtime, packs y PCP-I.
  `examples/`: targets AMD64 y ELF64 que documentan usos completos.
- `docs/en/` y `docs/es/`: documentación del lenguaje, compilación y memoria.
  `changelog/`: notas versionadas de cambios importantes.

## Dónde empezar según el cambio

| Área | Código principal | Pruebas relacionadas |
| --- | --- | --- |
| Sintaxis de bloques | `Frontend/syntax/items/blocks.py`, `Frontend/syntax/__init__.py` | `tests/test_blocks.py`, `tests/test_declarations.py` |
| Semántica config/linker | `Frontend/processor/visitors/config.py`, `linker.py` | `tests/test_processor.py`, `tests/test_pipeline.py`, `tests/test_variants.py` |
| Reglas y valores | `Frontend/syntax/items/declarations.py`, `Frontend/processor/visitors/rule.py`, `MIR/` | `tests/test_runtime.py`, `tests/test_mir.py` |
| Packs y serialización | `pack.py`, `MIR/compiled.py` | `tests/test_pack.py`, `tests/test_blocks.py` |
| PCP-I | `pcpi.py`, `pcpi_compiler.py`, `rif.py` | `tests/test_pcpi.py` |
| Inserts y parches | `Frontend/processor/visitors/artifacts.py`, `MIR/artifacts.py` | `tests/test_artifacts.py` |

Una característica puede cruzar gramática, semántica, contexto serializado y
backend. Sigue ese recorrido antes de modificar una sola capa.

## Herramientas y pruebas

- `vnma run rif.py ...` ejecuta la CLI del proyecto.
- `vnma test` ejecuta la suite rápida; `vnma test tests/<archivo>` permite una
  comprobación enfocada.
- Los `.pack`, binarios y logs generados no son puntos de partida para cambios
  de código. Conserva `.vscode/` y cualquier artefacto local no relacionado.
