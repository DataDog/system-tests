"""Generate the locks of nix/system-tests-vanilla (see ./README section in the repo's README.md).

Network is used here, never at build or run time. Every lock pins content by hash, so the
derivations built from them are fixed-output fetches.

    lock.py runner  --system-tests ST --out lock/runner.json
        system-tests' requirements.txt resolved (uv) for the runner's Python on every platform the
        runner builds for, with the file (wheel, else sdist) chosen for each.
    lock.py images  --system-tests ST --python RUNNER_PYTHON --scenario S... --weblog L:V... \
                    --out lock/images.json
        scenario -> weblog -> images, from system-tests' own scenario definitions
        (./scenario_images.py), and image -> digest (system-tests' mirror_images.lock.yaml) ->
        dockerTools.pullImage hash per architecture.
    lock.py weblog  --system-tests ST --variant V --ddtrace-version X --out lock/weblog-V.json
        the wheelhouse the weblog's Dockerfile `pip install`s from: ddtrace==X (installed through
        binaries/python-load-from-pip) and the Dockerfile's own `RUN pip install` pins, resolved
        against what the base image already has, per architecture.
"""

import argparse
import hashlib
import json
import re
import shlex
import subprocess
import sys
import tempfile
import tomllib
from pathlib import Path

import yaml
from packaging.tags import Tag, compatible_tags, cpython_tags, mac_platforms
from packaging.utils import canonicalize_name, parse_wheel_filename

# requirements.txt entries left out of the runner: shellcheck-py has no wheel for aarch64-linux and
# its sdist downloads shellcheck while building. It is a linter; no test run imports it.
RUNNER_EXCLUDED = {"shellcheck-py"}
RUNNER_PYTHON = (3, 12)  # build.sh's `python3.12 -m venv venv`, runner.Dockerfile's python:3.12
# Nix system -> (uv --python-platform, tag platforms in preference order).
GLIBC_MAX = 40  # uv's newest manylinux target; nixpkgs' glibc is newer, so any of them loads


def manylinux(arch: str, glibc_max: int) -> list[str]:
    legacy = {17: "manylinux2014", 12: "manylinux2010", 5: "manylinux1"}
    out = []
    for minor in range(glibc_max, 4, -1):
        out.append(f"manylinux_2_{minor}_{arch}")
        if minor in legacy:
            out.append(f"{legacy[minor]}_{arch}")
    return [*out, f"linux_{arch}"]


RUNNER_PLATFORMS = {
    "x86_64-linux": ("x86_64-manylinux_2_40", manylinux("x86_64", GLIBC_MAX)),
    "aarch64-linux": ("aarch64-manylinux_2_40", manylinux("aarch64", GLIBC_MAX)),
    "aarch64-darwin": ("aarch64-apple-darwin", list(mac_platforms((14, 0), "arm64"))),
    "x86_64-darwin": ("x86_64-apple-darwin", list(mac_platforms((14, 0), "x86_64"))),
}
DOCKER_ARCHES = {"amd64": "x86_64", "arm64": "aarch64"}


def run(*cmd: str, **kwargs) -> str:
    print("+", shlex.join(cmd), file=sys.stderr)
    return subprocess.run(cmd, check=True, text=True, stdout=subprocess.PIPE, **kwargs).stdout


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")
    print(f"wrote {path}", file=sys.stderr)


def supported_tags(python: tuple[int, int], platforms: list[str]) -> list[Tag]:
    return [*cpython_tags(python, platforms=platforms), *compatible_tags(python, platforms=platforms)]


def uv_resolve(requirements: str, python: tuple[int, int], platform: str, constraints: str | None = None) -> list[dict]:
    """Resolve requirements with uv into pylock.toml packages."""
    with tempfile.TemporaryDirectory() as tmp:
        req = Path(tmp, "requirements.in")
        req.write_text(requirements)
        out = Path(tmp, "pylock.toml")
        cmd = [
            "uv", "pip", "compile", str(req), "--quiet", "--no-header", "--format", "pylock.toml",
            "--python-version", f"{python[0]}.{python[1]}", "--python-platform", platform,
            "--no-config", "--index-url", "https://pypi.org/simple", "-o", str(out),
        ]  # fmt: skip
        if constraints is not None:
            con = Path(tmp, "constraints.txt")
            con.write_text(constraints)
            cmd += ["-c", str(con)]
        run(*cmd)
        return tomllib.loads(out.read_text())["packages"]


