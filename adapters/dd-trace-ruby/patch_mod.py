#!/usr/bin/env python3
"""Work around a Temper rust-backend codegen bug.

`temper build -b rust` emits the `impl TracerTrait for Tracer` newtype wrapper
(the `Tracer(Arc<dyn TracerTrait>)` forwarding shim) with the `start_span`
default-arg params double-wrapped in `Option`: it produces
`Option<Option<Arc<String>>>` where the `TracerTrait` trait method itself uses
`Option<Arc<String>>`. That mismatch makes the wrapper fail to satisfy the
trait, so the crate does not compile. This collapses the doubled `Option` back
to a single one in that one `start_span` signature.

Idempotent; run after `temper build -b rust`, before `cargo build`.
Exit nonzero if neither the bad nor the already-patched pattern is present.
"""
import sys

MOD = "temper.out/rust/system-tests-redux/src/mod.rs"

BAD = (
    "arg3: Option<Option<std::sync::Arc<String>>>, "
    "arg4: Option<Option<std::sync::Arc<String>>>, "
    "arg5: Option<Option<std::sync::Arc<String>>>"
)
GOOD = (
    "arg3: Option<std::sync::Arc<String>>, "
    "arg4: Option<std::sync::Arc<String>>, "
    "arg5: Option<std::sync::Arc<String>>"
)


def main() -> int:
    with open(MOD) as f:
        src = f.read()
    if BAD in src:
        src = src.replace(BAD, GOOD)
        with open(MOD, "w") as f:
            f.write(src)
        print("patch_mod: collapsed doubled Option in start_span wrapper")
        return 0
    if GOOD in src:
        print("patch_mod: already patched")
        return 0
    print(
        "patch_mod: ERROR neither the doubled-Option bug nor the patched "
        "signature found in " + MOD,
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    sys.exit(main())
