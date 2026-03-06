import os
from utils import scenarios


@scenarios.test_the_test
def test_utils():
    # verify that all files in test folder are either a test file, a utils.py file or a conftest.py file
    for folder, _, files in os.walk("tests"):
        if folder.startswith(("tests/fuzzer", "tests/perfs")):
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


if __name__ == "__main__":
    test_utils()
