import logging
import os
import random
import subprocess
import threading

from confluent_kafka import Producer, Consumer
import psycopg2
import requests
from flask import Flask, Response, jsonify
from flask import request
from flask import request as flask_request
from iast import (
    weak_cipher,
    weak_cipher_secure_algorithm,
    weak_hash,
    weak_hash_duplicates,
    weak_hash_multiple,
    weak_hash_secure_algorithm,
)
from integrations.db.mssql import executeMssqlOperation
from integrations.db.mysqldb import executeMysqlOperation
from integrations.db.postgres import executePostgresOperation

from flask_login import LoginManager
from flask_login import UserMixin
from flask_login import login_user

import ddtrace

ddtrace.patch_all()
from ddtrace import Pin, tracer
from ddtrace.settings.asm import config as asm_config
from ddtrace.appsec._constants import LOGIN_EVENTS_MODE
from ddtrace.appsec import trace_utils as appsec_trace_utils

try:
    from ddtrace.contrib.trace_utils import set_user
except ImportError:
    set_user = lambda *args, **kwargs: None

POSTGRES_CONFIG = dict(
    host="postgres", port="5433", user="system_tests_user", password="system_tests", dbname="system_tests",
)

app = Flask(__name__)
app.config["SECRET_KEY"] = "7110c8ae51a4b5af97be6534caef90e4bb9bdcb3380af008f90b23a5d1616bf319bc"
login_manager = LoginManager(app)

tracer.trace("init.service").finish()


class User(UserMixin):
    def __init__(self, _id, login, name, email, password, is_admin=False):
        self.id = _id
        self.login = login
        self.name = name
        self.email = email
        self.password = password
        self.is_admin = is_admin

    def set_password(self, password):
        self.password = password

    def check_password(self, password):
        return self.password == password

    def __repr__(self):
        return "<User {}>".format(self.email)

    def get_id(self):
        return self.id


EMPTY_USER = User(-1, "", "", "", "", False)

_USERS = [
    User("social-security-id", "test", "tester man", "testuser@ddog.com", "1234", False),
    User("591dc126-8431-4d0f-9509-b23318d3dce4", "testuuid", "tester uuid", "testuseruuid@ddog.com", "1234", False),
]


def get_user(login):
    for _user in _USERS:
        if _user.login == login:
            return _user
    return None


@login_manager.user_loader
def load_user(user_id):
    for user in _USERS:
        if user.id == int(user_id):
            return user
    return None


@app.route("/")
def hello_world():
    return "Hello, World!\\n"


@app.route("/sample_rate_route/<i>")
def sample_rate(i):
    return "OK"


_TRACK_CUSTOM_APPSEC_EVENT_NAME = "system_tests_appsec_event"


@app.route("/waf", methods=["GET", "POST", "OPTIONS"])
@app.route("/waf/", methods=["GET", "POST", "OPTIONS"])
@app.route("/waf/<path:url>", methods=["GET", "POST", "OPTIONS"])
@app.route("/params/<path>", methods=["GET", "POST", "OPTIONS"])
@app.route("/tag_value/<string:tag_value>/<int:status_code>", methods=["GET", "POST", "OPTIONS"])
def waf(*args, **kwargs):
    if "tag_value" in kwargs:
        appsec_trace_utils.track_custom_event(
            tracer, event_name=_TRACK_CUSTOM_APPSEC_EVENT_NAME, metadata={"value": kwargs["tag_value"]}
        )
        if kwargs["tag_value"].startswith("payload_in_response_body") and request.method == "POST":
            return jsonify({"payload": request.form})

        return "Value tagged", kwargs["status_code"], flask_request.args
    return "Hello, World!\n"


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
    url = flask_request.args["url"]
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


@app.route("/users")
def users():
    user = flask_request.args.get("user")
    set_user(
        tracer,
        user_id=user,
        email="usr.email",
        name="usr.name",
        session_id="usr.session_id",
        role="usr.role",
        scope="usr.scope",
    )
    return Response("OK")


