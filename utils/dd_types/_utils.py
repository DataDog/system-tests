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
