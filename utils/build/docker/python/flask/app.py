import logging
import os
import random
import subprocess
import threading

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
from integrations.messaging.aws.sns import sns_consume
from integrations.messaging.aws.sns import sns_produce
from integrations.messaging.aws.sqs import sqs_consume
from integrations.messaging.aws.sqs import sqs_produce
from integrations.messaging.kafka import kafka_consume
from integrations.messaging.kafka import kafka_produce
from integrations.messaging.rabbitmq import rabbitmq_consume
from integrations.messaging.rabbitmq import rabbitmq_produce

import ddtrace

from ddtrace import config

# enable botocore distributed tracing
config.botocore.propagation_enabled = True

ddtrace.patch_all(kombu=True)

from ddtrace import tracer
from ddtrace.appsec import trace_utils as appsec_trace_utils
from ddtrace import Pin, tracer
from ddtrace.appsec import trace_utils as appsec_trace_utils

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


_TRACK_CUSTOM_APPSEC_EVENT_NAME = "system_tests_appsec_event"


@app.route("/waf", methods=["GET", "POST", "OPTIONS"])
@app.route("/waf/", methods=["GET", "POST", "OPTIONS"])
@app.route("/waf/<path:url>", methods=["GET", "POST", "OPTIONS"])
@app.route("/params/<path>", methods=["GET", "POST", "OPTIONS"])
@app.route(
    "/tag_value/<string:tag_value>/<int:status_code>", methods=["GET", "POST", "OPTIONS"],
)
def waf(*args, **kwargs):
    if "tag_value" in kwargs:
        appsec_trace_utils.track_custom_event(
            tracer, event_name=_TRACK_CUSTOM_APPSEC_EVENT_NAME, metadata={"value": kwargs["tag_value"]},
        )
        if kwargs["tag_value"].startswith("payload_in_response_body") and request.method == "POST":
            return jsonify({"payload": request.form}), kwargs["status_code"], flask_request.args

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
            cursor.execute("SELECT version()")
            return Response("OK")
        elif operation == "executemany":
            cursor.executemany("SELECT version()", [((),)])
            return Response("OK")
        return Response(f"Cursor method is not supported: {operation}", 406)

    return Response(f"Integration is not supported: {integration}", 406)


@app.route("/kafka/produce")
def produce_kafka_message():
    """
    The goal of this endpoint is to trigger kafka producer calls
    """
    topic = flask_request.args.get("topic", "DistributedTracing")
    message = b"Distributed Tracing Test from Python for Kafka!"
    output = kafka_produce(topic, message)
    if "error" in output:
        return output, 400
    else:
        return output, 200


@app.route("/kafka/consume")
def consume_kafka_message():
    """
    The goal of this endpoint is to trigger kafka consumer calls
    """
    topic = flask_request.args.get("topic", "DistributedTracing")
    timeout = int(flask_request.args.get("timeout", 60))
    output = kafka_consume(topic, "apm_test", timeout)
    if "error" in output:
        return output, 400
    else:
        return output, 200


@app.route("/sqs/produce")
def produce_sqs_message():
    queue = flask_request.args.get("queue", "DistributedTracing")
    message = "Hello from Python SQS"
    output = sqs_produce(queue, message)
    if "error" in output:
        return output, 400
    else:
        return output, 200


@app.route("/sqs/consume")
def consume_sqs_message():
    queue = flask_request.args.get("queue", "DistributedTracing")
    timeout = int(flask_request.args.get("timeout", 60))
    output = sqs_consume(queue, timeout)
    if "error" in output:
        return output, 400
    else:
        return output, 200


@app.route("/sns/produce")
def produce_sns_message():
    queue = flask_request.args.get("queue", "DistributedTracing SNS")
    topic = flask_request.args.get("topic", "DistributedTracing SNS Topic")
    message = "Hello from Python SNS -> SQS"
    output = sns_produce(queue, topic, message)
    if "error" in output:
        return output, 400
    else:
        return output, 200


