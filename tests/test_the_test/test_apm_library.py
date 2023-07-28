import packaging.version
import pytest

from utils import apm_library


@pytest.mark.parametrize(
    "library, version",
    [
        ("python", "1.17.2"),
        ("ruby", "1.12.1"),
        ("java", "1.18.2"),
        ("dotnet", "2.34.0"),
        ("nodejs", "4.9.0"),
        ("golang", "1.52.0"),
    ],
)
def test_latest_version(library: apm_library.APMLibrary, version):
    version = packaging.version.parse(version)
    assert apm_library.latest_version(library) >= version