@app.route("/dbm")
def dbm():
    integration = flask_request.args.get("integration")
    if integration == "psycopg":
        postgres_db = psycopg2.connect(**POSTGRES_CONFIG)
        cursor = postgres_db.cursor()
        operation = flask_request.args.get("operation")
        if operation == "execute":
            cursor.execute("select 'blah'")
            return Response("OK")
        elif operation == "executemany":
            cursor.executemany("select %s", (("blah",), ("moo",)))
            return Response("OK")
        return Response(f"Cursor method is not supported: {operation}", 406)

    return Response(f"Integration is not supported: {integration}", 406)


@app.route("/dsm")
def dsm():
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s", level=logging.INFO, datefmt="%Y-%m-%d %H:%M:%S"
    )
    topic = "dsm-system-tests-queue"
    consumer_group = "testgroup1"

    def delivery_report(err, msg):
        if err is not None:
            logging.info(f"[kafka] Message delivery failed: {err}")
        else:
            logging.info("[kafka] Message delivered to topic %s and partition %s", msg.topic(), msg.partition())

    def produce():
        producer = Producer({"bootstrap.servers": "kafka:9092", "client.id": "python-producer"})
        message = b"Hello, Kafka!"
        producer.produce(topic, value=message, callback=delivery_report)
        producer.flush()

    def consume():
        consumer = Consumer(
            {
                "bootstrap.servers": "kafka:9092",
                "group.id": consumer_group,
                "enable.auto.commit": True,
                "auto.offset.reset": "earliest",
            }
        )

        consumer.subscribe([topic])

        msg_received = False
        while not msg_received:
            msg = consumer.poll(1)
            if msg is None:
                logging.info("[kafka] Consumed message but got nothing")
            elif msg.error():
                logging.info("[kafka] Consumed message but got error " + msg.error())
            else:
                logging.info("[kafka] Consumed message")
                msg_received = True
        consumer.close()

    integration = flask_request.args.get("integration")
    logging.info(f"[kafka] Got request with integration: {integration}")
    if integration == "kafka":
        produce_thread = threading.Thread(target=produce, args=())
        consume_thread = threading.Thread(target=consume, args=())
        produce_thread.start()
        consume_thread.start()
        produce_thread.join()
        consume_thread.join()
        logging.info("[kafka] Returning response")
        return Response("ok")

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


def _sink_point(table="user", id="1"):
    sql = "SELECT * FROM " + table + " WHERE id = '" + id + "'"
    postgres_db = psycopg2.connect(**POSTGRES_CONFIG)
    cursor = postgres_db.cursor()
    cursor.execute(sql)


@app.route("/iast/source/body/test", methods=["POST"])
def view_iast_source_body():
    table = flask_request.json.get("name")
    user = flask_request.json.get("value")
    _sink_point(table=table, id=user)
    return Response("OK")


@app.route("/iast/source/cookiename/test")
def view_iast_source_cookie_name():
    param = [key for key in flask_request.cookies.keys() if key == "user"]
    _sink_point(id=param[0])
    return Response("OK")


@app.route("/iast/source/cookievalue/test")
def view_iast_source_cookie_value():
    table = flask_request.cookies.get("table")
    _sink_point(table=table)
    return Response("OK")


@app.route("/iast/source/headername/test")
def view_iast_source_header_name():
    param = [key for key in flask_request.headers.keys() if key == "User"]
    _sink_point(id=param[0])
    return Response("OK")


@app.route("/iast/source/header/test")
def view_iast_source_header_value():
    table = flask_request.headers.get("table")
    _sink_point(table=table)
    return Response("OK")


@app.route("/iast/source/parametername/test", methods=["GET"])
def view_iast_source_parametername_get():
    param = [key for key in flask_request.args.keys() if key == "user"]
    _sink_point(id=param[0])
    return Response("OK")


@app.route("/iast/source/parametername/test", methods=["POST"])
def view_iast_source_parametername_post():
    param = [key for key in flask_request.json.keys() if key == "user"]
    _sink_point(id=param[0])
    return Response("OK")


@app.route("/iast/source/parameter/test", methods=["GET", "POST"])
def view_iast_source_parameter():
    if flask_request.args:
        table = flask_request.args.get("table")
    else:
        table = flask_request.json.get("table")
    _sink_point(table=table)
    return Response("OK")


