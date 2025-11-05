import inspect
import os
import re
from functools import partial
import enum
from types import FunctionType, MethodType
from typing import Any

import pytest
import semantic_version as semver

from utils._context.core import context
from utils._context.component_version import Version


_jira_ticket_pattern = re.compile(r"([A-Z]{3,}-\d+)(, [A-Z]{3,}-\d+)*")


def configure(config: pytest.Config):
    pass  # nothing to do right now


class _TestDeclaration(enum.StrEnum):
    BUG = "bug"
    FLAKY = "flaky"
    INCOMPLETE_TEST_APP = "incomplete_test_app"
    IRRELEVANT = "irrelevant"
    MISSING_FEATURE = "missing_feature"


SKIP_DECLARATIONS = (
    _TestDeclaration.MISSING_FEATURE,
    _TestDeclaration.BUG,
    _TestDeclaration.FLAKY,
    _TestDeclaration.IRRELEVANT,
    _TestDeclaration.INCOMPLETE_TEST_APP,
)


# semver module offers two spec engine :
# 1. SimpleSpec : not a good fit because it does not allows OR clause
# 2. NpmSpec : not a good fit because it disallow prerelease version by default (6.0.0-pre is not in ">=5.0.0")
# So we use a custom one, based on NPM spec, allowing pre-release versions
class CustomParser(semver.NpmSpec.Parser):
    @classmethod
    def range(cls, operator: Any, target: Any) -> semver.base.Range:  # noqa: ANN401
        return semver.base.Range(operator, target, prerelease_policy=semver.base.Range.PRERELEASE_ALWAYS)


class CustomSpec(semver.NpmSpec):
    Parser = CustomParser


_MANIFEST_ERROR_MESSAGE = "Please use manifest file, See docs/edit/manifest.md"


def parse_skip_declaration(skip_declaration: str) -> tuple[_TestDeclaration, str | None]:
    """Parse a skip declaration
    returns the corresponding TestDeclaration, and if it exists, de declaration details
    """

    if not skip_declaration.startswith(SKIP_DECLARATIONS):
        raise ValueError(f"The declaration must be a skip declaration: {skip_declaration}")

    match = re.match(r"^(\w+)( \((.*)\))?$", skip_declaration)
    assert match is not None
    declaration, _, declaration_details = match.groups()

    return _TestDeclaration(declaration), declaration_details


def _is_jira_ticket(declaration_details: str | None):
    return declaration_details is not None and _jira_ticket_pattern.fullmatch(declaration_details)


def _ensure_jira_ticket_as_reason(item: type[Any] | FunctionType | MethodType, declaration_details: str | None):
    if not _is_jira_ticket(declaration_details):
        path = inspect.getfile(item)
        rel_path = os.path.relpath(path)
        nodeid = f"{rel_path}::{item.__name__ if inspect.isclass(item) else item.__qualname__}"

        pytest.exit(f"Please set a jira ticket for {nodeid}, instead of reason: {declaration_details}", 1)


def add_pytest_marker(
    item: pytest.Module | FunctionType | MethodType,
    declaration: _TestDeclaration,
    declaration_details: str | None,
    *,
    force_skip: bool = False,
    reruns: int | None = None,
    reruns_delay: int | None = None,
):
    if not inspect.isfunction(item) and not inspect.isclass(item) and not isinstance(item, pytest.Module):
        raise ValueError(f"Unexpected skipped object: {item}")

    if declaration in (_TestDeclaration.BUG, _TestDeclaration.FLAKY):
        _ensure_jira_ticket_as_reason(item, declaration_details)

    reason = declaration.value if declaration_details is None else f"{declaration.value} ({declaration_details})"

    if isinstance(item, pytest.Module):
        add_marker = item.add_marker
    else:
        if not hasattr(item, "pytestmark"):
            item.pytestmark = []  # type: ignore[attr-defined, union-attr]

        add_marker = item.pytestmark.append  # type: ignore[union-attr]

    # For flaky tests with reruns specified, use pytest.mark.flaky from pytest-rerunfailures
    if declaration == _TestDeclaration.FLAKY and reruns is not None:
        flaky_kwargs = {"reruns": reruns}
        if reruns_delay is not None:
            flaky_kwargs["reruns_delay"] = reruns_delay
        add_marker(pytest.mark.flaky(**flaky_kwargs))
        # Add a custom marker to indicate this is a flaky test with retries (for reporting purposes)
        add_marker(pytest.mark.flaky_with_retries(reruns=reruns, reruns_delay=reruns_delay))
    elif force_skip or declaration in (_TestDeclaration.IRRELEVANT, _TestDeclaration.FLAKY):
        marker = pytest.mark.skip
        add_marker(marker(reason=reason))
    else:
        marker = pytest.mark.xfail
        add_marker(marker(reason=reason))

    add_marker(pytest.mark.declaration(declaration=declaration.value, details=declaration_details))

    return item


