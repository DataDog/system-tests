from ddtrace import tracer
from flask import Flask


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
@app.route("/params/<path:appscan_fingerprint>", methods=["GET", "POST"])
def waf():
    return "Hello, World!\\n"
