import inspect
import os
import re
from functools import partial
import enum

import pytest
import semantic_version as semver

from utils._context.core import context

_jira_ticket_pattern = re.compile(r"([A-Z]{3,}-\d+)(, [A-Z]{3,}-\d+)*")


def configure(config: pytest.Config):
    pass  # nothing to do right now


class DecoratorType(enum.Enum):
    BUG = "bug"
    FLAKY = "flaky"
    IRRELEVANT = "irrelevant"
    MISSING_FEATURE = "missing_feature"
    INCOMPLETE_TEST_APP = "incomplete_test_app"


# semver module offers two spec engine :
# 1. SimpleSpec : not a good fit because it does not allows OR clause
# 2. NpmSpec : not a good fit because it disallow prerelease version by default (6.0.0-pre is not in ">=5.0.0")
# So we use a custom one, based on NPM spec, allowing pre-release versions
class CustomParser(semver.NpmSpec.Parser):
    @classmethod
    def range(cls, operator, target):
        return semver.base.Range(operator, target, prerelease_policy=semver.base.Range.PRERELEASE_ALWAYS)


class CustomSpec(semver.NpmSpec):
    Parser = CustomParser


_MANIFEST_ERROR_MESSAGE = "Please use manifest file, See docs/edit/manifest.md"


def is_jira_ticket(reason: str):
    return reason is not None and _jira_ticket_pattern.fullmatch(reason)


def _ensure_jira_ticket_as_reason(item, reason: str):

    if not is_jira_ticket(reason):
        path = inspect.getfile(item)
        rel_path = os.path.relpath(path)

        if inspect.isclass(item):
            nodeid = f"{rel_path}::{item.__name__}"
        else:
            nodeid = f"{rel_path}::{item.__qualname__}"

        pytest.exit(f"Please set a jira ticket for {nodeid}, instead of reason: {reason}", 1)


def _add_pytest_marker(item, reason, marker):
    if inspect.isfunction(item) or inspect.isclass(item):
        if not hasattr(item, "pytestmark"):
            item.pytestmark = []

        item.pytestmark.append(marker(reason=reason))
    else:
        raise ValueError(f"Unexpected skipped object: {item}")

    return item


def _expected_to_fail(condition=None, library=None, weblog_variant=None):
    if condition is False:
        return False

    if weblog_variant is not None and weblog_variant != context.weblog_variant:
        return False

    if library is not None:
        if library not in (
            "cpp",
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


def _decorator(marker, decorator_type, condition, library, weblog_variant, reason, function_or_class):
    expected_to_fail = _expected_to_fail(library=library, weblog_variant=weblog_variant, condition=condition)

    if inspect.isclass(function_or_class):
        assert condition is not None or (library is None and weblog_variant is None), _MANIFEST_ERROR_MESSAGE

    if decorator_type in (DecoratorType.BUG, DecoratorType.FLAKY):
        _ensure_jira_ticket_as_reason(function_or_class, reason)

    full_reason = decorator_type.value if reason is None else f"{decorator_type.value} ({reason})"
    if not expected_to_fail:
        return function_or_class
    return _add_pytest_marker(function_or_class, full_reason, marker)


def missing_feature(condition=None, library=None, weblog_variant=None, reason=None, force_skip: bool = False):
    """decorator, allow to mark a test function/class as missing"""
    marker = pytest.mark.skip if force_skip else pytest.mark.xfail
    return partial(_decorator, marker, DecoratorType.MISSING_FEATURE, condition, library, weblog_variant, reason)


def incomplete_test_app(condition=None, library=None, weblog_variant=None, reason=None):
    """Decorator, allow to mark a test function/class as not compatible with the tested application"""
    return partial(
        _decorator, pytest.mark.xfail, DecoratorType.INCOMPLETE_TEST_APP, condition, library, weblog_variant, reason
    )


def irrelevant(condition=None, library=None, weblog_variant=None, reason=None):
    """decorator, allow to mark a test function/class as not relevant"""
    return partial(_decorator, pytest.mark.skip, DecoratorType.IRRELEVANT, condition, library, weblog_variant, reason)


def bug(condition=None, library=None, weblog_variant=None, reason=None, force_skip: bool = False):
    """Decorator, allow to mark a test function/class as an known bug.
    The test is executed, and if it passes, and warning is reported
    """
    marker = pytest.mark.skip if force_skip else pytest.mark.xfail
    return partial(_decorator, marker, DecoratorType.BUG, condition, library, weblog_variant, reason)


def flaky(condition=None, library=None, weblog_variant=None, reason=None):
    """Decorator, allow to mark a test function/class as a known bug, and skip it"""
    return partial(_decorator, pytest.mark.skip, DecoratorType.FLAKY, condition, library, weblog_variant, reason)


def released(
    cpp=None,
    dotnet=None,
    golang=None,
    java=None,
    nodejs=None,
    php=None,
    python=None,
    python_otel=None,
    nodejs_otel=None,
    ruby=None,
    agent=None,
    dd_apm_inject=None,
    k8s_cluster_agent=None,
):
    """Class decorator, allow to mark a test class with a version number of a component"""

    def wrapper(test_class):
        if not inspect.isclass(test_class):
            raise TypeError(f"{test_class} is not a class")

        def compute_declaration(only_for_library, component_name, declaration, tested_version):
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

            if declaration.startswith(("missing_feature", "bug", "flaky", "irrelevant", "incomplete_test_app")):
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


def rfc(link):
    def wrapper(item):
        return item

    return wrapper


def _resolve_declaration(released_declaration):
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
