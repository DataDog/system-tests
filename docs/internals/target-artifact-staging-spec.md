# Target artifact staging

Target artifact staging resolves a test target to bounded, inspectable entries in
`binaries/` before a build consumes them. The first migration covers Python; other
targets continue to use `utils/scripts/load-binary.sh` until migrated separately.

## Contract

Each migrated target provides `utils/build/docker/<target>/artifact.py` with `Dev`
and `Prod` implementations. They declare resolver inputs and map the resolved values
to text entries without performing network or filesystem side effects themselves.

The shared orchestrator owns external lookups and writes the generated entries. It
also maintains `binaries/.target-artifacts-manifest.json`, which records the owner
and content hash of every generated file. Staging:

- verifies that previously generated entries still match their recorded hashes;
- refreshes entries previously owned by the same target;
- removes stale entries owned by that target;
- preserves entries owned by other targets; and
- refuses to overwrite unowned files, changed generated entries, symlinks, conflicting
  selectors, or entries owned by another target.

Selectors should be bounded, such as a commit SHA, release tag, package version, or
OCI digest. If an installer must consume a mutable provider selector, the target must
also emit a bounded selection marker with `provider_fetch_entries`.

The `custom` environment does not resolve or create selectors because an upstream or
local artifact bundle is already the source of truth. It removes unchanged generated
selectors previously owned by the target so they cannot override that custom payload.

## Commands

The canonical entry point is:

```bash
python3 utils/scripts/stage-target-artifacts.py <target> <dev|prod|custom>
```

During migration, the existing compatibility command delegates migrated targets to
the same implementation:

```bash
./utils/scripts/load-binary.sh <target> <dev|prod|custom>
```

## Python demonstration

For `python dev`, the configured `LIBRARY_TARGET_BRANCH` (default: `main`) resolves
to a commit SHA and produces `python-load-from-s3`. For `python prod`, the latest
published `ddtrace` package version produces `python-load-from-pip`. Existing Python
installer behavior consumes both files, so no installer change is needed.

## Adding a target

1. Add the target's `artifact.py` with `Dev` and `Prod` implementations.
2. Reuse shared resolvers, or add a resolver with isolated unit coverage.
3. Emit text entries only; keep payload downloads in existing build/install steps.
4. Preserve local payload overrides and add public-contract tests for the target.
5. Route only that target through the compatibility loader.

GitLab job integration and Buildx remote caching are intentionally handled in later
changes after target migrations are reviewed.