def _expected_to_fail(condition: bool | None = None, library: str | None = None, weblog_variant: str | None = None):
    if condition is False:
        return False

    if weblog_variant is not None and weblog_variant != context.weblog_variant:
        return False

    if library is not None:
        if library not in (
            "cpp",
            "cpp_httpd",
            "cpp_nginx",
            "dotnet",
            "golang",
            "java",
            "nodejs",
            "python",
            "php",
            "ruby",
            "java_otel",
            "python_otel",
            "nodejs_otel",
            "python_lambda",
            "rust",
        ):
            raise ValueError(f"Unknown library: {library}")

        if context.library != library:
            return False

    return True


def _decorator(
    function_or_class: type[Any] | FunctionType | MethodType,
    declaration: _TestDeclaration,
    condition: bool | None,
    library: str | None,
    weblog_variant: str | None,
    declaration_details: str | None,
    *,
    force_skip: bool = False,
    reruns: int | None = None,
    reruns_delay: int | None = None,
):
    expected_to_fail = _expected_to_fail(library=library, weblog_variant=weblog_variant, condition=condition)

    if inspect.isclass(function_or_class):
        assert condition is not None or (library is None and weblog_variant is None), _MANIFEST_ERROR_MESSAGE

    if not expected_to_fail:
        return function_or_class

    return add_pytest_marker(
        function_or_class,
        declaration=declaration,
        declaration_details=declaration_details,
        force_skip=force_skip,
        reruns=reruns,
        reruns_delay=reruns_delay,
    )


def missing_feature(
    condition: bool | None = None,
    library: str | None = None,
    weblog_variant: str | None = None,
    reason: str | None = None,
    *,
    force_skip: bool = False,
):
    """decorator, allow to mark a test function/class as missing"""
    return partial(
        _decorator,
        declaration=_TestDeclaration.MISSING_FEATURE,
        condition=condition,
        library=library,
        weblog_variant=weblog_variant,
        declaration_details=reason,
        force_skip=force_skip,
    )


def incomplete_test_app(
    condition: bool | None = None,
    library: str | None = None,
    weblog_variant: str | None = None,
    reason: str | None = None,
):
    """Decorator, allow to mark a test function/class as not compatible with the tested application"""
    return partial(
        _decorator,
        declaration=_TestDeclaration.INCOMPLETE_TEST_APP,
        condition=condition,
        library=library,
        weblog_variant=weblog_variant,
        declaration_details=reason,
    )


def irrelevant(
    condition: bool | None = None,
    library: str | None = None,
    weblog_variant: str | None = None,
    reason: str | None = None,
):
    """decorator, allow to mark a test function/class as not relevant"""
    return partial(
        _decorator,
        declaration=_TestDeclaration.IRRELEVANT,
        condition=condition,
        library=library,
        weblog_variant=weblog_variant,
        declaration_details=reason,
    )


def bug(
    condition: bool | None = None,
    library: str | None = None,
    weblog_variant: str | None = None,
    *,
    reason: str,
    force_skip: bool = False,
):
    """Decorator, allow to mark a test function/class as an known bug.
    The test is executed, and if it passes, and warning is reported
    """
    return partial(
        _decorator,
        declaration=_TestDeclaration.BUG,
        condition=condition,
        library=library,
        weblog_variant=weblog_variant,
        declaration_details=reason,
        force_skip=force_skip,
    )


def flaky(
    condition: bool | None = None,
    library: str | None = None,
    weblog_variant: str | None = None,
    *,
    reason: str,
    reruns: int | None = None,
    reruns_delay: int | None = None,
):
    """Decorator, allow to mark a test function/class as flaky.

    Args:
        condition: Boolean condition to determine if the test should be marked as flaky
        library: Specific library this flaky behavior applies to
        weblog_variant: Specific weblog variant this flaky behavior applies to
        reason: JIRA ticket reference (required)
        reruns: Number of times to rerun the test if it fails (optional)
        reruns_delay: Delay in seconds between reruns (optional)

    If reruns is not specified, the test will be skipped (default behavior).
    If reruns is specified, the test will be executed and retried up to 'reruns' times on failure.

    """
    return partial(
        _decorator,
        declaration=_TestDeclaration.FLAKY,
        condition=condition,
        library=library,
        weblog_variant=weblog_variant,
        declaration_details=reason,
        reruns=reruns,
        reruns_delay=reruns_delay,
    )


