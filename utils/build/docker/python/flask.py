import requests

from ddtrace import tracer
from flask import Flask, request

app = Flask(__name__)

tracer.trace("init.service").finish()


@app.route("/")
def hello_world():
    return "Hello, World!\\n"


@app.route("/sample_rate_route/<i>")
def sample_rate(i):
    return "OK"


@app.route("/waf", methods=["GET", "POST"])
@app.route("/waf/", methods=["GET", "POST"])
@app.route("/waf/<path:url>", methods=["GET", "POST"])
@app.route("/params/<path>", methods=["GET", "POST"])
def waf(request, *args, **kwargs):
    return "Hello, World!\\n"


@app.route("/read_file", methods=["GET"])
def read_file():
    if "file" not in request.args:
        return "Please provide a file parameter", 400

    filename = request.args.get("file")

    with open(filename, "r") as f:
        return f.read()


@app.route("/distributed-http")
def distributed_http():
    end_hello = requests.get("http://weblog:7777/distributed-http-end")
    return end_hello.content


@app.route("/distributed-http-end")
def distributed_http_end():
    return "Hello, World!\\n"
