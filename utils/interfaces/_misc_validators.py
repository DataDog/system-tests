# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils.interfaces._core import BaseValidation
from utils import context
import re

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

class HeadersMatchValidation(BaseValidation):
    """Verify that headers header mathes regexp"""

    is_success_on_expiry = True

    def __init__(self, path_filters=None, request_headers = {}, response_headers = {}, check_condition=None):
        super().__init__(path_filters=path_filters)
        self.request_headers = dict(request_headers)
        self.response_headers = dict(response_headers)
        self.check_condition = check_condition

    def check(self, data):
        if self.check_condition and not self.check_condition(data):
            return

        request_headers = {h[0].lower(): h[1] for h in data["request"]["headers"]}
        for hdr_name, regexp in self.request_headers.items():
            header = request_headers[hdr_name.lower()]
            if header:
                if re.match(regexp, header) == None: 
                    self.set_failure(f"Header {hdr_name} did not match {regexp} in request {data['log_filename']}")
            else:
                self.set_failure(f"Request header {hdr_name} is missing in request {data['log_filename']}")

        response_headers = {h[0].lower(): h[1] for h in data["response"]["headers"]}
        for hdr_name, regexp in self.response_headers.items():
            header = response_headers[hdr_name.lower()]
            if header:
                if re.match(regexp, header) == None: 
                    self.set_failure(f"header {hdr_name} did not match {regexp} in response {data['log_filename']}")
            else:
                self.set_failure(f"Response header {hdr_name} is missing in response {data['log_filename']}")