def pick_file(package: dict, tags: list[Tag]) -> dict:
    """The best wheel for `tags`, else the sdist: {name, version, filename, url, sha256, kind}."""
    rank = {tag: i for i, tag in enumerate(tags)}
    best = None
    for wheel in package.get("wheels", []):
        filename = wheel["url"].rsplit("/", 1)[1]
        _, _, _, wheel_tags = parse_wheel_filename(filename)
        score = min((rank[t] for t in wheel_tags if t in rank), default=None)
        if score is not None and (best is None or score < best[0]):
            best = (score, wheel, filename, "wheel")
    if best is None:
        if "sdist" not in package:
            sys.exit(f"{package['name']} {package['version']}: no compatible wheel and no sdist")
        sdist = package["sdist"]
        best = (0, sdist, sdist["url"].rsplit("/", 1)[1], "sdist")
    _, file, filename, kind = best
    return {
        "name": package["name"],
        "version": package["version"],
        "filename": filename,
        "url": file["url"],
        "sha256": file["hashes"]["sha256"],
        "kind": kind,
    }


def cmd_runner(args) -> None:
    st = Path(args.system_tests)
    requirements = []
    for line in (st / "requirements.txt").read_text().splitlines():
        spec = line.split("#", 1)[0].strip()
        if spec and canonicalize_name(re.split(r"[=<>!~ ;\[]", spec, maxsplit=1)[0]) not in RUNNER_EXCLUDED:
            requirements.append(spec)
    platforms = {}
    for system, (uv_platform, tag_platforms) in RUNNER_PLATFORMS.items():
        tags = supported_tags(RUNNER_PYTHON, tag_platforms)
        packages = uv_resolve("\n".join(requirements) + "\n", RUNNER_PYTHON, uv_platform)
        platforms[system] = [pick_file(p, tags) for p in packages]
    write_json(
        Path(args.out),
        {
            "python": "%d.%d" % RUNNER_PYTHON,
            "requirementsSha256": sha256_file(st / "requirements.txt"),
            "excluded": sorted(RUNNER_EXCLUDED),
            "platforms": platforms,
        },
    )


def mirror_lock(st: Path) -> dict[str, dict]:
    return yaml.safe_load((st / "mirror_images.lock.yaml").read_text())["images"]


def image_arches(ref: str) -> dict[str, str]:
    """docker arch -> the platform's variant ('' if none), for the arches we build for."""
    manifest = json.loads(run("skopeo", "inspect", "--raw", f"docker://{ref}"))
    if "manifests" in manifest:
        arches = {}
        for m in manifest["manifests"]:
            p = m.get("platform", {})
            if p.get("os") == "linux" and p.get("architecture") in DOCKER_ARCHES:
                arches.setdefault(p["architecture"], p.get("variant", ""))
        return arches
    config = json.loads(run("skopeo", "inspect", "--config", f"docker://{ref}"))
    return {config["architecture"]: config.get("variant", "")}


def prefetch(name: str, tag: str, digest: str, arch: str) -> str:
    out = run(
        "nix-prefetch-docker", "--json", "--quiet", "--image-name", name, "--image-tag", tag,
        "--image-digest", digest, "--os", "linux", "--arch", arch,
    )  # fmt: skip
    return json.loads(out)["hash"]


def split_ref(ref: str) -> tuple[str, str]:
    name, _, tag = ref.rpartition(":")
    if not name or "/" in tag:
        return ref, "latest"
    return name, tag


def cmd_images(args) -> None:
    st = Path(args.system_tests)
    out = Path(args.out)
    previous = json.loads(out.read_text()) if out.exists() else {"images": {}}
    weblog_args = [a for w in args.weblog for a in ("--weblog", w)]
    scenarios = json.loads(
        run(args.python, "-I", str(Path(__file__).with_name("scenario_images.py")), *args.scenario, *weblog_args, cwd=st)
    )
    mirror = mirror_lock(st)
    images = {}
    for ref in sorted({i for weblogs in scenarios.values() for imgs in weblogs.values() for i in imgs}):
        if ref not in mirror:
            sys.exit(f"{ref} is not in system-tests' mirror_images.lock.yaml: no digest to pin it to")
        digest = mirror[ref]["digest"]
        old = previous["images"].get(ref)
        if old and old["digest"] == digest:
            images[ref] = old
            continue
        name, tag = split_ref(ref)
        arches = image_arches(f"{name}@{digest}")
        images[ref] = {
            "digest": digest,
            "hashes": {arch: prefetch(name, tag, digest, arch) for arch in sorted(arches)},
            "variants": {arch: v for arch, v in sorted(arches.items()) if v},
        }
    write_json(
        out,
        {
            "scenarios": scenarios,
            "images": images,
        },
    )


