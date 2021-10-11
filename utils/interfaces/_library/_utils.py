# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.


def _spans_with_parent(traces, parent_ids):
    for trace in traces:
        for span in trace:
            if span.get("parent_id") in parent_ids:
                yield span


def get_root_spans(traces):
    yield from _spans_with_parent(traces, (0, None))


def _get_rid_from_span(span):

    # code version
    user_agent = span.get("meta", {}).get("http.request.headers.user-agent", None)

    if not user_agent:
        # try something for .NET
        user_agent = span.get("meta", {}).get("http_request_headers_user-agent", None)

    if not user_agent or "rid/" not in user_agent:
        return None

    rid = user_agent[-36:]
    return rid


def get_spans_related_to_rid(traces, rid):
    for trace in traces:
        for span in trace:
            if rid == _get_rid_from_span(span):
                yield span
