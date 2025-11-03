from functools import lru_cache
import os
from pathlib import Path
import re
import semantic_version as semver

from manifests.parser.core import validate_manifest_files, load

from utils import scenarios


def get_variants_map():
    result = {}

    for folder in os.listdir("utils/build/docker"):
        folder_path = os.path.join("utils/build/docker/", folder)
        if not Path(folder_path).is_dir():
            continue

        result[folder] = ["*"]
        for file in os.listdir(folder_path):
            file_path = os.path.join(folder_path, file)
            if Path(file_path).is_dir():
                continue
            if not file.endswith(".Dockerfile"):
                continue

            variant = file[: -len(".Dockerfile")]
            result[folder].append(variant)

    return result


@scenarios.test_the_test
def test_formats():
    validate_manifest_files()


