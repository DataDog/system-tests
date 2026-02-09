from pathlib import Path
import shutil
import tempfile
import textwrap
import pytest
from utils import scenarios
from utils._context.component_version import Version
from utils.manifest import Manifest, SkipDeclaration, TestDeclaration
from utils.manifest._internal.types import SemverRange as CustomSpec
from utils.manifest._internal.validate import assert_nodeids_exist


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

    def test_validate_assume_sorted(self):
        """Test that assume_sorted parameter skips key order validation."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir)
            # Create dummy test files to satisfy nodeid validation
            test_a_path = Path("tests/test_the_test/test_a.py")
            test_b_path = Path("tests/test_the_test/test_b.py")
            test_a_content = textwrap.dedent(
                """\
                class Test_A:
                    def test_method(self): pass
                """
            )
            test_b_content = textwrap.dedent(
                """\
                class Test_B:
                    def test_method(self): pass
                """
            )
            test_a_path.write_text(test_a_content)
            test_b_path.write_text(test_b_content)

            try:
                # Create a manifest file with unsorted keys
                unsorted_manifest = manifest_path / "test.yml"
                manifest_content = textwrap.dedent(
                    """\
                    ---
                    manifest:
                      tests/test_the_test/test_b.py::Test_B: missing_feature
                      tests/test_the_test/test_a.py::Test_A: missing_feature
                    """
                )
                unsorted_manifest.write_text(manifest_content)

                # Validation should fail with assume_sorted=False (default)
                with pytest.raises(AssertionError, match="Key order errors"):
                    Manifest.validate(path=manifest_path, assume_sorted=False)

                # Validation should pass with assume_sorted=True (skips key order check)
                Manifest.validate(path=manifest_path, assume_sorted=True)
            finally:
                # Clean up dummy test files
                if test_a_path.exists():
                    test_a_path.unlink()
                if test_b_path.exists():
                    test_b_path.unlink()


@scenarios.test_the_test
class Test_NodeidValidation:
    """Tests for the assert_nodeids_exist function."""

    def test_existing_nodeids_pass_validation(self):
        """Test that existing nodeids at all levels pass validation."""
        test_dir_str = "tests/test_the_test/nodeid_test_dir_exist"
        test_file_str = f"{test_dir_str}/test_nodeid_validation.py"

        # Create test directory and file with inheritance hierarchy
        test_dir = Path(test_dir_str)
        test_dir.mkdir(exist_ok=True)

        test_file = Path(test_file_str)
        test_file.write_text(
            textwrap.dedent(
                """\
                class GrandParentClass:
                    def grandparent_method(self):
                        pass

                class ParentClass(GrandParentClass):
                    def parent_method(self):
                        pass

                class Test_Child(ParentClass):
                    def own_method(self):
                        pass
                """
            )
        )

        manifest = {
            "manifest": {
                # Directory level nodeid
                test_dir_str: "missing_feature",
                # File level nodeid
                test_file_str: "missing_feature",
                # Class level nodeid
                f"{test_file_str}::Test_Child": "missing_feature",
                # Function level nodeid (own method)
                f"{test_file_str}::Test_Child::own_method": "missing_feature",
                # Function inherited twice (from grandparent)
                f"{test_file_str}::Test_Child::grandparent_method": "missing_feature",
            }
        }

        try:
            errors = assert_nodeids_exist(manifest)
            assert errors == [], f"Expected no errors for existing nodeids but got: {errors}"
        finally:
            shutil.rmtree(test_dir)

    def test_non_existing_nodeids_fail_validation(self):
        """Test that non-existing nodeids at all levels fail validation."""
        test_dir_str = "tests/test_the_test/nodeid_test_dir_nonexist"
        test_file_str = f"{test_dir_str}/test_nodeid_validation.py"

        # Create test directory and file with inheritance hierarchy
        test_dir = Path(test_dir_str)
        test_dir.mkdir(exist_ok=True)

        test_file = Path(test_file_str)
        test_file.write_text(
            textwrap.dedent(
                """\
                class GrandParentClass:
                    def grandparent_method(self):
                        pass

                class ParentClass(GrandParentClass):
                    def parent_method(self):
                        pass

                class Test_Child(ParentClass):
                    def own_method(self):
                        pass
                """
            )
        )

        manifest = {
            "manifest": {
                # Non-existing directory level nodeid
                "tests/test_the_test/nonexistent_dir": "missing_feature",
                # Non-existing file level nodeid
                f"{test_dir_str}/nonexistent_file.py": "missing_feature",
                # Non-existing class level nodeid
                f"{test_file_str}::Test_NonExistent": "missing_feature",
                # Non-existing function level nodeid
                f"{test_file_str}::Test_Child::nonexistent_method": "missing_feature",
                # Non-existing function that looks like inherited (but isn't)
                f"{test_file_str}::Test_Child::fake_grandparent_method": "missing_feature",
            }
        }

        try:
            errors = assert_nodeids_exist(manifest)

            assert len(errors) == 5, f"Expected 5 errors but got {len(errors)}: {errors}"

            # Verify each type of error is present
            assert any("nonexistent_dir" in e and "does not exist" in e for e in errors), f"Missing dir error: {errors}"
            assert any("nonexistent_file.py" in e and "does not exist" in e for e in errors), (
                f"Missing file error: {errors}"
            )
            assert any("does not contain class Test_NonExistent" in e for e in errors), f"Missing class error: {errors}"
            assert any("does not contain function nonexistent_method" in e for e in errors), (
                f"Missing function error: {errors}"
            )
            assert any("does not contain function fake_grandparent_method" in e for e in errors), (
                f"Missing inherited function error: {errors}"
            )
        finally:
            shutil.rmtree(test_dir)
