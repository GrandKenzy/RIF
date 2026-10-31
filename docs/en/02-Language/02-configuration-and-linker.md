# Configuration and Linker

The `@block config` block describes the output format. The `@block linker` block describes
the external MIR input.

## Configuration

```rif
@block config:
sectiondef ".section"
make section "data"
make section "text"
make section "bss"
sectionend ":"
entrysection "text"
entrylabel "_start"
comment ";"
labelend ":"
datasection "data"
defaultsection "text"
sectionflags "text" "rx"
sectionalign "text" 4
sectionvaddr "text" 4194304
wordsize 32
addresssize 32
endianness "little"
casesensitive true
symbolprefix "_"
localprefix "."
undefinedsymbols "error"
duplicatesymbols "error"
strict true
allowemptysections false
bitorder "msb"
@end
```

Required directives are:

| Directive | Meaning |
| :--- | :--- |
| `sectiondef` | Prefix used to render an output section. |
| `make section` | Adds a valid output section. Repeatable. |
| `sectionend` | Terminates a rendered section header. |
| `entrysection` | Section receiving the default MIR output. |
| `entrylabel` | Entry label rendered for the entry section. |
| `comment` | Comment marker for rendered output. |
| `labelend` | Label terminator. |
| `datasection` | Section used for data symbols. |
| `defaultsection` | Section selected when no section is supplied. |
| `wordsize` | Width used by `emmit`, in bits. |
| `addresssize` | Target address width, in bits. |
| `endianness` | `"little"` or `"big"`. |
| `casesensitive` | Controls case matching for external Rule names. |
| `symbolprefix` | Prefix for rendered symbols. |
| `localprefix` | Prefix for local symbols. |
| `undefinedsymbols` | `error`, `warn`, or `ignore`. |
| `duplicatesymbols` | `error`, `warn`, or `ignore`. |
| `strict` | Enables strict target policy. |
| `allowemptysections` | Controls empty section rendering. |

Optional section directives are `sectionflags`, `sectionalign`,
`sectionvaddr`, and `bitorder`. `sectionalign` controls physical and
automatic virtual alignment in bytes; `sectionvaddr` assigns an explicit
virtual base to a section. `bitorder` accepts `"msb"` or `"lsb"`.

## Linker

```rif
@block linker:
ext ".asm"
name "main"
searching ""
@end
```

`ext` is the accepted external MIR extension. `name` identifies the main
source name. `searching` controls automatic file discovery used by linker
features and variants:

- `""` searches beside the main file.
- A folder string searches below that folder.
- `false` disables automatic searching.

The linker configuration is target metadata; it does not itself compile the
MIR. The external compiler API validates the MIR extension before processing.
