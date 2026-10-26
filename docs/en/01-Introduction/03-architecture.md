# Architecture

RIF has two input phases and one output phase.

## Target Definition

`main.rif` describes the target:

```text
main.rif -> CompiledRuleSet
```

The compiled Rule Set contains resolved instruction operands and references to
tokens, tables, and other Rules. It is reused for every external MIR program
compiled against the target.

## External MIR

The external MIR is the program that the target consumes:

```text
CompiledRuleSet + program.asm -> program.bin
```

Its first token on each line selects a Rule. The remaining tokens are passed to
that Rule. RIF can tokenize the file itself or receive tokens from another
compiler through the direct Python API.

## Internal Components

| Component | Responsibility |
| :--- | :--- |
| `Frontend.syntax` | Declares the Gram grammar for RIF definitions. |
| `Frontend.processor` | Materializes configuration, tables, defines, Rules, and loads. |
| `MIR.compiler` | Converts parsed instruction nodes into flat internal instructions. |
| `MIR.semantic` | Resolves token, table, Rule, and reservation references. |
| `MIR.runtime.RIFMachine` | Executes instructions against MIR tokens. |
| `MIR.bitbuffer.BitBuffer` | Stores and rewrites arbitrary bit ranges. |
| `MIR.output.AssemblyImage` | Owns one output buffer per configured section. |
| `pack.py` | Creates and validates reproducible `.pack` archives. |

## State Ownership

The root target owns global definitions, tables, configuration, and Rules.
`RIFMachine` owns execution state such as token position, saved tokens,
selected rows, datastack values, reservations, and traces. A machine can be
created for a section of an `AssemblyImage` without changing the target
definition.
