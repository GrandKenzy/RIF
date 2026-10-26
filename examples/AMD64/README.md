# AMD64 example

This example uses RIF to encode a small Linux x86-64 program as a pure raw
binary. The external MIR source is intentionally close to assembly:

```text
mov rax, 60
mov rdi, 42
syscall
```

The resulting machine code is:

```text
48 C7 C0 3C 00 00 00 48 C7 C7 2A 00 00 00 0F 05
```

It is the AMD64 Linux sequence for `sys_exit(42)`:

```asm
mov rax, 60
mov rdi, 42
syscall
```

## Compile

From the repository root:

```powershell
vnma run rif.py examples/AMD64/main.rif examples/AMD64/main.asm `
  -o examples/AMD64/exit.bin
```

The output is a raw binary, not an ELF executable. It can be inspected with:

```powershell
Format-Hex examples/AMD64/exit.bin
```

The same target can be precompiled as a package. The package resolves the
RIF sources before the MIR is processed:

```powershell
vnma run rif.py --pack examples/AMD64/main.rif `
  -o examples/AMD64/amd64.pack
vnma run rif.py examples/AMD64/amd64.pack examples/AMD64/main.asm `
  -o examples/AMD64/exit-from-pack.bin
```

`exit.bin` and `exit-from-pack.bin` must be identical.

The current `mov` rule supports the eight legacy AMD64 general-purpose
registers (`rax` through `rdi`) and unsigned 32-bit immediates. Register
extensions (`r8` through `r15`), labels, relocations, and ELF packaging are
deliberately outside this first example.

## Expected result

The output must contain 16 bytes, in this order:

```text
48 c7 c0 3c 00 00 00 48 c7 c7 2a 00 00 00 0f 05
```

The `fits 32` instruction consumes the immediate from the MIR line and emits
it as a four-byte little-endian field. The table selects the correct ModRM
byte for the register without hard-coding eight separate rules.
