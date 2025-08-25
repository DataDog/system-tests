import inspect
import os
import re
from functools import partial
import enum
from types import FunctionType, MethodType
from typing import Any
from fnmatch import fnmatchcase

import pytest
import semantic_version as semver

from utils._context.core import context
from utils._context.component_version import Version


_jira_ticket_pattern = re.compile(r"([A-Z]{3,}-\d+)(, [A-Z]{3,}-\d+)*")


def configure(config: pytest.Config):
    pass  # nothing to do right now


class _DecoratorType(enum.StrEnum):
    BUG = "bug"
    FLAKY = "flaky"
    IRRELEVANT = "irrelevant"
    MISSING_FEATURE = "missing_feature"
    INCOMPLETE_TEST_APP = "incomplete_test_app"


SKIP_DECLARATIONS = (
    _DecoratorType.MISSING_FEATURE,
    _DecoratorType.BUG,
    _DecoratorType.FLAKY,
    _DecoratorType.IRRELEVANT,
    _DecoratorType.INCOMPLETE_TEST_APP,
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


def is_jira_ticket(reason: str | None):
    return reason is not None and _jira_ticket_pattern.fullmatch(reason)


def _ensure_jira_ticket_as_reason(item: type[Any] | FunctionType | MethodType, reason: str | None):
    if not is_jira_ticket(reason):
        path = inspect.getfile(item)
        rel_path = os.path.relpath(path)
        nodeid = f"{rel_path}::{item.__name__ if inspect.isclass(item) else item.__qualname__}"

        pytest.exit(f"Please set a jira ticket for {nodeid}, instead of reason: {reason}", 1)


def _add_pytest_marker(item: type[Any] | FunctionType | MethodType, reason: str | None, marker: pytest.MarkDecorator):
    if inspect.isfunction(item) or inspect.isclass(item):
        if not hasattr(item, "pytestmark"):
            item.pytestmark = []  # type: ignore[attr-defined]

        item.pytestmark.append(marker(reason=reason))  # type: ignore[union-attr]
    else:
        raise ValueError(f"Unexpected skipped object: {item}")

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
        ):
            raise ValueError(f"Unknown library: {library}")

        if context.library != library:
            return False

    return True


def _decorator(
    function_or_class: type[Any] | FunctionType | MethodType,
    marker: pytest.MarkDecorator,
    decorator_type: _DecoratorType,
    condition: bool | None,
    library: str | None,
    weblog_variant: str | None,
    reason: str | None,
):
    expected_to_fail = _expected_to_fail(library=library, weblog_variant=weblog_variant, condition=condition)

    if inspect.isclass(function_or_class):
        assert condition is not None or (library is None and weblog_variant is None), _MANIFEST_ERROR_MESSAGE

    if decorator_type in (_DecoratorType.BUG, _DecoratorType.FLAKY):
        _ensure_jira_ticket_as_reason(function_or_class, reason)

    full_reason = decorator_type.value if reason is None else f"{decorator_type.value} ({reason})"
    if not expected_to_fail:
        return function_or_class
    return _add_pytest_marker(function_or_class, full_reason, marker)


def missing_feature(
    condition: bool | None = None,
    library: str | None = None,
    weblog_variant: str | None = None,
    reason: str | None = None,
    *,
    force_skip: bool = False,
):
    """decorator, allow to mark a test function/class as missing"""
    marker = pytest.mark.skip if force_skip else pytest.mark.xfail
    return partial(
        _decorator,
        marker=marker,
        decorator_type=_DecoratorType.MISSING_FEATURE,
        condition=condition,
        library=library,
        weblog_variant=weblog_variant,
        reason=reason,
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
        marker=pytest.mark.xfail,
        decorator_type=_DecoratorType.INCOMPLETE_TEST_APP,
        condition=condition,
        library=library,
        weblog_variant=weblog_variant,
        reason=reason,
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
        marker=pytest.mark.skip,
        decorator_type=_DecoratorType.IRRELEVANT,
        condition=condition,
        library=library,
        weblog_variant=weblog_variant,
        reason=reason,
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
    marker = pytest.mark.skip if force_skip else pytest.mark.xfail
    return partial(
        _decorator,
        marker=marker,
        decorator_type=_DecoratorType.BUG,
        condition=condition,
        library=library,
        weblog_variant=weblog_variant,
        reason=reason,
    )


def flaky(condition: bool | None = None, library: str | None = None, weblog_variant: str | None = None, *, reason: str):
    """Decorator, allow to mark a test function/class as a known bug, and skip it"""
    return partial(
        _decorator,
        marker=pytest.mark.skip,
        decorator_type=_DecoratorType.FLAKY,
        condition=condition,
        library=library,
        weblog_variant=weblog_variant,
        reason=reason,
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
    agent: str | None = None,
    dd_apm_inject: str | None = None,
    k8s_cluster_agent: str | None = None,
):
    """Class decorator, allow to mark a test class with a version number of a component"""

    def wrapper(test_class: type[Any]):
        if not inspect.isclass(test_class):
            raise TypeError(f"{test_class} is not a class")

        def compute_declaration(
            only_for_library: str, component_name: str, declaration: str | None, tested_version: Version
        ):
            if declaration is None:
                # nothing declared
                return None

            if only_for_library != "*":
                # this declaration is applied only if the tested library is <only_for_library>
                if context.library != only_for_library:
                    # the tested library is not concerned by this declaration
                    return None

            declaration = _resolve_declaration(declaration)

            if declaration is None:
                return None

            assert declaration != "?"  # ensure there is no more ? in version declaration

            if declaration.startswith(SKIP_DECLARATIONS):
                return declaration

            # declaration must be now a version number
            if declaration.startswith("v"):
                if tested_version >= declaration:
                    return None
            elif semver.Version(str(tested_version)) in CustomSpec(declaration):
                return None

            return (
                f"missing_feature for {component_name}: "
                f"declared released version is {declaration}, tested version is {tested_version}"
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
            compute_declaration("ruby", "ruby", ruby, context.library.version),
            compute_declaration("*", "agent", agent, context.agent_version),
            compute_declaration("*", "dd_apm_inject", dd_apm_inject, context.dd_apm_inject_version),
            compute_declaration("*", "k8s_cluster_agent", k8s_cluster_agent, context.k8s_cluster_agent_version),
        ]

        skip_reasons = [reason for reason in skip_reasons if reason is not None]  # remove None

        if len(skip_reasons) != 0:
            # look for any flaky or irrelevant, meaning we don't execute the test at all
            for reason in skip_reasons:
                if reason.startswith("flaky"):
                    _ensure_jira_ticket_as_reason(test_class, reason[7:-1])
                    return _add_pytest_marker(test_class, reason, pytest.mark.skip)

                if reason.startswith("irrelevant"):
                    return _add_pytest_marker(test_class, reason, pytest.mark.skip)

                # Otherwise, it's either bug, or missing_feature. Take the first one
                if reason.startswith("bug"):
                    _ensure_jira_ticket_as_reason(test_class, reason[5:-1])

                return _add_pytest_marker(test_class, reason, pytest.mark.xfail)

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

        for variant, declaration in released_declaration.items():
            if fnmatchcase(context.weblog_variant, variant):
                return declaration

        return None # _DecoratorType.MISSING_FEATURE

    raise TypeError(f"Unsuported release info: {released_declaration}")
