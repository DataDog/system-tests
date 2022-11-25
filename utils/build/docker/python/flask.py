import requests
from ddtrace import tracer
from flask import Flask, Response
from flask import request as flask_request
from iast import (
    weak_hash_secure_algorithm,
    weak_hash,
    weak_hash_multiple,
    weak_hash_duplicates,
    weak_cipher,
    weak_cipher_secure_algorithm,
)
import psycopg2

try:
    from ddtrace.contrib.trace_utils import set_user
except ImportError:
    set_user = lambda *args, **kwargs: None

POSTGRES_CONFIG = dict(
    host="postgres", port="5433", user="system_tests_user", password="system_tests", dbname="system_tests",
)

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
    if "file" not in flask_request.args:
        return "Please provide a file parameter", 400

    filename = flask_request.args.get("file")

    with open(filename, "r") as f:
        return f.read()


@app.route("/headers")
def headers():
    resp = Response("OK")
    resp.headers["Content-Language"] = "en-US"
    return resp


@app.route("/status")
def status_code():
    code = flask_request.args.get("code", default=200, type=int)
    return Response("OK, probably", status=code)


@app.route("/make_distant_call")
def make_distant_call():
    # curl localhost:7777/make_distant_call?url=http%3A%2F%2Fweblog%3A7777 | jq

    url = flask_request.args["url"]
    # url = "http://weblog:7777"
    response = requests.get(url)

    result = {
        "url": url,
        "status_code": response.status_code,
        "request_headers": dict(response.request.headers),
        "response_headers": dict(response.headers),
    }

    return result


@app.route("/identify")
def identify():
    set_user(
        tracer,
        user_id="usr.id",
        email="usr.email",
        name="usr.name",
        session_id="usr.session_id",
        role="usr.role",
        scope="usr.scope",
    )
    return Response("OK")


@app.route("/identify-propagate")
def identify_propagate():
    set_user(
        tracer,
        user_id="usr.id",
        email="usr.email",
        name="usr.name",
        session_id="usr.session_id",
        role="usr.role",
        scope="usr.scope",
        propagate=True,
    )
    return Response("OK")


@app.route("/dbm")
def dbm():
    integration = flask_request.headers.get("integration")
    if integration == "psycopg":
        postgres_db = psycopg2.connect(**POSTGRES_CONFIG)
        cursor = postgres_db.cursor()
        cursor_method = flask_request.headers.get("cursor_method")
        if cursor_method == "execute":
            cursor.execute("select 'blah'")
            return Response("OK")
        elif cursor_method == "executemany":
            cursor.executemany("select %s", (("blah",), ("moo",)))
            return Response("OK")
        return Response(f"Cursor method is not supported: {cursor_method}", 406)

    return Response(f"Integration is not supported: {integration}", 406)


@app.route("/iast/insecure_hashing/multiple_hash")
def view_weak_hash_multiple_hash():
    weak_hash_multiple()
    return Response("OK")


@app.route("/iast/insecure_hashing/test_secure_algorithm")
def view_weak_hash_secure_algorithm():
    result = weak_hash_secure_algorithm()
    return Response("OK")


@app.route("/iast/insecure_hashing/test_md5_algorithm")
def view_weak_hash_md5_algorithm():
    result = weak_hash()
    return Response("OK")


@app.route("/iast/insecure_hashing/deduplicate")
def view_weak_hash_deduplicate():
    weak_hash_duplicates()
    return Response("OK")


@app.route("/iast/insecure_cipher/test_insecure_algorithm")
def view_weak_cipher_insecure():
    weak_cipher()
    return Response("OK")


@app.route("/iast/insecure_cipher/test_secure_algorithm")
def view_weak_cipher_secure():
    weak_cipher_secure_algorithm()
    return Response("OK")