def dockerfile_pip_installs(dockerfile: Path) -> list[str]:
    """The requirement specs of the Dockerfile's `RUN pip install` lines."""
    specs = []
    for line in dockerfile.read_text().splitlines():
        m = re.match(r"^\s*RUN\s+pip\s+install\s+(.+)$", line)
        if m:
            specs += [a for a in shlex.split(m.group(1)) if not a.startswith("-")]
    return specs


def cmd_weblog(args) -> None:
    st = Path(args.system_tests)
    out = Path(args.out)
    previous = json.loads(out.read_text()) if out.exists() else {"ddtrace": {}}
    dockerfile = Path("utils/build/docker/python") / f"{args.variant}.Dockerfile"
    # The base image, resolved like build.sh does.
    contexts = run(
        "python3", "-I", "utils/scripts/resolve-base-images-contexts.py", "--build-contexts", str(dockerfile), cwd=st
    ).split()
    if len(contexts) != 1:
        sys.exit(f"expected one base image context for {dockerfile}, got {contexts}")
    alias, _, target = contexts[0].partition("=docker-image://")
    digest = mirror_lock(st)[target]["digest"]
    pip_installs = dockerfile_pip_installs(st / dockerfile)
    requirements = [f"ddtrace=={args.ddtrace_version}", *pip_installs]

    arches = {}
    for arch, machine in DOCKER_ARCHES.items():
        ref = f"{target.rpartition(':')[0]}@{digest}"
        probe = run(
            "docker", "run", "--rm", "--network", "none", "--platform", f"linux/{arch}", ref, "sh", "-c",
            "python -c 'import sys; print(\"%d.%d\" % sys.version_info[:2])'"
            " && ldd --version | head -1 | grep -oE '[0-9]+\\.[0-9]+$' && pip freeze",
        ).splitlines()  # fmt: skip
        python = tuple(int(x) for x in probe[0].split("."))
        glibc_minor = int(probe[1].split(".")[1])
        freeze = "\n".join(probe[2:]) + "\n"
        installed = {}
        for line in probe[2:]:
            name, _, version = line.partition("==")
            installed[canonicalize_name(name)] = version
        tags = supported_tags(python, manylinux(machine, glibc_minor))
        packages = uv_resolve(
            "\n".join(requirements) + "\n", python, f"{machine}-manylinux_2_{min(glibc_minor, GLIBC_MAX)}", freeze
        )
        # What the base image already has at the resolved version, pip leaves alone: not served.
        files = [pick_file(p, tags) for p in packages if installed.get(canonicalize_name(p["name"])) != p["version"]]
        sdists = [f["filename"] for f in files if f["kind"] != "wheel"]
        if sdists:
            sys.exit(f"{arch}: no wheel for {sdists}; pip would build them in the image")
        arches[arch] = {"python": "%d.%d" % python, "files": files}

    ddtrace = dict(previous.get("ddtrace", {}))
    ddtrace[args.ddtrace_version] = arches
    write_json(
        out,
        {
            "variant": args.variant,
            "baseAlias": alias,
            "baseImage": target,
            "dockerfileSha256": sha256_file(st / dockerfile),
            "installDdtraceSha256": sha256_file(st / "utils/build/docker/python/install_ddtrace.sh"),
            "pipInstalls": pip_installs,
            "defaultDdtrace": args.ddtrace_version if args.default or not previous.get("defaultDdtrace") else previous["defaultDdtrace"],
            "ddtrace": ddtrace,
        },
    )


def latest_ddtrace() -> str:
    import urllib.request

    with urllib.request.urlopen("https://pypi.org/pypi/ddtrace/json") as r:  # noqa: S310
        return json.load(r)["info"]["version"]


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("runner")
    p.add_argument("--system-tests", required=True)
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_runner)

    p = sub.add_parser("images")
    p.add_argument("--system-tests", required=True)
    p.add_argument("--python", required=True, help="the runner's python")
    p.add_argument("--scenario", action="append", required=True)
    p.add_argument("--weblog", action="append", required=True, help="<library>:<variant>")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_images)

    p = sub.add_parser("weblog")
    p.add_argument("--system-tests", required=True)
    p.add_argument("--variant", required=True)
    p.add_argument("--ddtrace-version", help="default: the latest release on PyPI")
    p.add_argument("--default", action="store_true", help="make this ddtrace version the default")
    p.add_argument("--out", required=True)
    p.set_defaults(func=cmd_weblog)

    args = parser.parse_args()
    if getattr(args, "ddtrace_version", "x") is None:
        args.ddtrace_version = latest_ddtrace()
        args.default = True
    args.func(args)


if __name__ == "__main__":
    main()
