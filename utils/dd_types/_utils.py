from utils.tools import get_rid_from_user_agent


def get_rid_from_span_data(span_type: str, meta: dict, metrics: dict) -> str | None:
    user_agent = None

    if span_type == "rpc":
        user_agent = meta.get("grpc.metadata.user-agent")
        # java does not fill this tag; it uses the normal http tags

    if not user_agent and metrics.get("_dd.top_level") == 1.0:
        # The top level span (aka root span) is mark via the _dd.top_level tag by the tracers
        user_agent = meta.get("http.request.headers.user-agent")

    if not user_agent:  # try something for .NET
        user_agent = meta.get("http_request_headers_user-agent")

    if not user_agent:
        # cpp tracer
        user_agent = meta.get("http_user_agent")

    if not user_agent:  # last hope
        user_agent = meta.get("http.useragent")

    if not user_agent:  # last last hope (java opentelemetry autoinstrumentation)
        user_agent = meta.get("user_agent.original")

    if not user_agent:  # last last last hope (python opentelemetry autoinstrumentation)
        user_agent = meta.get("http.user_agent")

    return get_rid_from_user_agent(user_agent)


def is_same_boolean(
    *, actual: bool | int | str | None, expected: bool | int | str | None, is_otel_boolean: bool = False
) -> bool:
    """Compare two boolean-ish values that may arrive in different shapes.

    Booleans reach the agent in several forms depending on the trace protocol and the source tag:
      - older formats stringify them as "true"/"false";
      - protocol v1.0 may deserialize as native True/False;
      - OTel booleans may deserialize as 1/0.

    The 1/0 form is only accepted when `is_otel_boolean=True`.
    """

    def _normalize(*, value: bool | int | str | None) -> bool | int | str | None:
        if value is True or value == "true":
            return True
        if value is False or value == "false":
            return False
        if is_otel_boolean:
            if value == 1:
                return True
            if value == 0:
                return False
        return value  # not a recognizable native boolean, will be compared by value as last resort

    actual_value = _normalize(value=actual)
    expected_value = _normalize(value=expected)

    if isinstance(actual_value, bool) or isinstance(expected_value, bool):
        return actual_value is expected_value

    return actual_value == expected_value
