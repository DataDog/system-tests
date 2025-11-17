from utils._decorators import _TestDeclaration as TestDeclaration
from utils._decorators import CustomSpec
from utils._context.component_version import Version
from utils.manifest import Manifest
from utils import scenarios


@scenarios.test_the_test
class TestManifest:
    def test_formats(self):
        # Manifest.validate()
        pass

    def test_parser(self):
        manifest = Manifest.parse("tests/test_the_test/manifests/manifests_parser_test/")
        print(manifest)
        assert manifest == {'tests/apm_tracing_e2e/test_otel.py::Test_Otel_Span': [{'excluded_library_version': CustomSpec('>=3.4.5'), 'declaration': 'missing_feature', 'library': 'java'}, {'declaration': 'missing_feature (missing /e2e_otel_span endpoint on weblog)', 'library': 'python'}], 'tests/appsec/api_security/test_api_security_rc.py::Test_API_Security_RC_ASM_DD_scanners': [{'declaration': 'missing_feature', 'library': 'java'}, {'excluded_library_version': CustomSpec('>=2.6.0'), 'declaration': 'missing_feature', 'library': 'python'}], 'tests/appsec/api_security/test_endpoint_discovery.py::Test_Endpoint_Discovery': [{'excluded_weblog': ['spring-boot'], 'excluded_library_version': CustomSpec('>=1.2.3'), 'declaration': 'missing_feature', 'library': 'java'}, {'weblog': 'spring-boot', 'declaration': 'missing_feature', 'library': 'java'}, {'excluded_weblog': ['django-poc', 'django-py3.13', 'python3.12'], 'declaration': 'missing_feature', 'library': 'python'}, {'weblog': 'django-poc', 'excluded_library_version': CustomSpec('>=3.12.0-dev'), 'declaration': 'missing_feature', 'library': 'python'}, {'weblog': 'django-py3.13', 'excluded_library_version': CustomSpec('>=3.12.0-dev'), 'declaration': 'missing_feature', 'library': 'python'}, {'weblog': 'python3.12', 'excluded_library_version': CustomSpec('>=3.12.0-dev'), 'declaration': 'missing_feature', 'library': 'python'}], 'tests/appsec/api_security/test_schemas.py::Test_Scanners': [{'excluded_weblog': ['fastapi'], 'excluded_library_version': CustomSpec('>=2.4.0'), 'declaration': 'missing_feature', 'library': 'python'}, {'weblog': 'fastapi', 'declaration': 'missing_feature', 'library': 'python'}], 'tests/appsec/api_security/test_schemas.py::Test_Schema_Request_Cookies': [{'excluded_weblog': ['fastapi'], 'excluded_library_version': CustomSpec('>=2.1.0'), 'declaration': 'missing_feature', 'library': 'python'}, {'weblog': 'fastapi', 'excluded_library_version': CustomSpec('>=2.5.0'), 'declaration': 'missing_feature', 'library': 'python'}], 'tests/appsec/iast/sink': [{'declaration': 'missing_feature', 'library': 'python'}], 'tests/appsec/iast': [{'excluded_library_version': CustomSpec('>=2.1.0'), 'declaration': 'missing_feature', 'library': 'python'}]}


    def test_all_missing_feature(self):
        manifest = Manifest("python", Version("3.12.0"), "django-poc", path="tests/test_the_test/manifests/manifests_parser_test/")
        assert manifest.get_declarations("tests/apm_tracing_e2e/test_otel.py::Test_Otel_Span::test_function") == [(TestDeclaration.MISSING_FEATURE, 'missing /e2e_otel_span endpoint on weblog')]

    def test_variant_conditions(self):
        manifest = Manifest("python", Version("3.12.0"), "django-poc", path="tests/test_the_test/manifests/manifests_parser_test/")
        assert manifest.get_declarations("tests/apm_tracing_e2e/test_otel.py::Test_API_Security_RC_ASM_DD_scanners::test_function") == []
        assert manifest.get_declarations("tests/appsec/api_security/test_endpoint_discovery.py::Test_Endpoint_Discovery::test_function") == []
        assert manifest.get_declarations("tests/appsec/api_security/test_schemas.py::Test_Endpoint_Discovery::test_function") == []

    def test_variant_star(self):
        manifest = Manifest("python", Version("3.12.0"), "some-variant", path="tests/test_the_test/manifests/manifests_parser_test/")
        assert manifest.get_declarations("tests/appsec/api_security/test_endpoint_discovery.py::Test_Endpoint_Discovery") == [(TestDeclaration.MISSING_FEATURE, None)]

    def test_variant_star(self):
        manifest = Manifest("python", Version("2.4.0"), "some-variant", path="tests/test_the_test/manifests/manifests_parser_test/")
        assert manifest.get_declarations("tests/appsec/api_security/test_api_security_rc.py::Test_API_Security_RC_ASM_DD_scanners") == [(TestDeclaration.MISSING_FEATURE, None)]
        assert manifest.get_declarations("tests/appsec/api_security/test_schemas.py::Test_Scanners") == []
        assert manifest.get_declarations("tests/appsec/iast/sink/file.py::Class::function") == [(TestDeclaration.MISSING_FEATURE, None)]