@app.route("/sns/consume")
def consume_sns_message():
    queue = flask_request.args.get("queue", "DistributedTracing SNS")
    timeout = int(flask_request.args.get("timeout", 60))
    output = sns_consume(queue, timeout)
    if "error" in output:
        return output, 400
    else:
        return output, 200


@app.route("/rabbitmq/produce")
def produce_rabbitmq_message():
    queue = flask_request.args.get("queue", "DistributedTracingContextPropagation")
    exchange = flask_request.args.get("exchange", "DistributedTracingContextPropagation")
    message = "Hello from Python RabbitMQ Context Propagation Test"
    output = rabbitmq_produce(queue, exchange, message)
    if "error" in output:
        return output, 400
    else:
        return output, 200


@app.route("/rabbitmq/consume")
def consume_rabbitmq_message():
    queue = flask_request.args.get("queue", "DistributedTracingContextPropagation")
    exchange = flask_request.args.get("exchange", "DistributedTracingContextPropagation")
    timeout = int(flask_request.args.get("timeout", 60))
    output = rabbitmq_consume(queue, exchange, timeout)
    if "error" in output:
        return output, 400
    else:
        return output, 200


@app.route("/dsm")
def dsm():
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s", level=logging.INFO, datefmt="%Y-%m-%d %H:%M:%S",
    )
    queue = "dsm-system-tests-queue"
    topic = "dsm-system-tests-topic"
    integration = flask_request.args.get("integration")

    # force reset DSM context for global tracer and global DSM processor
    try:
        del tracer.data_streams_processor._current_context.value
    except AttributeError:
        pass
    try:
        from ddtrace.internal.datastreams import data_streams_processor

        del data_streams_processor()._current_context.value
    except AttributeError:
        pass

    logging.info(f"[DSM] Got request with integration: {integration}")

    response = Response(f"Integration is not supported: {integration}", 406)

    if integration == "kafka":

        def delivery_report(err, msg):
            if err is not None:
                logging.info(f"[kafka] Message delivery failed: {err}")
            else:
                logging.info("[kafka] Message delivered to topic %s and partition %s", msg.topic(), msg.partition())

        produce_thread = threading.Thread(
            target=kafka_produce, args=(queue, b"Hello, Kafka from DSM python!", delivery_report,)
        )
        consume_thread = threading.Thread(target=kafka_consume, args=(queue, "testgroup1",))
        produce_thread.start()
        consume_thread.start()
        produce_thread.join()
        consume_thread.join()
        logging.info("[kafka] Returning response")
        response = Response("ok")
    elif integration == "sqs":
        produce_thread = threading.Thread(target=sqs_produce, args=(queue, "Hello, SQS from DSM python!",))
        consume_thread = threading.Thread(target=sqs_consume, args=(queue,))
        produce_thread.start()
        consume_thread.start()
        produce_thread.join()
        consume_thread.join()
        logging.info("[sqs] Returning response")
        response = Response("ok")
    elif integration == "rabbitmq":
        timeout = int(flask_request.args.get("timeout", 60))
        produce_thread = threading.Thread(
            target=rabbitmq_produce, args=(queue, queue, "Hello, RabbitMQ from DSM python!")
        )
        consume_thread = threading.Thread(target=rabbitmq_consume, args=(queue, queue, timeout))
        produce_thread.start()
        consume_thread.start()
        produce_thread.join()
        consume_thread.join()
        logging.info("[RabbitMQ] Returning response")
        response = Response("ok")
    elif integration == "sns":
        sns_queue = queue + "-sns"
        sns_topic = topic + "-sns"
        produce_thread = threading.Thread(
            target=sns_produce, args=(sns_queue, sns_topic, "Hello, SNS->SQS from DSM python!",)
        )
        consume_thread = threading.Thread(target=sns_consume, args=(sns_queue,))
        produce_thread.start()
        consume_thread.start()
        produce_thread.join()
        consume_thread.join()
        logging.info("[SNS->SQS] Returning response")
        response = Response("ok")

    # force flush stats to ensure they're available to agent after test setup is complete
    tracer.data_streams_processor.periodic()
    return response


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
