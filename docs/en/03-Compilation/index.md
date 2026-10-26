# 03. Compilation

RIF exposes a command-line workflow and a direct Python API. Both compile the
same target definition and use the same MIR dispatcher.

| Guide | Summary |
| :--- | :--- |
| [01. External MIR](./01-external-mir.md) | CLI and direct API compilation of MIR files or token streams. |
| [02. RIF Packages](./02-rif-packages.md) | `.pack` contents, precompilation, and package advantages. |
| [03. Python Functions](./03-python-functions.md) | The `funcs.py` handler contract and runtime context. |

## Two Compilation Stages

```text
Stage 1: main.rif or main.pack -> CompiledRuleSet
Stage 2: CompiledRuleSet + external MIR -> pure binary
```

Stage 1 resolves the target. Stage 2 runs Rules against the input MIR. A
precompiled `.pack` combines most of Stage 1 into a portable artifact.
