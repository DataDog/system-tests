"""Guard the Node weblog lifecycle required by direct-EVP shutdown validation."""

from pathlib import Path

from utils import features, scenarios


@scenarios.test_the_test
@features.not_reported
def test_node_direct_shutdown_fixture_execs_runtime_and_scopes_sigterm_handler() -> None:
    dockerfile = Path("utils/build/docker/nodejs/express4.Dockerfile").read_text(encoding="utf-8")
    app = Path("utils/build/docker/nodejs/express/app.js").read_text(encoding="utf-8")

    assert "RUN printf 'exec node app.js\\n' >> app.sh" in dockerfile
    assert 'CMD ["./app.sh"]' in dockerfile
    assert "SYSTEM_TESTS_FFE_SHUTDOWN_FLUSH_ENABLED === 'true'" in app
    assert "process.once('SIGTERM'" in app
    assert "server.close(" in app
    assert "event: 'system_tests.ffe.shutdown.server_closed'" in app
    assert "timestamp: new Date().toISOString()" in app
