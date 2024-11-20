def make_single_request_and_get_inject_headers(test_library, headers):
    with test_library.extract_headers_and_make_child_span("name", headers) as span:
        headers = test_library.dd_inject_headers(span.span_id)
        return {k.lower(): v for k, v in headers}
