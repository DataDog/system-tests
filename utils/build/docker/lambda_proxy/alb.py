from collections import defaultdict
import json
import base64
from flask import Request

TARGET_GROUP_ARN = "arn:aws:elasticloadbalancing:local:000000000000:targetgroup/local-proxy/0000000000000000"


def _should_base64_encode(content_type: str, body: bytes) -> bool:
    """
    Decide whether the body must be base64-encoded, following ALB rules:
      * ALB always encodes when `content-encoding` is present.
      * Else it encodes unless the type is plaintext (text/*, json, xml, js) **or**
        the caller tells us this is a "known good" textual type.
    """
    if not body:
        return False

    if "content-encoding" in (content_type or ""):
        return True

    text_like = (
        content_type.startswith("text/")
        or content_type.startswith("application/json")
        or content_type.startswith("application/xml")
        or content_type.startswith("application/javascript")
    )

    return not text_like


def build_alb_event(request: Request, multi: bool) -> dict:
    """
    Transform a Flask request into the ALB invocation event format.
    doc: https://docs.aws.amazon.com/elasticloadbalancing/latest/application/lambda-functions.html#receive-event-from-load-balancer
    """
    raw_body = request.get_data() or b""
    is_b64 = _should_base64_encode(request.content_type, raw_body)
    body = base64.b64encode(raw_body).decode() if is_b64 else raw_body.decode(errors="replace")

    event = {
        "requestContext": {"elb": {"targetGroupArn": TARGET_GROUP_ARN}},
        "httpMethod": request.method,
        "path": request.path,
        "body": body,
        "isBase64Encoded": is_b64,
    }

    if multi:
        event["multiValueQueryStringParameters"] = request.args.to_dict(flat=False)
        multi_value_headers = defaultdict(list)
        for k, v in request.headers.to_wsgi_list():
            multi_value_headers[k].append(v)
        event["multiValueHeaders"] = dict(multi_value_headers)
    else:
        event["queryStringParameters"] = request.args.to_dict(flat=True)
        event["headers"] = dict(request.headers)

    return event


def parse_alb_lambda_output(payload: str, multi: bool) -> tuple[int, dict[str, str | list[str]], bytes]:
    """
    Convert the JSON response expected from an ALB_triggered Lambda into pieces
    doc: https://docs.aws.amazon.com/elasticloadbalancing/latest/application/lambda-functions.html#respond-to-the-load-balancer
    """
    resp = json.loads(payload)

    status = int(resp["statusCode"])
    body_field = resp.get("body") or ""

    if resp.get("isBase64Encoded", False):
        body_bytes = base64.b64decode(body_field)
    else:
        body_bytes = (body_field).encode()

    if multi:
        headers = resp["multiValueHeaders"]
    else:
        headers = resp["headers"]

    return status, headers, body_bytes
