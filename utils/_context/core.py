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

    @property
    def appsec_is_released(self):
        return self.appsec_not_released_reason is None

    @property
    def appsec_not_released_reason(self):
        if self.library == "cpp":
            return "not relevant: No C++ appsec planned"

        if self.library == "golang" and self.weblog_variant == "echo-poc":
            return "not relevant: echo isn't instrumented"

        if self.library.library in ("nodejs", "php", "ruby"):
            return "missing feature: not yet released"

        if self.library < "java@0.87.0":
            return "missing feature: release planned for 0.87.0"

        if self.library < "dotnet@1.28.6":
            return "missing feature: release planned for 1.28.6"

        if self.library.library == "python" and self.library != "python@0.53.0.dev70+g494e6dc0":
            return "missing feature: release planned for 0.55"

        return None


context = _Context()

if __name__ == "__main__":

    print(context)
    print(context.appsec_is_released)
    print(context.appsec_not_released_reason)
