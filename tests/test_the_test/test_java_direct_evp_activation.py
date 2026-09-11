"""Guard the Java-only trust and shutdown pieces for direct-EVP validation."""

from pathlib import Path
from typing import Literal

import pytest

from utils import features, scenarios
from utils._context._scenarios.agentless_endtoend import FeatureFlaggingAgentlessEndToEndScenario
from utils.proxy.ports import ProxyPorts


@pytest.mark.parametrize(
    ("route", "library", "weblog_variant", "expected"),
    [
        ("direct", "java", "spring-boot", "configured"),
        ("sidecar", "java", "spring-boot", "unchanged"),
        ("direct", "java", "spring-boot-3-native", "unchanged"),
        ("direct", "nodejs", "express4", "unchanged"),
    ],
)
@scenarios.test_the_test
@features.not_reported
def test_java_direct_evp_uses_canonical_startup_and_preserves_java_opts(
    route: Literal["direct", "sidecar"],
    library: str,
    weblog_variant: str,
    expected: Literal["configured", "unchanged"],
) -> None:
    scenario = FeatureFlaggingAgentlessEndToEndScenario(
        "MOCK_FFE_JAVA_DIRECT_EVP",
        doc="test",
        exposure_egress=route,
    )
    library_container = scenario.weblog_infra.http_container
    library_container.image.labels["system-tests-library"] = library
    library_container.weblog_variant = weblog_variant
    library_container.environment["JAVA_OPTS"] = "-Dexisting.option=true"

    scenario._configure_java_direct_evp()  # noqa: SLF001 - focused activation test

    assert library_container.environment["JAVA_OPTS"] == "-Dexisting.option=true"
    if expected == "unchanged":
        assert "SYSTEM_TESTS_JAVA_PROXY_OPTS" not in library_container.environment
        assert "./utils/build/docker/java/app-with-proxy-ca.sh" not in library_container.volumes
        assert "./utils/build/docker/java/app.sh" not in library_container.volumes
        assert "./utils/proxy/.mitmproxy/mitmproxy-ca-cert.cer" not in library_container.volumes
        return

    assert library_container.environment["SYSTEM_TESTS_JAVA_PROXY_OPTS"] == (
        f"-Dhttps.proxyHost=proxy -Dhttps.proxyPort={ProxyPorts.datadog_direct}"
    )
    assert library_container.volumes["./utils/build/docker/java/app-with-proxy-ca.sh"] == {
        "bind": "/app/app.sh",
        "mode": "ro",
    }
    assert library_container.volumes["./utils/build/docker/java/app.sh"] == {
        "bind": "/app/system-tests-java-app.sh",
        "mode": "ro",
    }
    assert library_container.volumes["./utils/proxy/.mitmproxy/mitmproxy-ca-cert.cer"] == {
        "bind": "/app/system-tests-proxy-ca.cer",
        "mode": "ro",
    }

    wrapper = Path("utils/build/docker/java/app-with-proxy-ca.sh").read_text(encoding="utf-8")
    assert 'JAVA_OPTS="${JAVA_OPTS:-} ${SYSTEM_TESTS_JAVA_PROXY_OPTS:-}' in wrapper
    assert "export JAVA_OPTS" in wrapper
    assert "exec /app/system-tests-java-app.sh" in wrapper
    assert "java -Xmx" not in wrapper


@scenarios.test_the_test
@features.not_reported
def test_java_direct_evp_shutdown_is_opt_in_and_closes_server_before_exit() -> None:
    entrypoint = Path(
        "utils/build/docker/java/spring-boot/src/main/java/com/datadoghq/system_tests/springboot/"
        "SpringbootwildflyApplication.java"
    ).read_text(encoding="utf-8")
    shutdown = Path(
        "utils/build/docker/java/spring-boot/src/main/java/com/datadoghq/system_tests/springboot/DirectEvpShutdown.java"
    ).read_text(encoding="utf-8")

    assert "ConfigurableApplicationContext context = SpringApplication.run(applicationClass, args);" in entrypoint
    assert "DirectEvpShutdown.install(context);" in entrypoint
    assert "SYSTEM_TESTS_FFE_SHUTDOWN_FLUSH_ENABLED" in shutdown
    assert 'Signal.handle(new Signal("TERM")' in shutdown
    assert shutdown.index("context.close();") < shutdown.index("system_tests.ffe.shutdown.server_closed")
    assert shutdown.index("system_tests.ffe.shutdown.server_closed") < shutdown.index("System.exit(exitCode);")
