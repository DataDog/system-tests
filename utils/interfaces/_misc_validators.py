# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.


from collections.abc import Callable, Iterable
import re


class HeadersPresenceValidator:
    """Verify that some headers are present"""

    def __init__(
        self,
        request_headers: Iterable[str] = (),
        response_headers: Iterable[str] = (),
        check_condition: Callable | None = None,
    ):
        self.request_headers = set(request_headers)
        self.response_headers = set(response_headers)
        self.check_condition = check_condition

    def __call__(self, data: dict) -> None:
        if self.check_condition and not self.check_condition(data):
            return

        request_headers = {h[0].lower() for h in data["request"]["headers"]}
        missing_request_headers = self.request_headers - request_headers
        if missing_request_headers:
            raise ValueError(f"Headers {missing_request_headers} are missing in request {data['log_filename']}")

        response_headers = {h[0].lower() for h in data["response"]["headers"]}
        missing_response_headers = self.response_headers - response_headers
        if missing_response_headers:
            raise ValueError(f"Headers {missing_response_headers} are missing in request {data['log_filename']}")


class HeadersMatchValidator:
    """Verify that headers header mathes regexp"""

    def __init__(
        self,
        request_headers: dict | None = None,
        response_headers: dict | None = None,
        check_condition: Callable | None = None,
    ):
        self.request_headers = dict(request_headers) if request_headers is not None else {}
        self.response_headers = dict(response_headers) if response_headers is not None else {}
        self.check_condition = check_condition

    def __call__(self, data: dict) -> None:
        if self.check_condition and not self.check_condition(data):
            return

        request_headers = {h[0].lower(): h[1] for h in data["request"]["headers"]}
        for hdr_name, regexp in self.request_headers.items():
            header = request_headers[hdr_name.lower()]
            if header:
                if re.match(regexp, header) is None:
                    raise ValueError(f"Header {hdr_name} did not match {regexp} in request {data['log_filename']}")
            else:
                raise ValueError(f"Request header {hdr_name} is missing in request {data['log_filename']}")

        response_headers = {h[0].lower(): h[1] for h in data["response"]["headers"]}
        for hdr_name, regexp in self.response_headers.items():
            header = response_headers[hdr_name.lower()]
            if header:
                if re.match(regexp, header) is None:
                    raise ValueError(f"header {hdr_name} did not match {regexp} in response {data['log_filename']}")
            else:
                raise ValueError(f"Response header {hdr_name} is missing in response {data['log_filename']}")
