# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from urllib.parse import urlparse
from utils.tools import logger
from utils.interfaces._core import get_rid_from_span


def get_spans_related_to_rid(traces, rid):
    if not isinstance(traces, list):
        logger.error("Traces should be an array")
        yield from []  # do notfail here, it's schema's job
    else:
        for trace in traces:
            for span in trace:
                if rid is None or rid == get_rid_from_span(span):
                    yield span


def get_trace_request_path(root_span):
    if root_span.get("type") != "web":
        return None

    url = root_span["meta"].get("http.url")

    if url is None:
        return None

    path = urlparse(url).path

    return path
