# RIF · Changelog

<p align="center">
  <strong>Versioned release notes for RIF</strong><br>
  Retargetable definitions, MIR compilation, bit memory, and target packages.
</p>

---

## Current release

### [`1.0.0`](changelog_1.0.0.md) · Initial stable release

RIF `1.0.0` provides the complete definition-to-binary pipeline, including
external MIR compilation, bit-addressable output, target packages, tables,
variants, Python functions, and independent physical and virtual memory state.

## Release timeline

| Version | Date | Main focus | Notes |
| --- | --- | --- | --- |
| [`1.0.0`](changelog_1.0.0.md) | 2026-10-26 | Complete RIF compilation pipeline | Current |

## How to read these notes

Each release has a `changelog_*.md` file. Entries are grouped by impact:

- **Added:** new public capabilities and language constructs.
- **Changed:** modifications to existing behavior.
- **Fixed:** corrected bugs and regressions.
- **Documentation:** synchronized English and Spanish guides.
- **Verification:** tests, stress runs, and compatibility checks.

Keep the version in the changelog filename, heading, and `vnma.toml` metadata
synchronized when preparing a release.
