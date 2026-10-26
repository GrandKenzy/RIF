# 01. Introduction

This section explains what RIF compiles, how its representations are kept
separate, and how to install a project that uses Gram as its local parser
dependency.

| Guide | Summary |
| :--- | :--- |
| [01. What is RIF?](./01-what-is-rif.md) | RIF's purpose, terminology, and processing model. |
| [02. Installation](./02-installation.md) | VNMA setup and the expected project layout. |
| [03. Architecture](./03-architecture.md) | The path from source definition to pure binary output. |

## The Three Main Representations

1. **RIF definition:** `main.rif` or a precompiled `main.pack`. It describes
   the target language and its Rules.
2. **Compiled Rule Set:** RIF's internal representation of resolved Rules,
   tokens, tables, and references.
3. **External MIR:** the user program consumed by the Rules, such as
   `program.asm`.

The external MIR is not the same object as the compiled Rule Set. Keeping this
boundary makes it possible to compile one target definition against many MIR
inputs.