@app.route("/iast/path_traversal/test_insecure", methods=["POST"])
def view_iast_path_traversal_insecure():
    path = flask_request.form["path"]
    os.mkdir(path)
    return Response("OK")


@app.route("/iast/path_traversal/test_secure", methods=["POST"])
def view_iast_path_traversal_secure():
    path = flask_request.form["path"]
    root_dir = "/home/usr/secure_folder/"

    if os.path.commonprefix((os.path.realpath(path), root_dir)) == root_dir:
        open(path)

    return Response("OK")


@app.route("/iast/ssrf/test_insecure", methods=["POST"])
def view_iast_ssrf_insecure():
    import requests

    url = flask_request.form["url"]
    try:
        requests.get(url)
    except Exception:
        pass
    return Response("OK")


@app.route("/iast/ssrf/test_secure", methods=["POST"])
def view_iast_ssrf_secure():
    from urllib.parse import urlparse
    import requests

    url = flask_request.form["url"]
    # Validate the URL and enforce whitelist
    allowed_domains = ["example.com", "api.example.com"]
    parsed_url = urlparse(url)

    if parsed_url.hostname not in allowed_domains:
        return "Forbidden", 403

    try:
        requests.get(url)
    except Exception:
        pass

    return Response("OK")


_TRACK_METADATA = {
    "metadata0": "value0",
    "metadata1": "value1",
}


_TRACK_USER = "system_tests_user"


@app.route("/user_login_success_event")
def track_user_login_success_event():
    appsec_trace_utils.track_user_login_success_event(tracer, user_id=_TRACK_USER, metadata=_TRACK_METADATA)
    return Response("OK")


@app.route("/user_login_failure_event")
def track_user_login_failure_event():
    appsec_trace_utils.track_user_login_failure_event(
        tracer, user_id=_TRACK_USER, exists=True, metadata=_TRACK_METADATA,
    )
    return Response("OK")


@app.route("/login", methods=["GET", "POST"])
def login_endpoint():
    sdk_event = request.args.get("sdk_event", "")
    sdk_user = request.args.get("sdk_user", "")
    sdk_user_exists = request.args.get("sdk_user_exists", "false").lower() == "true"

    if sdk_event:
        if sdk_event == "success":
            appsec_trace_utils.track_user_login_success_event(
                tracer, user_id=sdk_user, login_events_mode=LOGIN_EVENTS_MODE.SDK
            )
            return Response("OK")

        appsec_trace_utils.track_user_login_failure_event(
            tracer, user_id=sdk_user, exists=sdk_user_exists, login_events_mode=LOGIN_EVENTS_MODE.SDK
        )
        return Response("Unauthorized from SDK", status=401)

    mode = asm_config._automatic_login_events_mode
    user_id = None
    if request.method == "GET":
        return Response("Basic Auth not supported on flask-login by default")
    elif request.method == "POST":
        _user = get_user(flask_request.form["username"])
        if _user:
            user_id = _user.id
            if _user.password == flask_request.form["password"]:
                login_user(_user, remember=False)
                return Response("OK", status=200)
            else:
                appsec_trace_utils.track_user_login_failure_event(
                    tracer, user_id=user_id, exists=True, login_events_mode=mode
                )
                return Response("Wrong authentication", status=401)

    appsec_trace_utils.track_user_login_failure_event(tracer, user_id=user_id, exists=False, login_events_mode=mode)
    return Response("Unauthorized, method: %s" % str(request.method), status=401)


_TRACK_CUSTOM_EVENT_NAME = "system_tests_event"


@app.route("/custom_event")
def track_custom_event():
    appsec_trace_utils.track_custom_event(tracer, event_name=_TRACK_CUSTOM_EVENT_NAME, metadata=_TRACK_METADATA)
    return Response("OK")


@app.route("/iast/sqli/test_secure", methods=["POST"])
def view_sqli_secure():
    sql = "SELECT * FROM IAST_USER WHERE USERNAME = ? AND PASSWORD = ?"
    postgres_db = psycopg2.connect(**POSTGRES_CONFIG)
    cursor = postgres_db.cursor()
    cursor.execute(sql, flask_request.form["username"], flask_request.form["password"])
    return Response("OK")


