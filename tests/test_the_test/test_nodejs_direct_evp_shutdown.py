"""Guard the Node weblog lifecycle required by direct-EVP shutdown validation."""

from pathlib import Path

import pytest

from utils import features, scenarios
from utils._context.component_version import Version
from utils.manifest import Manifest


@scenarios.test_the_test
@features.not_reported
def test_node_direct_shutdown_fixture_execs_runtime_and_scopes_sigterm_handler() -> None:
    dockerfile = Path("utils/build/docker/nodejs/express5.Dockerfile").read_text(encoding="utf-8")
    app = Path("utils/build/docker/nodejs/express/app.js").read_text(encoding="utf-8")

    assert "RUN printf 'exec node app.js\\n' >> app.sh" in dockerfile
    assert 'CMD ["./app.sh"]' in dockerfile
    assert "SYSTEM_TESTS_FFE_SHUTDOWN_FLUSH_ENABLED === 'true'" in app
    assert "process.once('SIGTERM'" in app
    assert "server.close(" in app
    assert "event: 'system_tests.ffe.shutdown.server_closed'" in app
    assert "timestamp: new Date().toISOString()" in app


@pytest.mark.parametrize("weblog", ["express4", "express5", "fastify"])
@scenarios.test_the_test
@features.not_reported
def test_node_direct_evp_activation_follows_main_express5_fixture(weblog: str) -> None:
    manifest = Manifest({"nodejs": Version("7.0.0-pre")}, weblog)
    for test_class in (
        "Test_FFE_Exposure_Egress_Agentless_Direct",
        "Test_FFE_Exposure_Egress_Agentless_Direct_Shutdown",
        "Test_FFE_Exposure_Egress_Agentless_Sidecar",
    ):
        declarations = manifest.get_declarations(f"tests/ffe/test_exposure_egress.py::{test_class}")
        assert (not declarations) == (weblog == "express5"), declarations
