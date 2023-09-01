import requests
from ddtrace import tracer
from ddtrace.appsec import trace_utils as appsec_trace_utils
from flask import Flask, Response
from flask import request as flask_request
from postgres import executePostgresOperation
from mysqldb import executeMysqlOperation

try:
    from ddtrace.contrib.trace_utils import set_user
except ImportError:
    set_user = lambda *args, **kwargs: None


app = Flask(__name__)

tracer.trace("init.service").finish()


@app.route("/")
def hello_world():
    return "Hello, World!\\n"


@app.route("/db", methods=["GET", "POST", "OPTIONS"])
def db():
    service = flask_request.args.get("service")
    operation = flask_request.args.get("operation")

    print("REQUEST RECEIVED!")

    if service == "postgresql":
        executePostgresOperation(operation)
    elif service == "mysql":
        executeMysqlOperation(operation)
    else:
        print(f"SERVICE NOT SUPPORTED: {service}")

    return "YEAH"
