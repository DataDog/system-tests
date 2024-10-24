def make_single_request_and_get_inject_headers(test_library, headers):
    with extract_headers_and_make_child_span(test_library, "name", headers) as span:
        headers = test_library.inject_headers(span.span_id)
        return {k.lower(): v for k, v in headers}


def extract_headers_and_make_child_span(test_library, name, http_headers):
    parent_id = test_library.extract_headers(http_headers=http_headers)
    return test_library.start_span(name=name, parent_id=parent_id,)
