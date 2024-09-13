import inspect
import os
import re

import pytest
import semantic_version as semver

from utils._context.core import context

# bug: APPSEC-51509

_jira_ticket_pattern = re.compile(r"([A-Z]{3,}-\d+)(, [A-Z]{3,}-\d+)*")

_allow_no_jira_ticket_for_bugs: list[str] = []


def configure(config: pytest.Config):
    _allow_no_jira_ticket_for_bugs.extend(config.inicfg["allow_no_jira_ticket_for_bugs"])


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


def _ensure_jira_ticket_as_reason(item, reason: str | None):

    if reason is None or not _jira_ticket_pattern.fullmatch(reason):
        path = inspect.getfile(item)
        rel_path = os.path.relpath(path)

        if inspect.isclass(item):
            nodeid = f"{rel_path}::{item.__name__}"
        else:
            nodeid = f"{rel_path}::{item.__qualname__}"

        for allowed_nodeid in _allow_no_jira_ticket_for_bugs:
            if nodeid.startswith(allowed_nodeid):
                return

        pytest.exit(f"Please set a jira ticket for {nodeid}, instead of reason: {reason}", 1)


def _get_skipped_item(item, skip_reason):
    if inspect.isfunction(item) or inspect.isclass(item):
        if not hasattr(item, "pytestmark"):
            setattr(item, "pytestmark", [])

        item.pytestmark.append(pytest.mark.skip(reason=skip_reason))

    else:
        raise ValueError(f"Unexpected skipped object: {item}")

    return item


def _get_expected_failure_item(item, skip_reason):
    if inspect.isfunction(item) or inspect.isclass(item):
        if not hasattr(item, "pytestmark"):
            setattr(item, "pytestmark", [])

        item.pytestmark.append(pytest.mark.xfail(reason=skip_reason))
    else:
        raise ValueError(f"Unexpected skipped object: {item}")

    return item


def _should_skip(condition=None, library=None, weblog_variant=None):
    if condition is not None and not condition:
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


def missing_feature(condition: bool = None, library=None, weblog_variant=None, reason=None):
    """decorator, allow to mark a test function/class as missing"""

    skip = _should_skip(library=library, weblog_variant=weblog_variant, condition=condition)

    def decorator(function_or_class):

        if inspect.isclass(function_or_class):
            assert condition is not None or (library is None and weblog_variant is None), _MANIFEST_ERROR_MESSAGE

        if not skip:
            return function_or_class

        full_reason = "missing_feature" if reason is None else f"missing_feature ({reason})"

        return _get_expected_failure_item(function_or_class, full_reason)

    return decorator


def irrelevant(condition=None, library=None, weblog_variant=None, reason=None):
    """decorator, allow to mark a test function/class as not relevant"""

    skip = _should_skip(library=library, weblog_variant=weblog_variant, condition=condition)

    def decorator(function_or_class):

        if inspect.isclass(function_or_class):
            assert condition is not None, _MANIFEST_ERROR_MESSAGE

        if not skip:
            return function_or_class

        full_reason = "irrelevant" if reason is None else f"irrelevant ({reason})"
        return _get_skipped_item(function_or_class, full_reason)

    return decorator


def bug(condition=None, library=None, weblog_variant=None, reason=None):
    """
    Decorator, allow to mark a test function/class as an known bug.
    The test is executed, and if it passes, and warning is reported
    """

    expected_to_fail = _should_skip(library=library, weblog_variant=weblog_variant, condition=condition)

    def decorator(function_or_class):

        if inspect.isclass(function_or_class):
            assert condition is not None, _MANIFEST_ERROR_MESSAGE

        _ensure_jira_ticket_as_reason(function_or_class, reason)

        if not expected_to_fail:
            return function_or_class

        full_reason = "bug" if reason is None else f"bug ({reason})"
        return _get_expected_failure_item(function_or_class, full_reason)

    return decorator


def flaky(condition=None, library=None, weblog_variant=None, reason=None):
    """Decorator, allow to mark a test function/class as a known bug, and skip it"""

    skip = _should_skip(library=library, weblog_variant=weblog_variant, condition=condition)

    def decorator(function_or_class):

        if inspect.isclass(function_or_class):
            assert condition is not None, _MANIFEST_ERROR_MESSAGE

        _ensure_jira_ticket_as_reason(function_or_class, reason)

        if not skip:
            return function_or_class

        full_reason = "flaky" if reason is None else f"flaky ({reason})"
        return _get_skipped_item(function_or_class, full_reason)

    return decorator


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

            if (
                declaration.startswith("missing_feature")
                or declaration.startswith("flaky")
                or declaration.startswith("bug")
                or declaration.startswith("irrelevant")
            ):
                return declaration

            # declaration must be now a version number
            if declaration.startswith("v"):
                if tested_version >= declaration:
                    return None
            else:
                if semver.Version(str(tested_version)) in CustomSpec(declaration):
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
        ]

        skip_reasons = [reason for reason in skip_reasons if reason is not None]  # remove None

        if len(skip_reasons) != 0:
            # look for any flaky or irrelevant, meaning we don't execute the test at all
            for reason in skip_reasons:
                if reason.startswith("flaky"):
                    _ensure_jira_ticket_as_reason(test_class, reason[7:-1])
                    return _get_skipped_item(test_class, reason)

                elif reason.startswith("irrelevant"):
                    return _get_skipped_item(test_class, reason)

                else:
                    # Otherwise, it's either bug, or missing_feature. Take the first one
                    if reason.startswith("bug"):
                        _ensure_jira_ticket_as_reason(test_class, reason[5:-1])

                    return _get_expected_failure_item(test_class, reason)

        return test_class

    return wrapper


def rfc(link):
    def wrapper(item):
        return item

    return wrapper


def _resolve_declaration(released_declaration):
    """ if the declaration is a dict, resolve it regarding the tested weblog """
    if isinstance(released_declaration, str):
        return released_declaration

    if isinstance(released_declaration, dict):
        if context.weblog_variant in released_declaration:
            return released_declaration[context.weblog_variant]

        if "*" in released_declaration:
            return released_declaration["*"]

        return None

    raise TypeError(f"Unsuported release info: {released_declaration}")
