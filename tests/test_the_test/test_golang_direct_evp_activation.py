"""Guard the Go-only activation and lifecycle for direct-EVP validation."""

from pathlib import Path

import yaml

from utils import features, scenarios


@scenarios.test_the_test
@features.not_reported
def test_golang_direct_evp_activation_is_scoped_to_direct_egress() -> None:
    manifest = yaml.safe_load(Path("manifests/golang.yml").read_text(encoding="utf-8"))["manifest"]

    assert manifest["tests/ffe/test_exposure_egress.py::Test_FFE_Exposure_Egress_Agentless_Direct"] == "v2.11.0-dev"
    assert manifest["tests/ffe/test_exposure_egress.py::Test_FFE_Exposure_Egress_Agentless_Direct_Shutdown"] == [
        {
            "weblog_declaration": {
                "*": "missing_feature (Shutdown lifecycle hook is implemented only by net-http)",
                "net-http": "v2.11.0-dev",
            }
        }
    ]
    assert (
        manifest["tests/ffe/test_exposure_egress.py::Test_FFE_Exposure_Egress_Agentless_Sidecar"]
        == "missing_feature (Not yet implemented)"
    )
    assert (
        manifest["tests/ffe/test_flag_eval_evp.py::Test_FFE_EVP_Flagevaluation_Egress_Agentless_Direct"]
        == "v2.11.0-dev"
    )
    assert (
        manifest["tests/ffe/test_flag_eval_evp.py::Test_FFE_EVP_Flagevaluation_Egress_Agentless_Sidecar"]
        == "missing_feature (Not yet implemented)"
    )


@scenarios.test_the_test
@features.not_reported
def test_golang_direct_evp_shutdown_uses_openfeature_lifecycle_after_server_close() -> None:
    source = Path("utils/build/docker/golang/app/net-http/main.go").read_text(encoding="utf-8")

    assert "signal.Notify(c, syscall.SIGTERM)" in source
    assert 'SYSTEM_TESTS_FFE_SHUTDOWN_FLUSH_ENABLED") == "true"' in source
    assert '"event":     "system_tests.ffe.shutdown.server_closed"' in source
    assert "srv.Shutdown(httpShutdownCtx)" in source
    assert "of.ShutdownWithContext(providerShutdownCtx)" in source
    assert source.count("context.WithTimeout(context.Background(), 10*time.Second)") == 2
    assert source.index("srv.Shutdown(httpShutdownCtx)") < source.index("system_tests.ffe.shutdown.server_closed")
    assert source.index("system_tests.ffe.shutdown.server_closed") < source.index(
        "of.ShutdownWithContext(providerShutdownCtx)"
    )
