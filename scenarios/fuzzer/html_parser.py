# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from html.parser import HTMLParser


class _RequestExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.callback = None
        self.base_url = None
        self.request = None

    def handle_endtag(self, tag):
        if tag == "form":
            self.callback(self.request)
            self.request = None

    def handle_starttag(self, tag, attrs):
        def get_path(url_or_path):
            if not url_or_path:
                return
            if url_or_path.startswith("/"):
                return url_or_path
            elif url_or_path.startswith(self.base_url):
                return url_or_path.replace(self.base_url, "")
            else:
                return

        if tag == "form":
            attrs = {k: v for k, v in attrs}
            self.request = {"method": attrs["method"], "path": get_path(attrs.get("action", "/")), "data": {}}

        elif tag == "input" and self.request:
            attrs = {k: v for k, v in attrs}

            name = attrs.get("id", attrs.get("name", None))
            if name:
                self.request["data"][name] = attrs.get("value", "")

        elif tag == "a":
            for name, value in attrs:
                if name.lower() == "href":
                    self.callback({"method": "GET", "path": get_path(value)})


_extractor = _RequestExtractor()


def extract_requests(content, base_url, callback):
    _extractor.base_url = base_url
    _extractor.callback = callback
    _extractor.feed(content)
