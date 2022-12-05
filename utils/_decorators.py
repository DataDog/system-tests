import inspect
import pytest

from utils._context.core import context


def _get_skipped_item(item, skip_reason):

    if not inspect.isfunction(item) and not inspect.isclass(item):
        raise Exception(f"Unexpected skipped object: {item}")

    if not hasattr(item, "pytestmark"):
        setattr(item, "pytestmark", [])

    item.pytestmark.append(pytest.mark.skip(reason=skip_reason))

    return item


def _get_expected_failure_item(item, skip_reason):

    if not inspect.isfunction(item) and not inspect.isclass(item):
        raise Exception(f"Unexpected skipped object: {item}")

    if not hasattr(item, "pytestmark"):
        setattr(item, "pytestmark", [])

    item.pytestmark.append(pytest.mark.xfail(reason=skip_reason))

    return item


def _should_skip(condition=None, library=None, weblog_variant=None):
    if condition is not None and not condition:
        return False

    if weblog_variant is not None and weblog_variant != context.weblog_variant:
        return False

    if library is not None and context.library != library:
        return False

    return True


def missing_feature(condition=None, library=None, weblog_variant=None, reason=None):
    """decorator, allow to mark a test function/class as missing"""

    skip = _should_skip(library=library, weblog_variant=weblog_variant, condition=condition)

    def decorator(function_or_class):

        if not skip:
            return function_or_class

        full_reason = "missing feature" if reason is None else f"missing feature: {reason}"
        return _get_expected_failure_item(function_or_class, full_reason)

    return decorator


def irrelevant(condition=None, library=None, weblog_variant=None, reason=None):
    """decorator, allow to mark a test function/class as not relevant"""

    skip = _should_skip(library=library, weblog_variant=weblog_variant, condition=condition)

    def decorator(function_or_class):

        if not skip:
            return function_or_class

        full_reason = "not relevant" if reason is None else f"not relevant: {reason}"
        return _get_skipped_item(function_or_class, full_reason)

    return decorator


def bug(condition=None, library=None, weblog_variant=None, reason=None):
    """
    Decorator, allow to mark a test function/class as an known bug.
    The test is executed, and if it passes, and warning is reported
    """

    expected_to_fail = _should_skip(library=library, weblog_variant=weblog_variant, condition=condition)

    def decorator(function_or_class):

        if not expected_to_fail:
            return function_or_class

        full_reason = "known bug" if reason is None else f"known bug: {reason}"
        return _get_expected_failure_item(function_or_class, full_reason)

    return decorator


def flaky(condition=None, library=None, weblog_variant=None, reason=None):
    """Decorator, allow to mark a test function/class as a known bug, and skip it"""

    skip = _should_skip(library=library, weblog_variant=weblog_variant, condition=condition)

    def decorator(function_or_class):

        if not skip:
            return function_or_class

        full_reason = "known bug (flaky)" if reason is None else f"known bug (flaky): {reason}"
        return _get_skipped_item(function_or_class, full_reason)

    return decorator


def released(
    cpp=None, dotnet=None, golang=None, java=None, nodejs=None, php=None, python=None, ruby=None, php_appsec=None
):
    """Class decorator, allow to mark a test class with a version number of a component"""

    def wrapper(test_class):
        def compute_requirement(tested_library, component_name, released_version, tested_version):
            if context.library != tested_library or released_version is None:
                return None

            if not hasattr(test_class, "__released__"):
                setattr(test_class, "__released__", {})

            if component_name in test_class.__released__:
                raise ValueError(f"A {component_name}' version for {test_class.__name__} has been declared twice")

            released_version = _compute_released_version(released_version)

            test_class.__released__[component_name] = released_version

            if released_version == "?":
                return "missing feature: release not yet planned"

            if released_version.startswith("not relevant"):
                raise Exception("TODO remove this test, it should never happen")

            if tested_version >= released_version:
                return None

            return (
                f"missing feature for {component_name}: "
                f"release version is {released_version}, tested version is {tested_version}"
            )

        skip_reasons = [
            compute_requirement("cpp", "cpp", cpp, context.library.version),
            compute_requirement("dotnet", "dotnet", dotnet, context.library.version),
            compute_requirement("golang", "golang", golang, context.library.version),
            compute_requirement("java", "java", java, context.library.version),
            compute_requirement("nodejs", "nodejs", nodejs, context.library.version),
            compute_requirement("php", "php_appsec", php_appsec, context.php_appsec),
            compute_requirement("php", "php", php, context.library.version),
            compute_requirement("python", "python", python, context.library.version),
            compute_requirement("ruby", "ruby", ruby, context.library.version),
        ]

        skip_reasons = [reason for reason in skip_reasons if reason is not None]  # remove None

        if len(skip_reasons) != 0:
            return _get_expected_failure_item(test_class, skip_reasons[0])  # use the first skip reason found

        return test_class

    return wrapper


def rfc(link):
    def wrapper(item):
        setattr(item, "__rfc__", link)
        return item

    return wrapper


scenario = pytest.mark.scenario


def _compute_released_version(released_version):
    if isinstance(released_version, str):
        return released_version

    if isinstance(released_version, dict):
        if context.weblog_variant in released_version:
            return released_version[context.weblog_variant]

        if "*" in released_version:
            return released_version["*"]

        return None

    raise TypeError(f"Unsuported release info: {released_version}")
