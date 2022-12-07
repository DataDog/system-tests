# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

""" Profiling validations """

import re
from utils.tools import logger


class _ProfilingFieldValidator:
    def __init__(self, field_name, content_pattern):

        self.field_name = field_name
        self.content_pattern = re.compile(content_pattern) if content_pattern else None

    def __call__(self, data):
        for item in data["request"]["content"]:
            content_disposition = item["headers"].get("Content-Disposition", "")
            if content_disposition.startswith(f'form-data; name="{self.field_name}"'):
                if self.content_pattern:
                    if not self.content_pattern.fullmatch(item["content"]):
                        raise Exception(
                            exception=f"Value {repr(item['content'])} does not match {self.content_pattern.pattern}",
                        )

                logger.debug(f"{self} is ok on {data['log_filename']}")
                return

        raise Exception(f"{data['log_filename']} is not valid")

