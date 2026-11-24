"""The files of a system-tests checkout a scenario's run reads (see ./sources.nix).

    sources.py index <checkout> <scenario> <out> --library <library> [--manifest <component>]...
        [--path <path>]...

collects the scenario's tests (pytest -S <scenario> --collect-only) on a copy of <checkout>,
recording every file read meanwhile and which file of the checkout read it, and writes to <out> the
sorted JSON list of the files the scenario needs:

- outside tests/: what collection read (the framework, conftest.py, pyproject.toml), except the
  manifests of components other than the --manifest ones;
- under tests/: the modules holding a selected test, the conftest.py and __init__.py files above
  them, and the non-Python files next to them (data the tests read at run time);
- what those files import (statically, also in functions) and, for test modules and their helpers,
  what they read during collection, transitively;
- the --path files and directories (what the run reads that collection does not).

Test modules without a selected test, and whatever only they use, are left out. The scenario's
tests are then collected again on the files kept alone; the index fails unless the same tests are
selected.

    sources.py collect <dir> <scenario> <library> <result>

(internal) collects in <dir> and writes the outcome to <result>.
"""

import argparse
import ast
import functools
import json
import os
import shutil
import subprocess
import sys
import tempfile
import types
from pathlib import Path


def collect(directory: str, scenario: str, library: str, result: str) -> None:
    root = os.path.realpath(directory)
    prefix = root + "/"
    reads: set[tuple[str, str | None]] = set()

    @functools.cache
    def resolve(path: str) -> str | None:
        full = os.path.realpath(path)
        return full[len(prefix) :] if full.startswith(prefix) else None

    def relative(path: object) -> str | None:
        if isinstance(path, int) or path is None:
            return None
        try:
            path = os.fsdecode(path)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return None
        return resolve(os.path.join(os.getcwd(), path))

    def hook(event: str, args: tuple) -> None:
        if event != "open":
            return
        path, mode, flags = args
        if isinstance(mode, str):
            if any(c in mode for c in "wax+"):
                return
        elif flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT):
            return
        name = relative(path)
        if name is None:
            return
        # The reader is the innermost module of tests/ on the stack (a test module, or a helper it
        # calls), other than the file opened. Frames of utils/ do not count: they read on anyone's
        # behalf (utils/proxy/scrubber.py even wraps open), and what they read outside tests/ is
        # kept anyway. None when pytest or the framework alone reads the file.
        reader = None
        frame = sys._getframe(1)
        while frame is not None:
            code_file = frame.f_code.co_filename
            if os.path.isabs(code_file):
                code_file = relative(code_file)
                if code_file is not None and code_file != name and code_file.startswith("tests/"):
                    reader = code_file
                    break
            frame = frame.f_back
        reads.add((name, reader))

    import docker
    import pytest

    # What TestedContainer.configure reads of an image (ImageInfo): its environment and labels. The
    # weblog's say which library it is; the variant only picks the weblog's metadata, as tests are
    # selected by scenario alone (conftest.py, pytest_collection_modifyitems).
    image = types.SimpleNamespace(
        attrs={
            "Config": {
                "Env": [],
                "Labels": {
                    "system-tests-library": library,
                    "system-tests-weblog-variant": "nix-sources-index",
                },
            }
        }
    )

    class NoDaemon:
        """The Docker client collection gets: a Nix build has no daemon. Configuring a scenario
        asks the daemon for its info, the containers left from a previous run and the images
        (configure); containers start later, in pytest_sessionstart, which --collect-only skips."""

        containers = types.SimpleNamespace(list=lambda **_: [])
        images = types.SimpleNamespace(get=lambda _name: image)

        def info(self) -> dict:
            return {}

        def __getattr__(self, name: str):
            raise RuntimeError(f"collecting the tests used Docker ({name}), which the index lacks")

    docker.DockerClient.from_env = staticmethod(lambda *_, **__: NoDaemon())

    class Recorder:
        def __init__(self) -> None:
            self.modules: set[str] = set()
            self.selected: list[str] = []

        @pytest.hookimpl
        def pytest_collectstart(self, collector: pytest.Collector) -> None:
            if isinstance(collector, pytest.Module):
                self.modules.add(str(Path(collector.path).relative_to(root)))

        @pytest.hookimpl(trylast=True)
        def pytest_collection_finish(self, session: pytest.Session) -> None:
            self.selected = [item.nodeid for item in session.items]

    os.chdir(root)
    sys.path.insert(0, root)  # like `python -m pytest`
    sys.dont_write_bytecode = True
    sys.addaudithook(hook)
    recorder = Recorder()
    status = pytest.main(
        ["-S", scenario, "--collect-only", "-q", "-p", "no:cacheprovider", "-p", "no:warnings"],
        plugins=[recorder],
    )
    with open(result, "w", encoding="utf-8") as f:
        json.dump(
            {
                "status": int(status),
                "modules": sorted(recorder.modules),
                "selected": recorder.selected,
                "reads": sorted(reads, key=lambda r: (r[0], r[1] or "")),
            },
            f,
        )


def run_collect(directory: Path, scenario: str, library: str, work: Path) -> dict:
    result = work / f"{directory.name}.json"
    log = work / f"{directory.name}.log"
    with open(log, "w", encoding="utf-8") as out:
        subprocess.run(
            [sys.executable, __file__, "collect", str(directory), scenario, library, str(result)],
            stdout=out,
            stderr=subprocess.STDOUT,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
            check=False,
        )
    outcome = json.loads(result.read_text()) if result.exists() else {"status": -1}
    if outcome["status"] != 0:
        sys.stderr.write(log.read_text())
        sys.exit(f"collecting {scenario} in {directory} failed (status {outcome['status']})")
    return outcome


