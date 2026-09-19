"""Guard the Python-only lifecycle needed by direct-EVP validation."""

from pathlib import Path

import pytest

from utils import features, scenarios
from utils._context.component_version import Version
from utils.manifest import Manifest, TestDeclaration


@scenarios.test_the_test
@features.not_reported
def test_python_direct_evp_shutdown_uses_opt_in_gunicorn_worker_exit_hook() -> None:
    app_script = Path("utils/build/docker/python/flask/app.sh").read_text(encoding="utf-8")
    gunicorn_config = Path("utils/build/docker/python/flask/direct_evp_gunicorn.py").read_text(encoding="utf-8")

    assert 'SYSTEM_TESTS_FFE_SHUTDOWN_FLUSH_ENABLED:-} = "true"' in app_script
    assert "export DD_FFE_INTAKE_HEARTBEAT_INTERVAL=5" in app_script
    assert "gunicorn_args+=(--config python:direct_evp_gunicorn)" in app_script
    assert 'exec ddtrace-run gunicorn "${gunicorn_args[@]}"' in app_script
    assert app_script.index('SYSTEM_TESTS_FFE_SHUTDOWN_FLUSH_ENABLED:-} = "true"') < app_script.index(
        "export DD_FFE_INTAKE_HEARTBEAT_INTERVAL=5"
    )
    assert app_script.index("export DD_FFE_INTAKE_HEARTBEAT_INTERVAL=5") < app_script.index(
        "gunicorn_args+=(--config python:direct_evp_gunicorn)"
    )
    assert "def worker_exit(" in gunicorn_config
    assert "system_tests.ffe.shutdown.server_closed" in gunicorn_config
    assert gunicorn_config.index("worker_exit") < gunicorn_config.index("sys.stdout.write")
    assert gunicorn_config.index("sys.stdout.write") < gunicorn_config.index("sys.stdout.flush")


@scenarios.test_the_test
@features.not_reported
def test_python_direct_evp_activation_is_scoped_to_agentless_egress() -> None:
    manifest = Path("manifests/python.yml").read_text(encoding="utf-8")
    contract = Path("tests/ffe/test_flag_eval_evp.py").read_text(encoding="utf-8")

    assert "tests/ffe/test_flag_eval_evp.py: v4.16.0-dev" in manifest
    for enabled_contract in (
        "Test_FFE_EVP_Flagevaluation_Egress_Agentless_Direct",
        "Test_FFE_EVP_Flagevaluation_Egress_Agentless_Sidecar",
    ):
        assert f"tests/ffe/test_flag_eval_evp.py::{enabled_contract}:" in manifest
        assert enabled_contract in contract

    for deferred_contract in (
        "Test_FFE_EVP_Flagevaluation_Egress_Datadog_Agent",
        "Test_FFE_EVP_Flagevaluation_Basic",
        "Test_FFE_EVP_Flagevaluation_ObserveFullData_Absent_Hashed",
        "Test_FFE_EVP_Flagevaluation_ObserveFullData_False_Hashed",
    ):
        assert f"tests/ffe/test_flag_eval_evp.py::{deferred_contract}: missing_feature (FFL-2446)" in manifest


@pytest.mark.parametrize(
    "weblog",
    ["flask-poc", "uds-flask", "uwsgi-poc", "django-poc", "django-py3.13", "python3.12", "fastapi", "tornado"],
)
@pytest.mark.parametrize("version", ["4.15.1", "4.16.0-rc1", "4.16.0"])
@scenarios.test_the_test
@features.not_reported
def test_python_evp_activation_requires_supported_version_and_weblog(weblog: str, version: str) -> None:
    manifest = Manifest({"python": Version(version)}, weblog)
    expected_enabled = weblog == "flask-poc" and version != "4.15.1"
    for nodeid in (
        "tests/ffe/test_exposure_egress.py::Test_FFE_Exposure_Egress_Agentless_Direct",
        "tests/ffe/test_exposure_egress.py::Test_FFE_Exposure_Egress_Agentless_Direct_Shutdown",
        "tests/ffe/test_exposure_egress.py::Test_FFE_Exposure_Egress_Agentless_Sidecar",
        "tests/ffe/test_flag_eval_evp.py::Test_FFE_EVP_Flagevaluation_Egress_Agentless_Direct",
        "tests/ffe/test_flag_eval_evp.py::Test_FFE_EVP_Flagevaluation_Egress_Agentless_Sidecar",
    ):
        declarations = manifest.get_declarations(nodeid)
        if expected_enabled:
            assert declarations == [], (nodeid, declarations)
        else:
            assert any(declaration.value == TestDeclaration.MISSING_FEATURE for declaration in declarations), (
                nodeid,
                declarations,
            )
