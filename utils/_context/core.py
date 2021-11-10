# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""singleton exposing all about test context"""

import logging
import os
import json
import inspect
import pytest

from utils.tools import logger
from utils._context.cgroup_info import CGroupInfo
from utils._context.library_version import LibraryVersion, Version


class ImageInfo:
    """data on docker image. data comes from `docker inspect`"""

    def __init__(self, image_name):
        self._raw = json.load(open(f"logs/{image_name}_image.json"))

        self.env = {}

        for var in self._raw[0]["Config"]["Env"]:
            key, value = var.split("=", 1)
            self.env[key] = value


class _Context:
    def __init__(self):
        self.agent_image = ImageInfo("agent")
        self.weblog_image = ImageInfo("weblog")
        self._warmups = []

        # complete with some env that can be sent threw command line
        if "DD_APPSEC_RULES" in os.environ:
            self.weblog_image.env["DD_APPSEC_RULES"] = os.environ["DD_APPSEC_RULES"]

        self.dd_site = os.environ["DD_SITE"]

        library = self.weblog_image.env.get("SYSTEM_TESTS_LIBRARY", None)
        version = self.weblog_image.env.get("SYSTEM_TESTS_LIBRARY_VERSION", None)
        self.library = LibraryVersion(library, version)

        self.weblog_variant = self.weblog_image.env.get("SYSTEM_TESTS_WEBLOG_VARIANT", None)

        if "DD_TRACE_SAMPLE_RATE" in self.weblog_image.env:
            sampling_rate = self.weblog_image.env["DD_TRACE_SAMPLE_RATE"]
            try:
                self.sampling_rate = float(sampling_rate)
            except:
                pytest.exit(f"DD_TRACE_SAMPLE_RATE should be a float, not {sampling_rate}")
        else:
            self.sampling_rate = None

        if self.library == "nodejs":
            self.waf_rule_set = Version("1.0.0")
        elif self.library >= "java@0.90.0":
            self.waf_rule_set = Version("1.0.0")
        elif self.library == "java":
            self.waf_rule_set = Version("0.0.1")
        else:
            self.waf_rule_set = Version("0.0.1")

    def get_weblog_container_id(self):
        cgroup_file = "logs/weblog.cgroup"

        with open(cgroup_file, mode="r") as fp:
            for line in fp:
                info = CGroupInfo.from_line(line)
                if info and info.container_id:
                    return info.container_id

        raise RuntimeError("Failed to get container id")

    def add_warmup(self, warmup):
        logger.debug(f"Add warmup function {warmup}")
        self._warmups.append(warmup)

    def execute_warmups(self):
        for warmup in self._warmups:
            warmup()

    def serialize(self):
        return {
            "library": self.library.serialize(),
            "weblog_variant": self.weblog_variant,
            "dd_site": self.dd_site,
            "sampling_rate": self.sampling_rate,
        }

    def __str__(self):
        return json.dumps(self.serialize(), indent=4)


context = _Context()


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


def not_relevant(condition=None, library=None, weblog_variant=None, reason=None):
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
    import sys

    logger.handlers.append(logging.StreamHandler(stream=sys.stdout))
    print(context)

    @bug(library="ruby", reason="test")
    def test():
        pass

    @bug(library="ruby", reason="test")
    class Test:
        pass

    @released(ruby="99.99")
    class Test:
        pass
