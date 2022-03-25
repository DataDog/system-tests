# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils.interfaces._core import BaseValidation
from utils import context


class HeadersPresenceValidation(BaseValidation):
    """Verify that some headers are present"""

    is_success_on_expiry = True

    def __init__(self, path_filters=None, request_headers=(), response_headers=(), check_condition=None):
        super().__init__(path_filters=path_filters)
        self.request_headers = set(request_headers)
        self.response_headers = set(response_headers)
        self.check_condition = check_condition

    def check(self, data):
        if self.check_condition and not self.check_condition(data):
            return

        request_headers = {h[0].lower() for h in data["request"]["headers"]}
        missing_request_headers = self.request_headers - request_headers
        if missing_request_headers:
            self.set_failure(f"Headers {missing_request_headers} are missing in request {data['log_filename']}")

        response_headers = {h[0].lower() for h in data["response"]["headers"]}
        missing_response_headers = self.response_headers - response_headers
        if missing_response_headers:
            self.set_failure(f"Headers {missing_response_headers} are missing in request {data['log_filename']}")
