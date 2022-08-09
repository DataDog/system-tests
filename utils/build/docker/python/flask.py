from ddtrace import tracer
from flask import Flask, request, Response


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
def waf(*args, **kwargs):
    return "Hello, World!\\n"


@app.route("/read_file", methods=["GET"])
def read_file():
    if "file" not in request.args:
        return "Please provide a file parameter", 400

    filename = request.args.get("file")

    with open(filename, "r") as f:
        return f.read()


@app.route("/headers")
def headers():
    resp = Response("OK")
    resp.headers["Content-Language"] = "en-US"
    return resp


@app.route("/status")
def status_code():
    code = request.args.get("code", default=200, type=int)
    return Response("OK, probably", status=code)


@app.route("/identify")
def identify():
    tracer.set_user(
        user_id="usr.id",
        email="usr.email",
        name="usr.name",
        session_id="usr.session_id",
        role="usr.role",
        scope="usr.scope",
    )
    return "OK"
