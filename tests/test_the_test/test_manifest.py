from utils.manifest import Manifest
from utils import scenarios


@scenarios.test_the_test
def test_formats():
    Manifest.validate()
