# Source Structure

The root file is conventionally named `main.rif`. It may declare target-wide
objects in any order; the processor registers configuration, linker settings,
defines, and supports before resolving tables and Rules.

## Comments and Newlines

```rif
; This is a RIF comment.
@define mov ; comments can follow a declaration
```

Newlines are significant inside Rule bodies. There is no indentation grammar
for Rules, so these two forms have the same structural meaning:

```rif
@rule mov:
-> IDENT
-> emmit 1
```

## Root-Only Declarations

The root scope may contain `@config`, `@linker`, `@table`, `@stack`,
`@SUPPORTS`, `@ASMVARIANT`, `@define`, `@rule`, and `@LOAD`.

Included files loaded with `@LOAD` may contain only `@define`, `@table`,
`@rule`, and more `@LOAD` directives. Variant files loaded through
`@ASMVARIANT` may contain only `@define` and `@rule`.

This scope rule prevents a loaded file from silently replacing the target's
memory layout or linker policy.

## Generic blocks

The generic block form for declaring structured data is:

```rif
@block config:
sectiondef ".section"
make section "text"
wordsize 8
@end
```

Each line contains a name and zero, one, or two values before the newline. A
leading dot is also accepted (`.wordsize 8`) to ease migration from the legacy
directives. A line with more than two values is invalid.

`config` and `linker` blocks are translated into RIF's existing semantics.
Blocks with other names are preserved as structured data in
`program.context.blocks`, so specialized consumers can interpret them without
adding another parser rule.

## Definitions

`@define` registers a named language word:

```rif
@define mov
@define add
```

Definitions are labels in the RIF language. They do not allocate stack slots,
emit bits, or create runtime values.

## Rules

Rules are named instruction procedures:

```rif
@rule mov:
-> IDENT
-> put 0000 0000
```

An external MIR line beginning with `mov` dispatches to this Rule. The Rule
consumes tokens, emits fields, calls other Rules, and updates runtime state.

## Stack Declaration

The token stack is declared once:

```rif
@stack 50
```

It supports `save` and `load` for token-oriented control flow. It is separate
from the runtime `datastack`, which stores temporary values.
