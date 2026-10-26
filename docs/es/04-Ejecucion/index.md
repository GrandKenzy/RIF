# 04. Ejecución

La ejecución corre Rules resueltas contra tokens MIR y escribe en una imagen de
salida organizada por secciones y direccionable por bits.

| Guía | Resumen |
| :--- | :--- |
| [01. Memoria de bits](./01-memoria-de-bits.md) | Emisión, posiciones, reservas y reescrituras. |
| [02. Datastack](./02-datastack.md) | Valores temporales y anchos provenientes de tablas. |
| [03. Variantes](./03-variantes.md) | Carga y delegación a variantes ISA. |
| [04. Diagnóstico y pruebas](./04-diagnostico-y-pruebas.md) | Errores, trazas y verificación. |
| [05. Inserts y parches](./05-inserts-y-parches.md) | Payloads, queries nativas y layout físico/virtual. |

`RIFMachine` ejecuta un `CompiledRuleSet`; `BitEmitter` escribe mediante
`BitBuffer` y `AssemblyImage` conserva un buffer por sección.
