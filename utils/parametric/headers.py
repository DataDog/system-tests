def make_single_request_and_get_inject_headers(test_library, headers):
    with test_library.start_span(
        name="name",
        service="service",
        resource="resource",
        http_headers=headers,
    ) as span:
        headers = test_library.inject_headers(span.span_id)
        return {k.lower(): v for k, v in headers}