@functools.cache
def files_of(checkout: Path) -> frozenset[str]:
    """The checkout's files, by exact name: macOS' file system would also find `Scenario.py` for
    `scenario.py`."""
    return frozenset(
        os.path.relpath(os.path.join(d, f), checkout)
        for d, _, names in os.walk(checkout)
        for f in names
    )


def module_file(checkout: Path, name: str) -> str | None:
    base = name.replace(".", "/")
    for candidate in (f"{base}.py", f"{base}/__init__.py"):
        if candidate in files_of(checkout):
            return candidate
    return None


def imports(checkout: Path, file: str) -> set[str]:
    """The files of the checkout `file` imports, wherever the import statement is."""
    try:
        tree = ast.parse((checkout / file).read_bytes(), filename=file)
    except (SyntaxError, ValueError):
        return set()
    package = Path(file).parent.parts
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parts = list(package[: len(package) - node.level + 1])
                base = ".".join(parts + ([node.module] if node.module else []))
            else:
                base = node.module or ""
            if base:
                names.add(base)
            names.update(f"{base}.{alias.name}" if base else alias.name for alias in node.names)
    found = set()
    for name in names:
        # A module imports its parent packages too.
        parts = name.split(".")
        for i in range(1, len(parts) + 1):
            module = module_file(checkout, ".".join(parts[:i]))
            if module is not None:
                found.add(module)
    return found


def ancestors(file: str):
    parent = Path(file).parent
    while parent != Path("."):
        yield parent
        parent = parent.parent
    yield Path(".")


def index(
    checkout: Path, scenario: str, library: str, out: Path, manifests: list[str], paths: list[str]
) -> None:
    work = Path(tempfile.mkdtemp())
    full = work / "full"
    shutil.copytree(checkout, full, symlinks=True)
    for d, _, _ in os.walk(full):
        os.chmod(d, 0o755)
    collected = run_collect(full, scenario, library, work)

    def exists(name: str) -> bool:
        return name in files_of(checkout)

    reads = [(name, reader) for name, reader in collected["reads"] if exists(name)]
    selected_files = {nodeid.split("::", 1)[0] for nodeid in collected["selected"]}
    keep: set[str] = set(selected_files)

    for name, _ in reads:
        if name.startswith("tests/"):
            continue
        if (
            name.startswith("manifests/")
            and name.endswith(".yml")
            and Path(name).stem not in manifests
        ):
            continue
        keep.add(name)

    for path in paths:
        if (checkout / path).is_dir():
            keep.update(
                str(p.relative_to(checkout)) for p in (checkout / path).rglob("*") if p.is_file()
            )
        elif exists(path):
            keep.add(path)
        else:
            sys.exit(f"{path} (a source of {scenario}) is not in the checkout")

    for test in selected_files:
        directory = checkout / Path(test).parent
        keep.update(
            str(p.relative_to(checkout))
            for p in directory.iterdir()
            if p.is_file() and p.suffix != ".py"
        )
        for parent in ancestors(test):
            if exists(str(parent / "conftest.py")):
                keep.add(str(parent / "conftest.py"))

    read_by: dict[str, set[str]] = {}
    for name, reader in reads:
        if reader is not None:
            read_by.setdefault(reader, set()).add(name)

    pending = list(keep)
    while pending:
        file = pending.pop()
        found = set(read_by.get(file, ()))
        if file.endswith(".py"):
            found |= imports(checkout, file)
        for parent in ancestors(file):
            if exists(str(parent / "__init__.py")):
                found.add(str(parent / "__init__.py"))
        for name in found - keep:
            if name.startswith("manifests/") and Path(name).stem not in manifests:
                continue
            keep.add(name)
            pending.append(name)

    # The same tests must be selected from the files kept alone.
    sliced = work / "sliced"
    for name in keep:
        (sliced / name).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(checkout / name, sliced / name)
    check = run_collect(sliced, scenario, library, work)
    if check["selected"] != collected["selected"]:
        missing = sorted(set(collected["selected"]) - set(check["selected"]))
        extra = sorted(set(check["selected"]) - set(collected["selected"]))
        sys.exit(
            f"collecting {scenario} on its sources selects other tests than on the checkout:\n"
            + "".join(f"  missing: {n}\n" for n in missing[:20])
            + "".join(f"  extra:   {n}\n" for n in extra[:20])
            + ("  (same tests, other order)\n" if not missing and not extra else "")
        )

    dropped = len(set(collected["modules"]) - keep)
    print(
        f"{scenario}: {len(collected['selected'])} tests in {len(selected_files)} modules; "
        f"{len(keep)} files kept, {dropped} test modules without a selected test left out"
    )
    out.write_text(json.dumps(sorted(keep), indent=0) + "\n")


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "collect":
        collect(*sys.argv[2:6])
        return
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=["index"])
    parser.add_argument("checkout", type=Path)
    parser.add_argument("scenario")
    parser.add_argument("out", type=Path)
    parser.add_argument(
        "--library", required=True, help="the weblog's library (system-tests-library)"
    )
    parser.add_argument("--manifest", action="append", default=[])
    parser.add_argument("--path", action="append", default=[])
    args = parser.parse_args()
    index(args.checkout, args.scenario, args.library, args.out, args.manifest, args.path)


if __name__ == "__main__":
    main()
