; Linux x86-64 raw machine code source.
; Equivalent to: exit(42)
mov rax, 60
mov rdi, 42
syscall
