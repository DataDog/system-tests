import os
import random
import subprocess

import psycopg2
import requests

from flask import Flask, Response, jsonify
from flask import request
from flask import request as flask_request

from opentelemetry.distro.version import __version__ as otel_version

from integrations.db.mssql import executeMssqlOperation
from integrations.db.mysqldb import executeMysqlOperation
from integrations.db.postgres import executePostgresOperation

app = Flask(__name__)


@app.route("/", methods=["GET", "POST", "HEAD", "OPTIONS", "PROPFIND"])
def hello_world():
    return "Hello, World!\\n"


# Endpoints below mirror the Datadog flask weblog so the OpenTelemetry HTTP semantic-convention
# suite can also be pointed at the upstream OpenTelemetry SDK. Keep the paths and the query
# parameter names identical to utils/build/docker/python/flask/app.py.
@app.route("/sample_rate_route/<i>")
def sample_rate(i):
    return "OK"


@app.route("/status")
def status_code():
    code = flask_request.args.get("code", default=200, type=int)
    return Response("OK, probably", status=code)


@app.route("/make_distant_call")
def make_distant_call():
    url = flask_request.args["url"]
    method = flask_request.args.get("method", default="GET")
    response = requests.request(method, url)

    return {
        "url": url,
        "status_code": response.status_code,
        "request_headers": dict(response.request.headers),
        "response_headers": dict(response.headers),
    }


@app.route("/healthcheck")
def healthcheck():
    return {
        "status": "ok",
        "library": {
            "name": "python_otel",
            "version": otel_version,
        },
    }


@app.route("/db", methods=["GET", "POST", "OPTIONS"])
def db():
    service = flask_request.args.get("service")
    operation = flask_request.args.get("operation")

    print(f"Request received for db service [{service}] and operation [{operation}]")

    if service == "postgresql":
        executePostgresOperation(operation)
    elif service == "mysql":
        executeMysqlOperation(operation)
    elif service == "mssql":
        executeMssqlOperation(operation)
    else:
        print(f"SERVICE NOT SUPPORTED: {service}")

    return "YEAH"
