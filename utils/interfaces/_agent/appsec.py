# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

""" AppSec validations """

import traceback
import json

from utils.interfaces._core import BaseValidation
from utils.interfaces._library._utils import _get_rid_from_span
from utils.tools import m


class _BaseAppSecValidation(BaseValidation):
    path_filters = ["/api/v0.2/traces"]

    def _get_related_events(self, data):
        if "tracerPayloads" not in data["request"]["content"]:
            return

        content = data["request"]["content"]["tracerPayloads"]

        for payload in content:
            for chunk in payload["chunks"]:
                for span in chunk["spans"]:
                    rid = _get_rid_from_span(span)

                    if self.rid == rid:
                        self.log_debug(f'For {self} Found span with rid={self.rid} in {data["log_filename"]}')
                        if "meta" in span and "_dd.appsec.json" in span["meta"]:
                            appsec_data = json.loads(span["meta"]["_dd.appsec.json"])
                            yield payload, chunk, span, appsec_data
                        else:
                            self.log_info(f'For {self} in {data["log_filename"]}: no _dd.appsec.json data')


class AppSecValidation(_BaseAppSecValidation):
    def __init__(self, request, validator):
        super().__init__(request=request)
        self.validator = validator

    def check(self, data):
        log_filename = data["log_filename"]

        for payload, chunk, span, appsec_data in self._get_related_events(data):
            try:
                if self.validate(payload, chunk, span, appsec_data):
                    self.log_debug(f"{self} is validated by {log_filename}")
                    self.is_success_on_expiry = True
            except Exception as e:
                msg = traceback.format_exception_only(type(e), e)[0]
                self.set_failure(f"{m(self.message)} not validated on {log_filename}: {msg}")
