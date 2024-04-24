from functools import lru_cache
import os
import re
import semantic_version as semver

from manifests.parser.core import validate_manifest_files, load

from utils import scenarios


def get_variants_map():
    result = {}

    for folder in os.listdir("utils/build/docker"):
        folder_path = os.path.join("utils/build/docker/", folder)
        if not os.path.isdir(folder_path):
            continue

        result[folder] = ["*"]
        for file in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file)
            if os.path.isdir(file_path):
                continue
            if not file.endswith(".Dockerfile"):
                continue

            variant = file[: -len(".Dockerfile")]
            result[folder].append(variant)

    return result


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

        assert hasattr(module, name), f"Manifest path {nodeid} does not correspond to any test {dir(module)}"

        assert_in(elements, getattr(module, name), nodeid)

    def assert_valid_declaration(declaration):
        assert isinstance(declaration, str)

        if re.match(r"^(bug|flaky|irrelevant|missing_feature)( \(.+\))?$", declaration):
            return

        # must be a version declaration or semver spec
        if declaration.startswith("v"):
            assert re.match(r"^v\d.+", declaration)
        else:
            try:
                semver.NpmSpec(declaration)
            except Exception as e:
                raise ValueError(f"{declaration} is neither a version, a version range or a test state (bug, flaky ...)") from e

    manifest = load()

    variants_map = get_variants_map()

    for nodeid in sorted(manifest):
        component = list(manifest[nodeid])[0]  # blame the first one

        if "::" in nodeid:
            file, klass = nodeid.split("::")
        else:
            file, klass = nodeid, None

        try:
            content = get_file_content(file)
        except FileNotFoundError as e:
            raise ValueError(f"In {component} manifest, file {file} is declared, but does not exists") from e

        if klass is not None:
            assert (
                f"class {klass}" in content
            ), f"In {component} manifest, class {klass} is declared in {file}, but does not exists"

        # check variant names
        for component, declaration in manifest[nodeid].items():
            if isinstance(declaration, str):
                assert_valid_declaration(declaration)
                continue

            for variant in declaration:
                assert variant in variants_map[component], f"Variant {variant} does not exists for {component}"
                assert_valid_declaration(declaration[variant])
