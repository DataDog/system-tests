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
        self.env = {}

        try:
            self._raw = json.load(open(f"logs/{image_name}_image.json"))
        except FileNotFoundError:
            return  # silently fail, needed for testing

        for var in self._raw[0]["Config"]["Env"]:
            key, value = var.split("=", 1)
            self.env[key] = value

        try:
            with open(f"logs/.{image_name}.env") as f:
                for line in f:
                    if line.strip():
                        key, value = line.split("=", 1)
                        self.env[key] = value.strip()
        except FileNotFoundError:
            pass


class _Context:
    def __init__(self):
        self.agent_image = ImageInfo("agent")
        self.weblog_image = ImageInfo("weblog")
        self._warmups = []

        if "DD_APPSEC_RULES" in self.weblog_image.env:
            self.appsec_rules = self.weblog_image.env["DD_APPSEC_RULES"]
        else:
            self.appsec_rules = None

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

        if self.library == "php":
            self.php_appsec = Version(self.weblog_image.env.get("SYSTEM_TESTS_PHP_APPSEC_VERSION", None))
        else:
            self.php_appsec = None

        libddwaf_version = self.weblog_image.env.get("SYSTEM_TESTS_LIBDDWAF_VERSION", None)

        if not libddwaf_version:
            self.libddwaf_version = None
        else:
            self.libddwaf_version = Version(libddwaf_version, "libddwaf")

        agent_version = self.agent_image.env.get("SYSTEM_TESTS_AGENT_VERSION")

        if not agent_version:
            self.agent_version = None
        else:
            self.agent_version = Version(agent_version, "agent")

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
        result = {
            "library": self.library.serialize(),
            "weblog_variant": self.weblog_variant,
            "dd_site": self.dd_site,
            "sampling_rate": self.sampling_rate,
            "libddwaf_version": str(self.libddwaf_version),
            "appsec_rules": self.appsec_rules or "*default*",
        }

        if self.library == "php":
            result["php_appsec"] = self.php_appsec

        return result

    def __str__(self):
        return json.dumps(self.serialize(), indent=4)


context = _Context()
