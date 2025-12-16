import inspect
import os
import re
from functools import partial
from types import FunctionType, MethodType
from typing import Any

import pytest

from utils.manifest import TestDeclaration
from utils._context.core import context


_jira_ticket_pattern = re.compile(r"([A-Z]{3,}-\d+)(, [A-Z]{3,}-\d+)*")


def configure(config: pytest.Config):
    pass  # nothing to do right now


_MANIFEST_ERROR_MESSAGE = "Please use manifest file, See docs/edit/manifest.md"


def _is_jira_ticket(declaration_details: str | None):
    return declaration_details is not None and _jira_ticket_pattern.fullmatch(declaration_details)


def _ensure_jira_ticket_as_reason(item: type[Any] | FunctionType | MethodType, declaration_details: str | None):
    if isinstance(item, pytest.Function):
        item = item.function
    if not _is_jira_ticket(declaration_details):
        path = inspect.getfile(item)
        rel_path = os.path.relpath(path)
        nodeid = f"{rel_path}::{item.__name__ if inspect.isclass(item) else item.__qualname__}"

        pytest.exit(f"Please set a jira ticket for {nodeid}, instead of reason: {declaration_details}", 1)


def add_pytest_marker(
    item: pytest.Module | pytest.Function | FunctionType | MethodType,
    declaration: TestDeclaration,
    declaration_details: str | None,
    *,
    force_skip: bool = False,
):
    if (
        not inspect.isfunction(item)
        and not inspect.isclass(item)
        and not isinstance(item, pytest.Module)
        and not isinstance(item, pytest.Function)
    ):
        raise ValueError(f"Unexpected skipped object: {item}")

    if declaration in (TestDeclaration.BUG, TestDeclaration.FLAKY):
        _ensure_jira_ticket_as_reason(item, declaration_details)

    if force_skip or declaration in (TestDeclaration.IRRELEVANT, TestDeclaration.FLAKY):
        marker = pytest.mark.skip
    else:
        marker = pytest.mark.xfail

    reason = declaration.value if declaration_details is None else f"{declaration.value} ({declaration_details})"

    if isinstance(item, (pytest.Module, pytest.Function)):
        add_marker = item.add_marker
    else:
        if not hasattr(item, "pytestmark"):
            item.pytestmark = []  # type: ignore[attr-defined, union-attr]

        add_marker = item.pytestmark.append  # type: ignore[union-attr]

    add_marker(marker(reason=reason))
    add_marker(pytest.mark.declaration(declaration=declaration.value, details=declaration_details))

    return item


def _expected_to_fail(condition: bool | None = None, library: str | None = None, weblog_variant: str | None = None):  # noqa: FBT001
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
    *,
    declaration: TestDeclaration,
    condition: bool | None,
    library: str | None,
    weblog_variant: str | None,
    declaration_details: str | None,
    force_skip: bool = False,
):
    expected_to_fail = _expected_to_fail(library=library, weblog_variant=weblog_variant, condition=condition)

    if inspect.isclass(function_or_class):
        assert condition is not None or (library is None and weblog_variant is None), _MANIFEST_ERROR_MESSAGE

    if not expected_to_fail:
        return function_or_class

    return add_pytest_marker(
        function_or_class, declaration=declaration, declaration_details=declaration_details, force_skip=force_skip
    )


def missing_feature(
    condition: bool | None = None,  # noqa: FBT001
    library: str | None = None,
    weblog_variant: str | None = None,
    reason: str | None = None,
    *,
    force_skip: bool = False,
):
    """decorator, allow to mark a test function/class as missing"""
    return partial(
        _decorator,
        declaration=TestDeclaration.MISSING_FEATURE,
        condition=condition,
        library=library,
        weblog_variant=weblog_variant,
        declaration_details=reason,
        force_skip=force_skip,
    )


def incomplete_test_app(
    condition: bool | None = None,  # noqa: FBT001
    library: str | None = None,
    weblog_variant: str | None = None,
    reason: str | None = None,
):
    """Decorator, allow to mark a test function/class as not compatible with the tested application"""
    return partial(
        _decorator,
        declaration=TestDeclaration.INCOMPLETE_TEST_APP,
        condition=condition,
        library=library,
        weblog_variant=weblog_variant,
        declaration_details=reason,
    )


def irrelevant(
    condition: bool | None = None,  # noqa: FBT001
    library: str | None = None,
    weblog_variant: str | None = None,
    reason: str | None = None,
):
    """decorator, allow to mark a test function/class as not relevant"""
    return partial(
        _decorator,
        declaration=TestDeclaration.IRRELEVANT,
        condition=condition,
        library=library,
        weblog_variant=weblog_variant,
        declaration_details=reason,
    )


def bug(
    condition: bool | None = None,  # noqa: FBT001
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
        declaration=TestDeclaration.BUG,
        condition=condition,
        library=library,
        weblog_variant=weblog_variant,
        declaration_details=reason,
        force_skip=force_skip,
    )


def flaky(condition: bool | None = None, library: str | None = None, weblog_variant: str | None = None, *, reason: str):  # noqa: FBT001
    """Decorator, allow to mark a test function/class as a known bug, and skip it"""
    return partial(
        _decorator,
        declaration=TestDeclaration.FLAKY,
        condition=condition,
        library=library,
        weblog_variant=weblog_variant,
        declaration_details=reason,
    )


def rfc(link: str):  # noqa: ARG001
    def wrapper(item: type[Any]):
        return item

    return wrapper
