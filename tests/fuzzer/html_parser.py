# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from html.parser import HTMLParser
from collections.abc import Callable


class _RequestExtractor(HTMLParser):
    request: dict

    def __init__(self, base_url, callback: Callable):
        super().__init__()
        self.callback = callback
        self.base_url = base_url

    def error(self, message):
        pass

    def handle_endtag(self, tag):
        if tag == "form":
            self.callback(self.request)
            self.request = {}

    def handle_starttag(self, tag, attrs):
        def get_path(url_or_path):
            if not url_or_path:
                return None

            if url_or_path.startswith("/"):
                return url_or_path

            if url_or_path.startswith(self.base_url):
                return url_or_path.replace(self.base_url, "")

            return None

        if tag == "form":
            attrs = dict(attrs)
            self.request = {
                "method": attrs["method"],
                "path": get_path(attrs.get("action", "/")),
                "data": {},
            }

        elif tag == "input" and self.request:
            attrs = dict(attrs)

            name = attrs.get("id", attrs.get("name", None))
            if name:
                self.request["data"][name] = attrs.get("value", "")

        elif tag == "a":
            for name, value in attrs:
                if name.lower() == "href":
                    self.callback({"method": "GET", "path": get_path(value)})


def extract_requests(content, base_url, callback) -> None:
    extractor = _RequestExtractor(base_url, callback)

    extractor.feed(content)
