from pathlib import Path
from utils import scenarios
from utils._context.component_version import Version
from utils._decorators import CustomSpec
from utils._decorators import _TestDeclaration as TestDeclaration
from utils.manifest import Manifest, SkipDeclaration


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
                    "weblog": ["django-poc"],
                    "excluded_component_version": CustomSpec(">=3.12.0+dev"),
                    "declaration": SkipDeclaration("missing_feature", "declared version for python is v3.12.0.dev"),
                    "component": "python",
                },
                {
                    "weblog": ["django-py3.13"],
                    "excluded_component_version": CustomSpec(">=3.12.0+dev"),
                    "declaration": SkipDeclaration("missing_feature", "declared version for python is v3.12.0.dev"),
                    "component": "python",
                },
                {
                    "weblog": ["python3.12"],
                    "excluded_component_version": CustomSpec(">=3.12.0+dev"),
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
                    "excluded_component_version": CustomSpec(">=2.1.0"),
                    "declaration": SkipDeclaration("missing_feature", "declared version for python is v2.1.0"),
                    "component": "python",
                }
            ],
        }

    def test_all_missing_feature(self):
        manifest = Manifest(
            "python", Version("3.12.0"), "django-poc", path=Path("tests/test_the_test/manifests/manifests_parser_test/")
        )
        assert manifest.get_declarations("tests/apm_tracing_e2e/test_otel.py::Test_Otel_Span::test_function") == [
            SkipDeclaration(TestDeclaration.MISSING_FEATURE, "missing /e2e_otel_span endpoint on weblog")
        ]

    def test_variant_conditions(self):
        manifest = Manifest(
            "python", Version("3.12.0"), "django-poc", path=Path("tests/test_the_test/manifests/manifests_parser_test/")
        )
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
        manifest = Manifest(
            "python",
            Version("3.12.0"),
            "some-variant",
            path=Path("tests/test_the_test/manifests/manifests_parser_test/"),
        )
        assert manifest.get_declarations(
            "tests/appsec/api_security/test_endpoint_discovery.py::Test_Endpoint_Discovery"
        ) == [SkipDeclaration(TestDeclaration.MISSING_FEATURE, None)]

    def test_variant_lower_version(self):
        manifest = Manifest(
            "python",
            Version("2.4.0"),
            "some-variant",
            path=Path("tests/test_the_test/manifests/manifests_parser_test/"),
        )

        assert manifest.get_declarations(
            "tests/appsec/api_security/test_api_security_rc.py::Test_API_Security_RC_ASM_DD_scanners"
        ) == [SkipDeclaration(TestDeclaration.MISSING_FEATURE, "declared version for python is v2.6.0")]
        assert manifest.get_declarations("tests/appsec/api_security/test_schemas.py::Test_Scanners") == []
        assert manifest.get_declarations("tests/appsec/iast/sink/file.py::Class::function") == [
            SkipDeclaration(TestDeclaration.MISSING_FEATURE)
        ]

    def test_parametric_test(self):
        manifest = Manifest(
            "python",
            Version("3.12.0"),
            "some-variant",
            path=Path("tests/test_the_test/manifests/manifests_parser_test/"),
        )

        assert manifest.get_declarations(
            "tests/appsec/api_security/test_endpoint_discovery.py::Test_Endpoint_Discovery::func[param]"
        ) == [SkipDeclaration(TestDeclaration.MISSING_FEATURE)]

    def test_non_library_component(self):
        manifest = Manifest(
            "python",
            Version("3.12.0"),
            "some-variant",
            agent_version=Version("1.12.0"),
            path=Path("tests/test_the_test/manifests/manifests_parser_test/"),
        )

        assert manifest.get_declarations(
            "tests/appsec/api_security/test_api_security_rc.py::Test_API_Security_RC_ASM_DD_scanners::func"
        ) == [SkipDeclaration(TestDeclaration.MISSING_FEATURE, details="declared version for agent is v2.6.0")]
