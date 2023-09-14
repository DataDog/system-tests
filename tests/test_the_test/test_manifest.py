from manifests.parser.core import validate_manifest_files

from utils import scenarios


@scenarios.test_the_test
def test_fornats():
    validate_manifest_files()
