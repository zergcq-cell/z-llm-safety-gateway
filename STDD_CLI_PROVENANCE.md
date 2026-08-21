# Vendored STDD CLI provenance

The repository vendors the STDD command-line implementation required by its development process.

- Upstream: `https://github.com/leonai42/stdd`
- Upstream tag: `v2.9.5`
- Pinned commit: `fd9df3104d3588eb145cc84ec551c1803e783c9e`
- Commit date: `2026-06-28T12:39:45+08:00`
- Imported paths: `bin/stdd`, `stdd/`
- Integrity manifest: `stdd-v2.9.5.sha256`
- License: MIT; preserved in `stdd/UPSTREAM_LICENSE`

The imported upstream files are kept byte-for-byte identical to the pinned commit. Project-specific
backfill behavior lives in `tools/stdd_backfill.py` and is not represented as upstream code.

The project intentionally does not auto-upgrade this toolchain. A later STDD change must review and
test any version upgrade, especially a migration across the v2/v3 boundary.
