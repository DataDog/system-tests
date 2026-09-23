"""Keep released Python configuration coverage independent of EVP fallback."""

import pytest

from utils import features, scenarios
from utils._context.component_version import Version
from utils.manifest import Manifest


@pytest.mark.parametrize("version", ["4.13.3", "4.14.0", "4.15.2", "4.16.0-rc1"])
@pytest.mark.parametrize("weblog", ["flask-poc", "django-poc", "fastapi", "tornado"])
@scenarios.test_the_test
@features.not_reported
def test_python_agentless_configuration_activation_is_independent_of_evp(version: str, weblog: str) -> None:
    manifest = Manifest({"python": Version(version)}, weblog)
    declarations = manifest.get_declarations(
        "tests/ffe/test_agentless_configuration.py::Test_FFE_Agentless_Configuration"
    )
    assert (not declarations) == (version != "4.13.3" and weblog == "flask-poc"), declarations

    for nodeid in (
        "tests/ffe/test_exposure_egress.py::Test_FFE_Exposure_Egress_Agentless_Direct",
        "tests/ffe/test_exposure_egress.py::Test_FFE_Exposure_Egress_Agentless_Direct_Shutdown",
        "tests/ffe/test_exposure_egress.py::Test_FFE_Exposure_Egress_Agentless_Sidecar",
        "tests/ffe/test_flag_eval_evp.py::Test_FFE_EVP_Flagevaluation_Egress_Agentless_Direct",
        "tests/ffe/test_flag_eval_evp.py::Test_FFE_EVP_Flagevaluation_Egress_Agentless_Sidecar",
    ):
        assert manifest.get_declarations(nodeid), nodeid
