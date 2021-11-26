# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""singleton exposing all about test context"""

import os
import json
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

        self.dd_site = os.environ.get("DD_SITE")

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
        elif self.library >= "dotnet@1.30.0":
            self.waf_rule_set = Version("1.0.0")
        elif self.library >= "ruby@0.53.0":
            self.waf_rule_set = Version("1.0.0")
        elif self.library == "java":
            self.waf_rule_set = Version("0.0.1")
        elif self.library == "php":
            self.waf_rule_set = Version("1.0.0")
        else:
            self.waf_rule_set = Version("1.0.0")

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
            "waf_rule_set": str(self.waf_rule_set),
        }

    def __str__(self):
        return json.dumps(self.serialize(), indent=4)


context = _Context()