def released(
    cpp: str | None = None,
    cpp_httpd: str | None = None,
    cpp_nginx: str | None = None,
    dotnet: str | None = None,
    golang: str | None = None,
    java: str | None = None,
    nodejs: str | None = None,
    php: str | None = None,
    python: str | None = None,
    python_otel: str | None = None,
    nodejs_otel: str | None = None,
    ruby: str | None = None,
    rust: str | None = None,
    agent: str | None = None,
    dd_apm_inject: str | None = None,
    k8s_cluster_agent: str | None = None,
    python_lambda: str | None = None,
):
    """Class decorator, allow to mark a test class with a version number of a component"""

    def wrapper(test_class: type[Any]):
        if not inspect.isclass(test_class):
            raise TypeError(f"{test_class} is not a class")

        def compute_declaration(
            only_for_library: str, component_name: str, full_declaration: str | None, tested_version: Version
        ) -> tuple[str | None, str | None]:
            if full_declaration is None:
                # nothing declared
                return None, None

            if only_for_library != "*":
                # this declaration is applied only if the tested library is <only_for_library>
                if context.library != only_for_library:
                    # the tested library is not concerned by this declaration
                    return None, None

            full_declaration = _resolve_declaration(full_declaration)

            if full_declaration is None:
                return None, None

            if full_declaration.startswith(SKIP_DECLARATIONS):
                return parse_skip_declaration(full_declaration)

            # declaration must be now a version number
            if full_declaration.startswith("v"):
                if tested_version >= full_declaration:
                    return None, None
            elif semver.Version(str(tested_version)) in CustomSpec(full_declaration):
                return None, None

            return (
                _TestDeclaration.MISSING_FEATURE,
                f"declared version for {component_name} is {full_declaration}, tested version is {tested_version}",
            )

        skip_reasons = [
            compute_declaration("cpp", "cpp", cpp, context.library.version),
            compute_declaration("cpp_httpd", "cpp_httpd", cpp_httpd, context.library.version),
            compute_declaration("cpp_nginx", "cpp_nginx", cpp_nginx, context.library.version),
            compute_declaration("dotnet", "dotnet", dotnet, context.library.version),
            compute_declaration("golang", "golang", golang, context.library.version),
            compute_declaration("java", "java", java, context.library.version),
            compute_declaration("nodejs", "nodejs", nodejs, context.library.version),
            compute_declaration("nodejs_otel", "nodejs_otel", nodejs_otel, context.library.version),
            compute_declaration("php", "php", php, context.library.version),
            compute_declaration("python", "python", python, context.library.version),
            compute_declaration("python_otel", "python_otel", python_otel, context.library.version),
            compute_declaration("python_lambda", "python_lambda", python_lambda, context.library.version),
            compute_declaration("ruby", "ruby", ruby, context.library.version),
            compute_declaration("rust", "rust", rust, context.library.version),
            compute_declaration("*", "agent", agent, context.agent_version),
            compute_declaration("*", "dd_apm_inject", dd_apm_inject, context.dd_apm_inject_version),
            compute_declaration("*", "k8s_cluster_agent", k8s_cluster_agent, context.k8s_cluster_agent_version),
        ]

        for declaration, declaration_details in skip_reasons:
            if declaration is not None:
                return add_pytest_marker(test_class, _TestDeclaration(declaration), declaration_details)

        return test_class

    return wrapper


def rfc(link: str):  # noqa: ARG001
    def wrapper(item: type[Any]):
        return item

    return wrapper


def _resolve_declaration(released_declaration: str | dict[str, str]) -> str | None:
    """If the declaration is a dict, resolve it regarding the tested weblog"""
    if isinstance(released_declaration, str):
        return released_declaration

    if isinstance(released_declaration, dict):
        if context.weblog_variant in released_declaration:
            return released_declaration[context.weblog_variant]

        if "*" in released_declaration:
            return released_declaration["*"]

        return None

    raise TypeError(f"Unsuported release info: {released_declaration}")
