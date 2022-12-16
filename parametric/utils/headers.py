from parametric.protos.apm_test_client_pb2 import DistributedHTTPHeaders


def make_single_request_and_get_inject_headers(test_library, headers_list):
    distributed_message = DistributedHTTPHeaders()
    for key, value in headers_list:
        distributed_message.http_headers[key] = value

    with test_library.start_span(
        name="name", service="service", resource="resource", http_headers=distributed_message
    ) as span:
        headers = test_library.inject_headers(span.span_id).http_headers.http_headers
        return headers
