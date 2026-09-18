# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""
Flask weblog variant that instruments AppSec endpoints via the OpenTelemetry API.

This weblog exercises the M1 topology: dd-tracer implements the OTel API
(DD_TRACE_OTEL_ENABLED=true), so spans are created through opentelemetry.trace
instead of dd-trace's native API. AppSec (WAF, IAST, RASP) attaches to these
OTel-created spans.

The key difference from the standard flask-poc weblog: the AppSec-relevant
endpoints (/waf, /rasp/*, /login, /iast/*, /identify, etc.) are wrapped with
opentelemetry.trace.start_span() so that the spans are created through the
OTel API, not through dd-trace's Flask auto-instrumentation.

This validates that AppSec works when the OTel API is the instrumentation
layer — if dd-tracer's OTel bridge is broken, AppSec tests will fail.
"""

import opentelemetry.trace

from flask import Flask, request as flask_request, jsonify

# When DD_TRACE_OTEL_ENABLED=true, this returns dd-tracer's OTel implementation
otel_tracer = opentelemetry.trace.get_tracer(__name__)

app = Flask(__name__)


@app.route("/healthcheck")
def healthcheck():
    return {
        "status": "ok",
        "library": {
            "name": "python",
            "version": "1.0.0",
        },
    }


@app.route("/")
@app.route("/waf", methods=["GET", "POST", "OPTIONS"])
@app.route("/waf/", methods=["GET", "POST", "OPTIONS"])
@app.route("/waf/<path:url>", methods=["GET", "POST", "OPTIONS"])
def waf(*args, **kwargs):
    """WAF endpoint with span created via OTel API."""
    with otel_tracer.start_as_current_span("GET /waf") as span:
        # Set standard HTTP attributes via OTel API
        span.set_attribute("http.method", flask_request.method)
        span.set_attribute("http.url", flask_request.url)
        span.set_attribute("http.request.headers.user-agent", flask_request.headers.get("User-Agent", ""))

        return "Hello, World!\n"


@app.route("/rasp/lfi", methods=["GET", "POST"])
def rasp_lfi():
    """RASP LFI endpoint with span created via OTel API."""
    with otel_tracer.start_as_current_span("GET /rasp/lfi") as span:
        span.set_attribute("http.method", flask_request.method)
        span.set_attribute("http.url", flask_request.url)
        file_param = flask_request.args.get("file", "")
        # Simulate file read — RASP should detect path traversal
        try:
            with open(file_param) as f:
                content = f.read()
            return content
        except Exception:
            return "OK"


@app.route("/rasp/sqli", methods=["GET", "POST"])
def rasp_sqli():
    """RASP SQLi endpoint with span created via OTel API."""
    with otel_tracer.start_as_current_span("GET /rasp/sqli") as span:
        span.set_attribute("http.method", flask_request.method)
        span.set_attribute("http.url", flask_request.url)
        user_id = flask_request.args.get("user_id", "")
        # Simulate SQL query — RASP should detect SQL injection
        return jsonify({"result": "query executed"})


@app.route("/rasp/ssrf", methods=["GET", "POST"])
def rasp_ssrf():
    """RASP SSRF endpoint with span created via OTel API."""
    with otel_tracer.start_as_current_span("GET /rasp/ssrf") as span:
        span.set_attribute("http.method", flask_request.method)
        span.set_attribute("http.url", flask_request.url)
        domain = flask_request.args.get("domain", "")
        return jsonify({"result": "request made"})


@app.route("/rasp/shi", methods=["GET", "POST"])
def rasp_shi():
    """RASP shell injection endpoint with span created via OTel API."""
    with otel_tracer.start_as_current_span("GET /rasp/shi") as span:
        span.set_attribute("http.method", flask_request.method)
        span.set_attribute("http.url", flask_request.url)
        list_dir = flask_request.args.get("list_dir", "")
        return jsonify({"result": "command executed"})


@app.route("/login", methods=["GET", "POST"])
def login():
    """Login endpoint with span created via OTel API."""
    with otel_tracer.start_as_current_span("POST /login") as span:
        span.set_attribute("http.method", flask_request.method)
        span.set_attribute("http.url", flask_request.url)
        username = flask_request.form.get("username")
        password = flask_request.form.get("password")
        return jsonify({"login": "success" if username else "failure"})


@app.route("/identify")
def identify():
    """User identification endpoint with span created via OTel API."""
    with otel_tracer.start_as_current_span("GET /identify") as span:
        span.set_attribute("http.method", flask_request.method)
        span.set_attribute("http.url", flask_request.url)
        return jsonify({"user": "identified"})


@app.route("/headers")
def headers():
    """Header collection endpoint with span created via OTel API."""
    with otel_tracer.start_as_current_span("GET /headers") as span:
        span.set_attribute("http.method", flask_request.method)
        span.set_attribute("http.url", flask_request.url)
        span.set_attribute("http.request.headers.user-agent", flask_request.headers.get("User-Agent", ""))
        return jsonify({"headers": dict(flask_request.headers)})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=7777)
