import json
from pathlib import Path
from unittest.mock import Mock, patch

import conftest

from utils import pytest, scenarios
from utils._context._scenarios.aws_lambda import LambdaScenario
from utils._context.component_version import ComponentVersion
from utils._context.containers import LambdaWeblogContainer
from utils.manifest import Manifest


TELEMETRY_TESTS = [
    "tests/appsec/rasp/test_cmdi.py::Test_Cmdi_Telemetry",
    "tests/appsec/rasp/test_cmdi.py::Test_Cmdi_Telemetry_V2",
    "tests/appsec/rasp/test_cmdi.py::Test_Cmdi_Telemetry_Variant_Tag",
    "tests/appsec/rasp/test_lfi.py::Test_Lfi_Telemetry",
    "tests/appsec/rasp/test_lfi.py::Test_Lfi_Telemetry_V2",
    "tests/appsec/rasp/test_shi.py::Test_Shi_Telemetry",
    "tests/appsec/rasp/test_shi.py::Test_Shi_Telemetry_V2",
    "tests/appsec/rasp/test_shi.py::Test_Shi_Telemetry_Variant_Tag",
    "tests/appsec/rasp/test_sqli.py::Test_Sqli_Telemetry",
    "tests/appsec/rasp/test_sqli.py::Test_Sqli_Telemetry_V2",
    "tests/appsec/rasp/test_ssrf.py::Test_Ssrf_Telemetry",
    "tests/appsec/rasp/test_ssrf.py::Test_Ssrf_Telemetry_V2",
]


@scenarios.test_the_test
class Test_LambdaVersions:
    @pytest.mark.parametrize(
        ("language", "version", "normalized"),
        [
            ("python", "4.15.0.dev0", "4.15.0-dev0"),
            ("nodejs", "5.118.0", "5.118.0"),
            ("ruby", "2.40.0.rc1", "2.40.0-rc1"),
            ("java", "1.60.0~abcdef", "1.60.0+abcdef"),
        ],
    )
    def test_healthcheck_registers_tracer_component(
        self, tmp_path: Path, language: str, version: str, normalized: str
    ) -> None:
        container = object.__new__(LambdaWeblogContainer)
        container.host_project_dir = str(tmp_path)
        container.host_log_folder = "logs"
        container.name = "weblog"
        container.image = Mock(env={})
        container.stdout_interface = Mock()
        container.weblog_variant = "alb"
        healthcheck = Path(container.healthcheck_log_file)
        healthcheck.parent.mkdir(parents=True)
        data = {
            "library": {"name": f"{language}_lambda", "version": "8.129.0"},
            "tracer": {"name": language, "version": version},
        }
        healthcheck.write_text(json.dumps(data))
        with patch.object(container, "_container", None, create=True):
            container.post_start()

        scenario = object.__new__(LambdaScenario)
        scenario.lambda_weblog = container
        scenario.components = {}
        scenario._set_components()  # noqa: SLF001 - verify scenario component registration
        assert str(scenario.components[language]) == normalized
        assert str(scenario.components[f"{language}_lambda"]) == "8.129.0"
        assert scenario.components["library"] == container.library.version

        del data["tracer"]
        healthcheck.write_text(json.dumps(data))
        with patch.object(container, "_container", None, create=True):
            container.post_start()
        scenario.components = {}
        scenario._set_components()  # noqa: SLF001 - verify legacy healthcheck behavior
        assert language not in scenario.components

    @pytest.mark.parametrize("weblog", ["alb", "alb-multi", "apigw-http", "apigw-rest", "function-url"])
    @pytest.mark.parametrize(
        ("layer", "tracer", "restricted"),
        [
            ("8.129.0.dev0", "4.14.2", True),
            ("8.129.0", "4.15.0.dev0", True),
            ("8.129.0", "4.15.0", False),
            ("8.128.0", "4.15.0", False),
            ("8.127.0", "4.15.0", True),
            ("8.129.0", "4.16.0", False),
        ],
    )
    def test_rasp_telemetry_requires_layer_and_tracer(
        self, weblog: str, layer: str, tracer: str, *, restricted: bool
    ) -> None:
        manifest = Manifest(
            {
                "python_lambda": ComponentVersion("python_lambda", layer).version,
                "python": ComponentVersion("python", tracer).version,
            },
            weblog,
        )
        for nodeid in TELEMETRY_TESTS:
            assert bool(manifest.get_declarations(nodeid)) is restricted, nodeid

    def test_regular_python_telemetry_keeps_existing_versions(self) -> None:
        manifest = Manifest({"python": ComponentVersion("python", "4.14.2").version}, "flask-poc")
        for nodeid in TELEMETRY_TESTS:
            assert not manifest.get_declarations(nodeid), nodeid

    @pytest.mark.parametrize("weblog", ["ruby-apigw-http", "ruby-apigw-rest"])
    def test_ruby_lambda_keeps_passing_tests_enabled(self, weblog: str) -> None:
        manifest = Manifest(
            {
                "ruby_lambda": ComponentVersion("ruby_lambda", "3.30.0").version,
                "ruby": ComponentVersion("ruby", "2.40.0").version,
            },
            weblog,
        )
        for nodeid in [
            "tests/appsec/api_security/test_schemas.py::Test_Schema_Request_FormUrlEncoded_Body::test_request_method",
            "tests/appsec/rasp/test_ssrf.py::Test_Ssrf_Telemetry_V2::test_ssrf_telemetry",
            "tests/appsec/test_traces.py::Test_CollectDefaultRequestHeader::test_collect_default_request_headers",
            "tests/appsec/waf/test_blocking.py::Test_Blocking::test_json_template_v1",
        ]:
            assert not manifest.get_declarations(nodeid), nodeid

    @pytest.mark.parametrize(
        ("library", "version", "tracer", "exits"),
        [
            ("nodejs_lambda", "99.0.0", ComponentVersion("nodejs", "5.126.0"), False),
            ("ruby_lambda", "99.0.0", ComponentVersion("ruby", "2.43.0"), False),
            ("nodejs_lambda", "0.0.0", ComponentVersion("nodejs", "5.126.0"), True),
            ("ruby_lambda", "0.0.0", ComponentVersion("ruby", "2.43.0"), True),
            ("nodejs", "5.126.0", None, True),
            ("ruby", "2.43.0", None, True),
        ],
    )
    def test_dev_mode_checks_the_development_library(
        self,
        monkeypatch: pytest.MonkeyPatch,
        library: str,
        version: str,
        tracer: ComponentVersion | None,
        *,
        exits: bool,
    ) -> None:
        library_version = ComponentVersion(library, version)
        components = {library: library_version.version}
        if tracer:
            components[tracer.name] = tracer.version
        context = Mock(library=library_version, scenario=Mock(components=components), weblog_variant="alb")
        session = Mock()
        session.config.option.collectonly = True
        session.config.option.sleep = False
        session.config._store.get.return_value = None  # noqa: SLF001 - mock pytest's JUnit property store
        session.config.pluginmanager.get_plugin.return_value = conftest.logger.terminal
        monkeypatch.setenv("SYSTEM_TESTS_DEV_MODE", "true")
        with patch.object(conftest, "context", context), patch.object(conftest.pytest, "exit") as exit_mock:
            conftest.pytest_sessionstart(session)
        assert exit_mock.called is exits
