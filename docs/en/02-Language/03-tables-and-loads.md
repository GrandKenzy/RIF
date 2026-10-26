# Tables and Loads

Tables are declared as a header row, separator row, and one or more data rows.
They are materialized as a matrix while keeping a constant-time column map.

```rif
@table registers
| name | opcode | bits |
________________________
| mov  | 1      | 32   |
________________________
| add  | 2      | 32   |
@end
```

The underscore separator may contain any number of `_` characters. A separator
is required between rows, and each row must end with `|` before its newline.

## Table Access

The selected row can provide a value to an instruction:

```rif
-> $registers.name, IDENT
-> put $registers.opcode 0000
```

The first form matches the current token against the `name` column and selects
that row. Later accesses to `$registers.bits` read from the selected row.

Static indexed access selects a row without consuming a MIR token:

```rif
-> fits $registers.name[rax].bits
```

The selector column must have unique values when it is used as an index. Other
columns may contain duplicates. The index is built lazily on first use, so a
large table does not pay to index columns that are never queried.

## Loading Additional Sources

`@LOAD` includes another `.rif` source relative to the current source:

```rif
@LOAD "tables.rif"
@LOAD "rules.rif"
```

The loader requires the `.rif` extension, resolves paths canonically, detects
cycles, and preserves declaration scope. A loaded file can contain tables and
Rules, but it cannot redefine root configuration or linker settings.

## Tables in Packages

When a `.pack` is created, loaded source files are recorded in the package
manifest and their dependency order is resolved ahead of execution. Precompiled
packages store table rows in SQLite. The runtime recreates the matrix and lazy
indexes when the package is opened.
