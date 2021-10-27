# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""singleton exposing all about test context"""

import os
import json
import pytest

from utils.tools import logger
from utils._context.cgroup_info import CGroupInfo
from utils._context.library_version import LibraryVersion
from packaging.version import parse as parse_version


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

        if "DD_SITE" not in self.agent_image.env:
            pytest.exit("DD_SITE should be set in agent's image")
        self.dd_site = self.agent_image.env["DD_SITE"]

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


context = _Context()


def released(cpp=None, dotnet=None, golang=None, java=None, nodejs=None, php=None, python=None, ruby=None):
    def wrapper(test_class):
        def get_wrapped_class(skip_reason):
            @pytest.mark.skip(reason=skip_reason)
            class Test(test_class):
                pass

            Test.__doc__ = test_class.__doc__

            return Test

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
            logger.info(f"{test_class.__name__} feature will be released in a future version=> skipped")
            return get_wrapped_class(f"missing feature: release not yet planned")

        if version.startswith("not relevant"):
            skip_reason = version
            logger.info(f"{test_class.__name__} feature is {skip_reason} => skipped")
            return get_wrapped_class(skip_reason)

        if context.library.version >= parse_version(version):
            logger.debug(f"{test_class.__name__} feature is released in {version} => added in test queue")
            return test_class

        logger.info(f"{test_class.__name__} feature will be released in {version} => skipped")
        return get_wrapped_class(f"missing feature: release version is {version}")

    return wrapper


if __name__ == "__main__":

    print(context)
