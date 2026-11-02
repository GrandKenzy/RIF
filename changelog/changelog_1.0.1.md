# RIF 1.0.1

## RIF Frontend

RIF opcodes, keywords, token names, and syntax operations can no longer be
shadowed by Rules, tables, generic blocks, definitions, or variants. Names are
checked case-insensitively, while target-specific names such as `move` remain
available.

## STORE

STORE version 2 now supports inline hexadecimal binary blocks with
`@BINARY LABEL` and `@END`. The block stores all declared bytes as one opaque
payload, accepts optional commas and `0x` prefixes, and does not invoke media
plugins.
