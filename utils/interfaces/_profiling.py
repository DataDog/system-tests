# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

""" Profiling validations """

import traceback
import re
from utils.interfaces._core import BaseValidation
from utils.tools import m


class _ProfilingValidation(BaseValidation):
    """ will run an arbitrary check on profiling data.

        Validator function can :
        * returns true => validation will be validated at the end (but other will also be checked)
        * returns False or None => nothing is done
        * raise an exception => validation will fail
    """

    def __init__(self, path_filters, validator):
        super().__init__(path_filters=path_filters)
        self.validator = validator

    def check(self, data):
        try:
            if self.validator(data):
                self.log_debug(f"{self} is validated by {data['log_filename']}")
                self.is_success_on_expiry = True
        except Exception as e:
            msg = traceback.format_exception_only(type(e), e)[0]
            self.set_failure(f"{m(self.message)} not validated by {data['log_filename']}")


class _ProfilingFieldAssertion(BaseValidation):
    def __init__(self, path_filters, field_name, content_pattern):
        super().__init__(path_filters=path_filters)
        self.field_name = field_name
        self.content_pattern = re.compile(content_pattern) if content_pattern else None

    def check(self, data):
        for item in data["request"]["content"]:
            content_disposition = item["headers"].get("Content-Disposition", "")
            if content_disposition.startswith(f'form-data; name="{self.field_name}"'):
                if self.content_pattern:
                    if not self.content_pattern.fullmatch(item["content"]):
                        self.set_failure(
                            f"{self} is not validated on {data['log_filename']}: field is present but value {repr(item['content'])} does not match {self.content_pattern.pattern}"
                        )
                        return

                self.log_debug(f"{self} is ok on {data['log_filename']}")
                self.is_success_on_expiry = True
                return

        self.set_failure(f"{self} is not validated on {data['log_filename']}")