@app.route("/iast/sqli/test_insecure", methods=["POST"])
def view_sqli_insecure():
    sql = (
        "SELECT * FROM IAST_USER WHERE USERNAME = '"
        + flask_request.form["username"]
        + "' AND PASSWORD = '"
        + flask_request.form["password"]
        + "'"
    )
    postgres_db = psycopg2.connect(**POSTGRES_CONFIG)
    cursor = postgres_db.cursor()
    cursor.execute(sql)
    return Response("OK")


@app.route("/iast/insecure-cookie/test_insecure")
def test_insecure_cookie():
    resp = Response("OK")
    resp.set_cookie("insecure", "cookie", secure=False, httponly=False, samesite="None")
    return resp


@app.route("/iast/insecure-cookie/test_secure")
def test_secure_cookie():
    resp = Response("OK")
    resp.set_cookie(key="secure3", value="value", secure=True, httponly=True, samesite="Strict")
    return resp


@app.route("/iast/insecure-cookie/test_empty_cookie")
def test_empty_cookie():
    resp = Response("OK")
    resp.set_cookie(key="secure3", value="", secure=True, httponly=True, samesite="Strict")
    return resp


@app.route("/iast/no-httponly-cookie/test_insecure")
def test_nohttponly_insecure_cookie():
    resp = Response("OK")
    resp.set_cookie("insecure", "cookie", secure=True, httponly=False, samesite="Strict")
    return resp


@app.route("/iast/no-httponly-cookie/test_secure")
def test_nohttponly_secure_cookie():
    resp = Response("OK")
    resp.set_cookie(key="secure3", value="value", secure=True, httponly=True, samesite="Strict")
    return resp


@app.route("/iast/no-httponly-cookie/test_empty_cookie")
def test_nohttponly_empty_cookie():
    resp = Response("OK")
    resp.set_cookie(key="secure3", value="", secure=True, httponly=True, samesite="Strict")
    return resp


@app.route("/iast/no-samesite-cookie/test_insecure")
def test_nosamesite_insecure_cookie():
    resp = Response("OK")
    resp.set_cookie("insecure", "cookie", secure=True, httponly=True, samesite="None")
    return resp


@app.route("/iast/no-samesite-cookie/test_secure")
def test_nosamesite_secure_cookie():
    resp = Response("OK")
    resp.set_cookie(key="secure3", value="value", secure=True, httponly=True, samesite="Strict")
    return resp


@app.route("/iast/weak_randomness/test_insecure")
def test_weak_randomness_insecure():
    _ = random.randint(1, 100)
    return Response("OK")


@app.route("/iast/weak_randomness/test_secure")
def test_weak_randomness_secure():
    random_secure = random.SystemRandom()
    _ = random_secure.randint(1, 100)
    return Response("OK")


@app.route("/iast/cmdi/test_insecure", methods=["POST"])
def view_cmdi_insecure():
    filename = "/"
    command = flask_request.form["cmd"]
    subp = subprocess.Popen(args=[command, "-la", filename])
    subp.communicate()
    subp.wait()

    return Response("OK")


@app.route("/iast/cmdi/test_secure", methods=["POST"])
def view_cmdi_secure():
    filename = "/"
    command = " ".join([flask_request.form["cmd"], "-la", filename])
    # TODO: add secure command
    # subp = subprocess.check_output(command, shell=False)
    # subp.communicate()
    # subp.wait()
    return Response("OK")


@app.route("/db", methods=["GET", "POST", "OPTIONS"])
def db():
    service = flask_request.args.get("service")
    operation = flask_request.args.get("operation")

    print("REQUEST RECEIVED!")

    if service == "postgresql":
        executePostgresOperation(operation)
    elif service == "mysql":
        executeMysqlOperation(operation)
    elif service == "mssql":
        executeMssqlOperation(operation)
    else:
        print(f"SERVICE NOT SUPPORTED: {service}")

    return "YEAH"


@app.route("/createextraservice", methods=["GET"])
def create_extra_service():
    new_service_name = request.args.get("serviceName", default="", type=str)
    if new_service_name:
        Pin.override(Flask, service=new_service_name, tracer=tracer)
    return Response("OK")
