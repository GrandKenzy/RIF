# Installation

RIF is a local Python project that uses Gram from the sibling `Gram` project.
The repository's `vnma.toml` declares that dependency as an editable local
path:

```toml
[project]
name = "RIF"
version = "1.0.0"

[dependencies]
gram = { path = "~/Desktop/Gram", editable = true }
```

Install and synchronize the project environment with VNMA:

```powershell
vnma install
vnma sync-ide
```

Run the project entrypoint through VNMA:

```powershell
vnma run main.py
```

For development, the workspace normally contains:

```text
RIF/
├── Frontend/
│   ├── globals.py
│   ├── syntax/
│   └── processor/
├── MIR/
├── tests/
├── main.rif
├── main.py
├── rif.py
├── pack.py
└── vnma.toml
```

RIF imports Gram through the normal Python package name:

```python
from gram import config
from gram import lexer
```

The RIF syntax configures `;` as its comment token, preserves newline tokens,
and disables indentation support because Rule bodies use newlines as their
instruction delimiter.
