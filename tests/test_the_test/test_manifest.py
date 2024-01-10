from functools import lru_cache

from manifests.parser.core import validate_manifest_files, load

from utils import scenarios


@scenarios.test_the_test
def test_formats():
    validate_manifest_files()


@scenarios.test_the_test
def test_content():
    @lru_cache
    def get_file_content(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def assert_in(elements, module, nodeid):
        if len(elements) == 0:
            return

        name = elements.pop(0)
        if name.endswith(".py"):
            name = name[:-3]

        assert hasattr(
            module, name
        ), f"Manifest path {nodeid} does not correspond to any test {dir(module)}"

        assert_in(elements, getattr(module, name), nodeid)

    manifest = load()

    for nodeid in sorted(manifest):
        component = list(manifest[nodeid])[0]  # blame the first one

        if "::" in nodeid:
            file, klass = nodeid.split("::")
        else:
            file, klass = nodeid, None

        try:
            content = get_file_content(file)
        except FileNotFoundError as e:
            raise ValueError(
                f"In {component} manifest, file {file} is declared, but does not exists"
            ) from e

        if klass is not None:
            assert (
                f"class {klass}" in content
            ), f"In {component} manifest, class {klass} is declared in {file}, but does not exists"


test_content()
