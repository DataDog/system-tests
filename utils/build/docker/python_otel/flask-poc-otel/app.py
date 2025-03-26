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


@app.route("/")
def hello_world():
    return "Hello, World!\\n"


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
