from collections import defaultdict
import inspect
import os
import pytest

from utils._context.core import context


# temp code, for manifest file migrations
_released_declarations = defaultdict(dict)


def _fill_released_declaration(klass, weblog_variant, reason):
    """temp code for manifest migrations"""

    if not inspect.isclass(klass) or weblog_variant is None:
        return

    file = os.path.relpath(inspect.getfile(klass))
    nodeid = f"{file}::{klass.__name__}"
    if weblog_variant not in []:
        if weblog_variant in _released_declarations[nodeid]:
            assert (
                _released_declarations[nodeid][weblog_variant] == reason
            ), f"{_released_declarations[nodeid][weblog_variant]} VS {reason} for {klass}"
        _released_declarations[nodeid][weblog_variant] = reason


def _get_skipped_item(item, skip_reason):

    if not inspect.isfunction(item) and not inspect.isclass(item):
        raise ValueError(f"Unexpected skipped object: {item}")

    if not hasattr(item, "pytestmark"):
        setattr(item, "pytestmark", [])

    item.pytestmark.append(pytest.mark.skip(reason=skip_reason))

    return item


def _get_expected_failure_item(item, skip_reason):

    if not inspect.isfunction(item) and not inspect.isclass(item):
        raise ValueError(f"Unexpected skipped object: {item}")

    if not hasattr(item, "pytestmark"):
        setattr(item, "pytestmark", [])

    item.pytestmark.append(pytest.mark.xfail(reason=skip_reason))

    return item


def _should_skip(condition=None, library=None, weblog_variant=None):
    if condition is not None and not condition:
        return False

    if weblog_variant is not None and weblog_variant != context.weblog_variant:
        return False

    if library is not None:
        if library not in ("cpp", "dotnet", "golang", "java", "nodejs", "python", "php", "ruby", "python_http"):
            raise ValueError(f"Unknown library: {library}")

        if context.library != library:
            return False

    return True


def missing_feature(condition=None, library=None, weblog_variant=None, reason=None):
    """decorator, allow to mark a test function/class as missing"""

    skip = _should_skip(library=library, weblog_variant=weblog_variant, condition=condition)

    def decorator(function_or_class):

        _fill_released_declaration(
            function_or_class, weblog_variant, "missing_feature" if reason is None else f"missing_feature ({reason})"
        )

        if not skip:
            return function_or_class

        full_reason = "missing_feature" if reason is None else f"missing_feature: {reason}"

        return _get_expected_failure_item(function_or_class, full_reason)

    return decorator


def irrelevant(condition=None, library=None, weblog_variant=None, reason=None):
    """decorator, allow to mark a test function/class as not relevant"""

    skip = _should_skip(library=library, weblog_variant=weblog_variant, condition=condition)

    def decorator(function_or_class):

        _fill_released_declaration(
            function_or_class, weblog_variant, "irrelevant" if reason is None else f"irrelevant ({reason})"
        )

        if not skip:
            return function_or_class

        full_reason = "irrelevant" if reason is None else f"irrelevant: {reason}"
        return _get_skipped_item(function_or_class, full_reason)

    return decorator


def bug(condition=None, library=None, weblog_variant=None, reason=None):
    """
    Decorator, allow to mark a test function/class as an known bug.
    The test is executed, and if it passes, and warning is reported
    """

    expected_to_fail = _should_skip(library=library, weblog_variant=weblog_variant, condition=condition)

    def decorator(function_or_class):

        _fill_released_declaration(function_or_class, weblog_variant, "bug" if reason is None else f"bug ({reason})")

        if not expected_to_fail:
            return function_or_class

        full_reason = "known bug" if reason is None else f"known bug: {reason}"
        return _get_expected_failure_item(function_or_class, full_reason)

    return decorator


def flaky(condition=None, library=None, weblog_variant=None, reason=None):
    """Decorator, allow to mark a test function/class as a known bug, and skip it"""

    skip = _should_skip(library=library, weblog_variant=weblog_variant, condition=condition)

    def decorator(function_or_class):

        _fill_released_declaration(
            function_or_class, weblog_variant, "flaky" if reason is None else f"flaky ({reason})"
        )

        if not skip:
            return function_or_class

        full_reason = "known bug (flaky)" if reason is None else f"known bug (flaky): {reason}"
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
    ruby=None,
    php_appsec=None,
    agent=None,
    _is_from_manifest=False,
):
    """Class decorator, allow to mark a test class with a version number of a component"""

    if not _is_from_manifest:
        if nodejs is not None or python is not None or dotnet is not None or golang is not None:
            raise ValueError("Please use manifest file for version declaration")

    def wrapper(test_class):
        if not inspect.isclass(test_class):
            raise TypeError("@released must be used only on classes")

        def compute_declaration(only_for_library, component_name, declaration, tested_version):
            if declaration is None:
                # nothing declared
                return None

            if only_for_library != "*":
                # this declaration is applied only if the tested library is <only_for_library>
                if context.library != only_for_library:
                    # the tested library is not concerned by this declaration
                    return None

            if not hasattr(test_class, "__released__"):
                setattr(test_class, "__released__", {})

            if component_name in test_class.__released__:
                raise ValueError(f"A {component_name}' version for {test_class.__name__} has been declared twice")

            # temporary code for manifest migration
            if component_name == context.library.library:
                if isinstance(declaration, str):
                    _fill_released_declaration(test_class, "*", declaration)
                else:
                    for weblog_variant, value in declaration.items():
                        _fill_released_declaration(test_class, weblog_variant, value)

            declaration = _resolve_declaration(declaration)

            test_class.__released__[component_name] = declaration

            if declaration is None:
                return None

            if declaration == "?":  # fix legacy "?" in @released
                declaration = "missing_feature (release not yet planned)"

            if (
                declaration.startswith("missing_feature")
                or declaration.startswith("flaky")
                or declaration.startswith("bug")
                or declaration.startswith("irrelevant")
            ):
                return declaration

            # declaration must be now a version number
            if tested_version >= declaration:
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
            compute_declaration("php", "php_appsec", php_appsec, context.php_appsec),
            compute_declaration("php", "php", php, context.library.version),
            compute_declaration("python", "python", python, context.library.version),
            compute_declaration("python_http", "python_http", python, context.library.version),
            compute_declaration("ruby", "ruby", ruby, context.library.version),
            compute_declaration("*", "agent", agent, context.agent_version),
        ]

        skip_reasons = [reason for reason in skip_reasons if reason is not None]  # remove None

        if len(skip_reasons) != 0:
            # look for any flaky or irrelevant, meaning we don't execute the test at all
            for reason in skip_reasons:
                if reason.startswith("flaky") or reason.startswith("irrelevant"):
                    return _get_skipped_item(test_class, reason)  # use the first skip reason found

                # Otherwise, it's either bug, or missing_feature. Take the first one
                return _get_expected_failure_item(test_class, reason)

        return test_class

    return wrapper


def rfc(link):
    def wrapper(item):
        setattr(item, "__rfc__", link)
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
