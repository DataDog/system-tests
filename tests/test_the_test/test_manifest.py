from pathlib import Path
from utils import scenarios
from utils._context.component_version import Version
from utils.manifest import Manifest, SkipDeclaration, TestDeclaration
from utils.manifest._internal.types import SemverRange as CustomSpec


def manifest_init(
    components: dict[str, Version],
    weblog: str = "some_variant",
    path: Path = Path("tests/test_the_test/manifests/manifests_parser_test/"),
):
    return Manifest(components, weblog, path)


@scenarios.test_the_test
class TestManifest:
    def test_formats(self):
        Manifest.validate()

    def test_parser(self):
        manifest = Manifest.parse(Path("tests/test_the_test/manifests/manifests_parser_test/"))
        assert manifest == {
            "tests/apm_tracing_e2e/test_otel.py::Test_Otel_Span": [
                {
                    "excluded_component_version": CustomSpec(">=3.4.5"),
                    "declaration": SkipDeclaration("missing_feature", "declared version for java is v3.4.5"),
                    "component": "java",
                },
                {
                    "declaration": SkipDeclaration("missing_feature", "missing /e2e_otel_span endpoint on weblog"),
                    "component": "python",
                },
            ],
            "tests/appsec/api_security/test_api_security_rc.py::Test_API_Security_RC_ASM_DD_scanners": [
                {
                    "excluded_component_version": CustomSpec(">=2.6.0"),
                    "declaration": SkipDeclaration("missing_feature", "declared version for agent is v2.6.0"),
                    "component": "agent",
                },
                {"declaration": SkipDeclaration("missing_feature"), "component": "java"},
                {
                    "excluded_component_version": CustomSpec(">=2.6.0"),
                    "declaration": SkipDeclaration("missing_feature", "declared version for python is v2.6.0"),
                    "component": "python",
                },
            ],
            "tests/appsec/api_security/test_endpoint_discovery.py::Test_Endpoint_Discovery": [
                {
                    "excluded_weblog": ["spring-boot"],
                    "excluded_component_version": CustomSpec(">=1.2.3"),
                    "declaration": SkipDeclaration("missing_feature", "declared version for java is v1.2.3"),
                    "component": "java",
                },
                {"weblog": ["spring-boot"], "declaration": SkipDeclaration("missing_feature"), "component": "java"},
                {
                    "excluded_weblog": ["django-poc", "django-py3.13", "python3.12"],
                    "declaration": SkipDeclaration("missing_feature"),
                    "component": "python",
                },
                {
                    "weblog": ["django-poc", "django-py3.13", "python3.12"],
                    "excluded_component_version": CustomSpec(">=3.12.0-dev"),
                    "declaration": SkipDeclaration("missing_feature", "declared version for python is v3.12.0.dev"),
                    "component": "python",
                },
            ],
            "tests/appsec/api_security/test_schemas.py::Test_Scanners": [
                {
                    "excluded_weblog": ["fastapi"],
                    "excluded_component_version": CustomSpec(">=2.4.0"),
                    "declaration": SkipDeclaration("missing_feature", "declared version for python is v2.4.0"),
                    "component": "python",
                },
                {"weblog": ["fastapi"], "declaration": SkipDeclaration("missing_feature"), "component": "python"},
            ],
            "tests/appsec/api_security/test_schemas.py::Test_Schema_Request_Cookies": [
                {
                    "excluded_weblog": ["fastapi"],
                    "excluded_component_version": CustomSpec(">=2.1.0"),
                    "declaration": SkipDeclaration("missing_feature", "declared version for python is v2.1.0"),
                    "component": "python",
                },
                {
                    "weblog": ["fastapi"],
                    "excluded_component_version": CustomSpec(">=2.5.0"),
                    "declaration": SkipDeclaration("missing_feature", "declared version for python is v2.5.0"),
                    "component": "python",
                },
            ],
            "tests/appsec/iast/sink": [{"declaration": SkipDeclaration("missing_feature"), "component": "python"}],
            "tests/appsec/iast": [
                {
                    "component": "python",
                    "component_version": CustomSpec("<3.11.0"),
                    "declaration": SkipDeclaration(
                        "missing_feature",
                        "APPSEC-57830 python tracer was using MANUAL_KEEP for 1 trace in 60 seconds to keep instead of AUTO_KEEP",
                    ),
                    "weblog": ["django-poc", "django-py3.13", "python3.12"],
                }
            ],
            "tests/appsec/iast/test": [
                {
                    "component": "python",
                    "component_version": CustomSpec("<3.11.0"),
                    "declaration": SkipDeclaration("irrelevant"),
                    "weblog": ["django-poc", "django-py3.13", "python3.12", "fastapi"],
                }
            ],
        }

    def test_all_missing_feature(self):
        manifest = manifest_init({"python": Version("3.12.0")}, "django-poc")
        assert manifest.get_declarations("tests/apm_tracing_e2e/test_otel.py::Test_Otel_Span::test_function") == [
            SkipDeclaration(TestDeclaration.MISSING_FEATURE, "missing /e2e_otel_span endpoint on weblog")
        ]

    def test_variant_conditions(self):
        manifest = manifest_init({"python": Version("3.12.0")}, "django-poc")
        assert (
            manifest.get_declarations(
                "tests/apm_tracing_e2e/test_otel.py::Test_API_Security_RC_ASM_DD_scanners::test_function"
            )
            == []
        )
        assert (
            manifest.get_declarations(
                "tests/appsec/api_security/test_endpoint_discovery.py::Test_Endpoint_Discovery::test_function"
            )
            == []
        )
        assert (
            manifest.get_declarations(
                "tests/appsec/api_security/test_schemas.py::Test_Endpoint_Discovery::test_function"
            )
            == []
        )

    def test_variant_star(self):
        manifest = manifest_init({"python": Version("3.12.0")})
        assert manifest.get_declarations(
            "tests/appsec/api_security/test_endpoint_discovery.py::Test_Endpoint_Discovery"
        ) == [SkipDeclaration(TestDeclaration.MISSING_FEATURE, None)]

    def test_variant_lower_version(self):
        manifest = manifest_init({"python": Version("2.4.0")})

        assert manifest.get_declarations(
            "tests/appsec/api_security/test_api_security_rc.py::Test_API_Security_RC_ASM_DD_scanners"
        ) == [SkipDeclaration(TestDeclaration.MISSING_FEATURE, "declared version for python is v2.6.0")]
        assert manifest.get_declarations("tests/appsec/api_security/test_schemas.py::Test_Scanners") == []
        assert manifest.get_declarations("tests/appsec/iast/sink/file.py::Class::function") == [
            SkipDeclaration(TestDeclaration.MISSING_FEATURE)
        ]

    def test_parametric_test(self):
        manifest = manifest_init({"python": Version("3.12.0")})

        assert manifest.get_declarations(
            "tests/appsec/api_security/test_endpoint_discovery.py::Test_Endpoint_Discovery::func[param]"
        ) == [SkipDeclaration(TestDeclaration.MISSING_FEATURE)]

    def test_non_library_component(self):
        manifest = manifest_init({"python": Version("3.12.0"), "agent": Version("1.12.0")})

        assert manifest.get_declarations(
            "tests/appsec/api_security/test_api_security_rc.py::Test_API_Security_RC_ASM_DD_scanners::func"
        ) == [SkipDeclaration(TestDeclaration.MISSING_FEATURE, details="declared version for agent is v2.6.0")]
