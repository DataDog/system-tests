import ast
import os
from pathlib import Path
from utils import scenarios, logger


@scenarios.test_the_test
def test_utils():
    # verify that all files in test folder are either a test file, a utils.py file or a conftest.py file
    for folder, _, files in os.walk("tests"):
        if folder.startswith("tests/fuzzer"):
            # do not check these folders, they are particular use cases
            continue

        # particular use case: those folders will be correctly handled by orchestrator
        if folder.endswith("/utils"):
            continue

        for file in files:
            # test file, and data file are allowed everywhere
            if not file.endswith(".py") or file.startswith("test_"):
                continue

            # particular use case: those file will be correctly handled by orchestrator
            if file in ("utils.py", "conftest.py", "__init__.py"):
                continue

            raise ValueError(f"File {os.path.join(folder, file)} is not a test file or a utils file {folder}")


def _is_test_file(path: Path) -> bool:
    return path.suffix == ".py" and path.name.startswith("test_")


def _resolve_import_target(current_file: Path, module: str | None, level: int) -> Path | None:
    """Resolve an import (relative or absolute) to the .py file path it points at, if any."""
    if not module:
        # `from . import something` / `from .. import something`: imports a package, not a specific file
        return None

    if level > 0:
        directory = current_file.parent
        for _ in range(level - 1):
            directory = directory.parent
        return directory.joinpath(*module.split(".")).with_suffix(".py")

    if not module.startswith("tests."):
        # not an import of another test module, nothing to resolve
        return None

    return Path(*module.split(".")).with_suffix(".py")


@scenarios.test_the_test
def test_no_cross_test_file_imports():
    """A test file must never import from another test file. If logic is shared, it must live in a local utils.py."""

    has_error = False

    for folder, _, files in os.walk("tests"):
        if folder.startswith("tests/fuzzer"):
            # do not check these folders, they are particular use cases
            continue

        for file in files:
            if not file.startswith("test_") or not file.endswith(".py"):
                continue

            path = Path(folder, file)

            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))

            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom):
                    targets = [_resolve_import_target(path, node.module, node.level)]
                elif isinstance(node, ast.Import):
                    targets = [_resolve_import_target(path, alias.name, 0) for alias in node.names]
                else:
                    continue

                for target in targets:
                    if target is None or target == path:
                        continue

                    if _is_test_file(target):
                        logger.error(f"{path} imports from another test file: {target}")
                        has_error = True

    if has_error:
        raise ValueError(
            "Some test file imports from another test file. "
            "Shared logic must be moved to a local utils.py file instead."
        )


if __name__ == "__main__":
    test_utils()
    test_no_cross_test_file_imports()
