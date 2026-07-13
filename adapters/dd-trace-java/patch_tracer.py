#!/usr/bin/env python3
"""Work around a Temper java-backend codegen bug.

`temper build -b java` emits 2/3/4-arg `startSpan(...)` *calls* in the generated
suite (relying on the Temper default args `service=""`, `resource=""`,
`spanType=""`) but only the single 5-arg `startSpan` method on the generated
`Tracer` interface -- no default-arg overloads -- so the generated suite does
not compile (same class of bug as the Rust backend's default-param interface
methods). This injects the missing `default` overloads into the generated
Tracer.java, forwarding to the real 5-arg method with the Temper defaults.

Idempotent; run after `temper build -b java`, before `mvn install`.
"""
import re
import sys

TRACER = "temper.out/java/system-tests-redux/src/main/java/system_tests_redux/Tracer.java"

OVERLOADS = """    // [patched] Temper default-arg overloads for startSpan (see patch_tracer.py).
    default CapturedSpan startSpan(String name, String parentId) { return startSpan(name, parentId, "", "", ""); }
    default CapturedSpan startSpan(String name, String parentId, String service) { return startSpan(name, parentId, service, "", ""); }
    default CapturedSpan startSpan(String name, String parentId, String service, String resource) { return startSpan(name, parentId, service, resource, ""); }
"""

def main() -> int:
    with open(TRACER) as f:
        src = f.read()
    if "[patched] Temper default-arg overloads" in src:
        print("patch_tracer: already patched")
        return 0
    # Insert after the 5-arg startSpan declaration line.
    m = re.search(r"^\s*CapturedSpan startSpan\([^;]*\);\s*$", src, re.MULTILINE)
    if not m:
        print("patch_tracer: ERROR could not find the 5-arg startSpan declaration", file=sys.stderr)
        return 1
    out = src[:m.end()] + "\n" + OVERLOADS + src[m.end():]
    with open(TRACER, "w") as f:
        f.write(out)
    print("patch_tracer: injected startSpan default-arg overloads")
    return 0

if __name__ == "__main__":
    sys.exit(main())
