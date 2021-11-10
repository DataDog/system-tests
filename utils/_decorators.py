import pytest
import inspect

from utils.tools import logger
from utils._context.core import context


def _get_wrapped_class(klass, skip_reason):

    logger.info(f"{klass.__name__} class, {skip_reason} => skipped")

    @pytest.mark.skip(reason=skip_reason)
    class Test(klass):
        pass

    Test.__doc__ = klass.__doc__

    return Test


def _get_wrapped_function(function, skip_reason):
    logger.info(f"{function.__name__} function, {skip_reason} => skipped")

    @pytest.mark.skip(reason=skip_reason)
    def wrapper(*args, **kwargs):
        return function(*args, **kwargs)

    wrapper.__doc__ = function.__doc__

    return wrapper


def _should_skip(condition=None, library=None, weblog_variant=None):
    if condition is not None and not condition:
        return False

    if weblog_variant is not None and weblog_variant != context.weblog_variant:
        return False

    if library is not None and context.library != library:
        return False

    return True


def missing_feature(condition=None, library=None, weblog_variant=None, reason=None):
    """ decorator, allow to mark a test function/class as missing """

    skip = _should_skip(library=library, weblog_variant=weblog_variant, condition=condition)

    def decorator(function_or_class):

        if not skip:
            return function_or_class

        full_reason = "missing feature" if reason is None else f"missing feature: {reason}"

        if inspect.isfunction(function_or_class):
            return _get_wrapped_function(function_or_class, full_reason)
        elif inspect.isclass(function_or_class):
            return _get_wrapped_class(function_or_class, full_reason)
        else:
            raise Exception(f"Unexpected skipped object: {function_or_class}")

    return decorator


def irrelevant(condition=None, library=None, weblog_variant=None, reason=None):
    """ decorator, allow to mark a test function/class as not relevant """

    skip = _should_skip(library=library, weblog_variant=weblog_variant, condition=condition)

    def decorator(function_or_class):

        if not skip:
            return function_or_class

        full_reason = "not relevant" if reason is None else f"not relevant: {reason}"

        if inspect.isfunction(function_or_class):
            return _get_wrapped_function(function_or_class, full_reason)
        elif inspect.isclass(function_or_class):
            return _get_wrapped_class(function_or_class, full_reason)
        else:
            raise Exception(f"Unexpected skipped object: {function_or_class}")

    return decorator


def bug(condition=None, library=None, weblog_variant=None, reason=None):
    """ decorator, allow to mark a test function/class as a known bug """

    skip = _should_skip(library=library, weblog_variant=weblog_variant, condition=condition)

    def decorator(function_or_class):

        if not skip:
            return function_or_class

        full_reason = "known bug" if reason is None else f"known bug: {reason}"

        if inspect.isfunction(function_or_class):
            return _get_wrapped_function(function_or_class, full_reason)
        elif inspect.isclass(function_or_class):
            return _get_wrapped_class(function_or_class, full_reason)
        else:
            raise Exception(f"Unexpected skipped object: {function_or_class}")

    return decorator


def released(cpp=None, dotnet=None, golang=None, java=None, nodejs=None, php=None, python=None, ruby=None):
    """Class decorator, allow to mark a test class with a version number of a component"""

    def wrapper(test_class):

        version = {
            "cpp": cpp,
            "dotnet": dotnet,
            "golang": golang,
            "java": java,
            "nodejs": nodejs,
            "php": php,
            "python": python,
            "ruby": ruby,
        }[context.library.library]

        if version is None:
            return test_class

        setattr(test_class, "__released__", version)

        if version == "?":
            return _get_wrapped_class(test_class, f"missing feature: release not yet planned")

        if version.startswith("not relevant"):
            return _get_wrapped_class(test_class, "not relevant")

        if context.library.version >= version:
            logger.debug(f"{test_class.__name__} feature has been released in {version} => added in test queue")
            return test_class

        return _get_wrapped_class(test_class, f"missing feature: release version is {version}")

    return wrapper


def rfc(link):
    def wrapper(item):
        setattr(item, "__rfc__", link)
        return item

    return wrapper


if __name__ == "__main__":
    import sys, logging

    logger.addHandler(logging.StreamHandler(stream=sys.stdout))

    @bug(library="ruby", reason="test")
    def test():
        pass

    @bug(library="ruby", reason="test")
    class Test:
        pass

    @released(ruby="99.99")
    class Test:
        pass
