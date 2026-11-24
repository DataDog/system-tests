"""Check ./lock/*.json against the system-tests checkout; fail with "regenerate the lock" on drift.

Run with the runner's Python, from the checkout:

    python check.py <lock dir> <path to scenario_images.py>

Compares, without network:
  - the images each locked scenario asks for (system-tests' own scenario definitions);
  - each locked image's digest with mirror_images.lock.yaml's;
  - requirements.txt with the one the runner lock was resolved from;
  - each weblog's base image (resolved like build.sh does) and its Dockerfile's `pip install` pins.
"""

import hashlib
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path

import yaml


def sha256(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main() -> None:
    lock_dir, scenario_images = Path(sys.argv[1]), sys.argv[2]
    errors: list[str] = []

    runner = json.loads((lock_dir / "runner.json").read_text())
    if runner["requirementsSha256"] != sha256("requirements.txt"):
        errors.append("requirements.txt changed (lock.py runner)")

    images = json.loads((lock_dir / "images.json").read_text())
    scenarios = images["scenarios"]
    weblogs = sorted({v for s in scenarios.values() for v in s})
    args = [*scenarios, *[a for v in weblogs for a in ("--weblog", f"python:{v}")]]
    current = json.loads(subprocess.run([sys.executable, "-I", scenario_images, *args], check=True, text=True, stdout=subprocess.PIPE).stdout)
    for scenario, variants in scenarios.items():
        for variant, locked in variants.items():
            now = current[scenario][variant]
            if now != locked:
                errors.append(
                    f"{scenario} on {variant} uses {now}, the lock has {locked} (lock.py images)"
                )

    mirror = yaml.safe_load(Path("mirror_images.lock.yaml").read_text())["images"]
    for ref, entry in images["images"].items():
        digest = mirror.get(ref, {}).get("digest")
        if digest != entry["digest"]:
            errors.append(f"{ref}: mirror_images.lock.yaml has {digest}, the lock {entry['digest']} (lock.py images)")

    for path in sorted(lock_dir.glob("weblog-*.json")):
        weblog = json.loads(path.read_text())
        dockerfile = f"utils/build/docker/python/{weblog['variant']}.Dockerfile"
        contexts = subprocess.run(
            [sys.executable, "-I", "utils/scripts/resolve-base-images-contexts.py", "--build-contexts", dockerfile],
            check=True, text=True, stdout=subprocess.PIPE,
        ).stdout.split()  # fmt: skip
        expected = [f"{weblog['baseAlias']}=docker-image://{weblog['baseImage']}"]
        if contexts != expected:
            errors.append(f"{dockerfile}: base image context {contexts}, the lock has {expected} (lock.py weblog)")
        pins = []
        for line in Path(dockerfile).read_text().splitlines():
            m = re.match(r"^\s*RUN\s+pip\s+install\s+(.+)$", line)
            if m:
                pins += [a for a in shlex.split(m.group(1)) if not a.startswith("-")]
        if pins != weblog["pipInstalls"]:
            errors.append(f"{dockerfile}: pip installs {pins}, the lock has {weblog['pipInstalls']} (lock.py weblog)")
        if sha256("utils/build/docker/python/install_ddtrace.sh") != weblog["installDdtraceSha256"]:
            errors.append("install_ddtrace.sh changed: check it still installs binaries/python-load-from-pip (lock.py weblog)")

    if errors:
        print("system-tests drifted from nix/system-tests-vanilla/lock; regenerate the lock:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        print("  nix run .#system-tests-vanilla-lock", file=sys.stderr)
        sys.exit(1)
    print("locks match system-tests")


if __name__ == "__main__":
    main()
