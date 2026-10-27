# RIF 1.0.1 · Security hardening and resource controls

## Security

- Restricted `@LOAD`, `.file`, `.searching`, and packaged paths to relative
  locations bounded by the project or package root.
- Prevented package execution from using the creator machine's absolute paths.
  Absolute origins are retained only as diagnostic metadata and are excluded
  from content hashes and resolution.
- Added validation for symlinks, package members, compressed-size ratios, and
  declared package contents before execution.
- Kept `funcs.py` explicitly as trusted Python code; this release does not
  claim to sandbox it.

## Resource limits

- Added configurable MiB limits through `--plimit N`, with precedence from the
  command line, process environment, `.env`, and built-in defaults.
- Applied the effective limit to RIF sources, MIR input, assets, package
  contents, binary output, field widths, dynamic operations, and temporary
  conversion buffers.
- Added early rejection before reading oversized files, creating oversized
  packages, or evaluating unbounded widths.

## Concurrency and correctness

- Serialized the RIF compilation phase with a reentrant lock so Gram's global
  registries and `Frontend.globals` cannot mix simultaneous compilations.
- Kept compiled runtime machines and their buffers independent, allowing
  execution after compilation to remain concurrent.
- Preserved origin-independent package fingerprints and validated package
  metadata before loading compiled databases or assets.

## Performance

- Deduplicated real paths while collecting project files and avoided repeated
  conversions for aligned binary data.
- Added a bulk byte-append path for aligned output and reduced unnecessary
  temporary buffers during artifact processing.

## Verification

- Added hardening tests for resource-limit precedence, path traversal,
  package origins, and concurrent Gram compilations.
- `vnma test` passes all 114 tests.
- `python -m compileall -q .`, `vnma run rif.py ...`, and direct
  `python rif.py ...` execution were verified.
