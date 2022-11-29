# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

""" Profiling validations """

import re
from utils.interfaces._core import BaseValidation


class _ProfilingFieldAssertion(BaseValidation):
    def __init__(self, field_name, content_pattern):
        super().__init__(path_filters=["/profiling/v1/input", "/api/v2/profile"])

        from utils import interfaces  # TODO : find a better way

        interfaces.agent.timeout = 160
        interfaces.library.timeout = 160
        self.field_name = field_name
        self.content_pattern = re.compile(content_pattern) if content_pattern else None

    def check(self, data):
        for item in data["request"]["content"]:
            content_disposition = item["headers"].get("Content-Disposition", "")
            if content_disposition.startswith(f'form-data; name="{self.field_name}"'):
                if self.content_pattern:
                    if not self.content_pattern.fullmatch(item["content"]):
                        self.set_failure(
                            exception=f"Value {repr(item['content'])} does not match {self.content_pattern.pattern}",
                            data=data,
                        )
                        return

                self.log_debug(f"{self} is ok on {data['log_filename']}")
                self.is_success_on_expiry = True
                return

        self.set_failure(f"{self} is not validated on {data['log_filename']}")
