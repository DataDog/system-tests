import json
import logging
import mock
import os
import random
import subprocess
import threading
import http.client
import urllib.request
import xmltodict
import sys

if os.environ.get("INCLUDE_POSTGRES", "true") == "true":
    import asyncpg
    import psycopg2

if os.environ.get("INCLUDE_MYSQL", "true") == "true":
    import aiomysql
    import mysql
    import pymysql
    import MySQLdb

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

if os.environ.get("INCLUDE_SQLSERVER", "true") == "true":
    from integrations.db.mssql import executeMssqlOperation
if os.environ.get("INCLUDE_MYSQL", "true") == "true":
    from integrations.db.mysqldb import executeMysqlOperation
if os.environ.get("INCLUDE_POSTGRES", "true") == "true":
    from integrations.db.postgres import executePostgresOperation
from integrations.messaging.aws.kinesis import kinesis_consume
from integrations.messaging.aws.kinesis import kinesis_produce
from integrations.messaging.aws.sns import sns_consume
from integrations.messaging.aws.sns import sns_produce
from integrations.messaging.aws.sqs import sqs_consume
from integrations.messaging.aws.sqs import sqs_produce

if os.environ.get("INCLUDE_KAFKA", "true") == "true":
    from integrations.messaging.kafka import kafka_consume
    from integrations.messaging.kafka import kafka_produce
if os.environ.get("INCLUDE_RABBITMQ", "true") == "true":
    from integrations.messaging.rabbitmq import rabbitmq_consume
    from integrations.messaging.rabbitmq import rabbitmq_produce

import ddtrace

from ddtrace import tracer
from ddtrace.appsec import trace_utils as appsec_trace_utils
from ddtrace import Pin, tracer
from ddtrace.appsec import trace_utils as appsec_trace_utils
from ddtrace.internal.datastreams import data_streams_processor
from ddtrace.internal.datastreams.processor import DsmPathwayCodec

# Patch kombu since its not patched automatically
ddtrace.patch_all(kombu=True)

try:
    from ddtrace.contrib.trace_utils import set_user
except ImportError:
    set_user = lambda *args, **kwargs: None

POSTGRES_CONFIG = dict(
    host="postgres", port="5433", user="system_tests_user", password="system_tests", dbname="system_tests_dbname",
)
ASYNCPG_CONFIG = dict(POSTGRES_CONFIG)
ASYNCPG_CONFIG["database"] = ASYNCPG_CONFIG["dbname"]  # asyncpg uses 'database' instead of 'dbname'
del ASYNCPG_CONFIG["dbname"]

MYSQL_CONFIG = dict(host="mysqldb", port=3306, user="mysqldb", password="mysqldb", database="mysql_dbname",)
AIOMYSQL_CONFIG = dict(MYSQL_CONFIG)
AIOMYSQL_CONFIG["db"] = AIOMYSQL_CONFIG["database"]
del AIOMYSQL_CONFIG["database"]

app = Flask(__name__)

tracer.trace("init.service").finish()


def reset_dsm_context():
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


### BEGIN EXPLOIT PREVENTION


@app.route("/rasp/lfi", methods=["GET", "POST"])
def rasp_lfi(*args, **kwargs):
    file = None
    if request.method == "GET":
        file = flask_request.args.get("file")
    elif request.method == "POST":
        try:
            file = (request.form or request.json or {}).get("file")
        except Exception as e:
            print(repr(e), file=sys.stderr)
        try:
            if file is None:
                file = xmltodict.parse(flask_request.data).get("file")
        except Exception as e:
            print(repr(e), file=sys.stderr)
            pass
    if file is None:
        return Response("missing file parameter", status=400)
    try:
        with open(file, "rb") as f_in:
            f_in.seek(0, os.SEEK_END)
            return f"{file} open with {f_in.tell()} bytes"
    except OSError as e:
        return f"{file} could not be open: {e!r}"


@app.route("/rasp/ssrf", methods=["GET", "POST"])
def rasp_ssrf(*args, **kwargs):
    domain = None
    if request.method == "GET":
        domain = flask_request.args.get("domain")
    elif request.method == "POST":
        try:
            domain = (request.form or request.json or {}).get("domain")
        except Exception as e:
            print(repr(e), file=sys.stderr)
        try:
            if domain is None:
                domain = xmltodict.parse(flask_request.data).get("domain")
        except Exception as e:
            print(repr(e), file=sys.stderr)
            pass

    if domain is None:
        return Response("missing domain parameter", status=400)
    try:
        with urllib.request.urlopen(f"http://{domain}", timeout=1) as url_in:

            return f"url http://{domain} open with {len(url_in.read())} bytes"
    except http.client.HTTPException as e:
        return f"url http://{domain} could not be open: {e!r}"


### END EXPLOIT PREVENTION


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


@app.route("/stub_dbm")
async def stub_dbm():
    integration = flask_request.args.get("integration")
    operation = flask_request.args.get("operation", None)

    if integration == "psycopg":
        postgres_db = psycopg2.connect(**POSTGRES_CONFIG)
        cursor = postgres_db.cursor()
        return await db_execute_and_retrieve_comment(operation, cursor)

    elif integration == "asyncpg":
        conn = await asyncpg.connect(**ASYNCPG_CONFIG)

        orig = ddtrace.propagation._database_monitoring.set_argument_value

        def mock_func(args, kwargs, sql_pos, sql_kw, sql_with_dbm_tags):
            return orig(args, kwargs, sql_pos, sql_kw, sql_with_dbm_tags)

        with mock.patch(
            "ddtrace.propagation._database_monitoring.set_argument_value", side_effect=mock_func
        ) as patched:
            if operation == "execute":
                await conn.execute("SELECT version()")
                return get_dbm_comment(None, "execute", patched.call_args_list[0][0][4])
            elif operation == "executemany":
                await cursor.executemany("SELECT version()", [((),)])
                return get_dbm_comment(None, "executemany", patched.call_args_list[0][0][4])
        return Response(f"Cursor method is not supported: {operation}", 406)

    elif integration == "aiomysql":
        conn = await aiomysql.connect(**AIOMYSQL_CONFIG)
        cursor = await conn.cursor()
        return await db_execute_and_retrieve_comment(operation, cursor, is_async=True)

    elif integration == "mysql-connector":
        conn = mysql.connector.connect(**AIOMYSQL_CONFIG)
        cursor = conn.cursor()
        return await db_execute_and_retrieve_comment(operation, cursor)

    elif integration == "mysqldb":
        conn = MySQLdb.Connect(
            **{
                "host": MYSQL_CONFIG["host"],
                "user": MYSQL_CONFIG["user"],
                "passwd": MYSQL_CONFIG["password"],
                "db": MYSQL_CONFIG["database"],
                "port": MYSQL_CONFIG["port"],
            }
        )
        cursor = conn.cursor()
        return await db_execute_and_retrieve_comment(operation, cursor)

    elif integration == "pymysql":
        conn = pymysql.connect(**AIOMYSQL_CONFIG)
        cursor = conn.cursor()
        return await db_execute_and_retrieve_comment(operation, cursor)
    return Response(f"Integration is not supported: {integration}", 406)


async def db_execute_and_retrieve_comment(operation, cursor, is_async=False):
    if not is_async:
        cursor.__wrapped__ = mock.Mock()
        if operation == "execute":
            cursor.execute("SELECT version()")
            return get_dbm_comment(cursor.__wrapped__, "execute")
        elif operation == "executemany":
            cursor.executemany("SELECT version()", [((),)])
            return get_dbm_comment(cursor.__wrapped__, "executemany")
    else:
        cursor.__wrapped__ = mock.AsyncMock()
        if operation == "execute":
            await cursor.execute("SELECT version()")
            return get_dbm_comment(cursor.__wrapped__, "execute")
        elif operation == "executemany":
            await cursor.executemany("SELECT version()", [((),)])
            return get_dbm_comment(cursor.__wrapped__, "executemany")


def get_dbm_comment(wrapped_instance, operation, wrapped_call_args=None):
    if wrapped_call_args is None:
        dbm_comment = getattr(wrapped_instance, operation).call_args.args[0]
    else:
        dbm_comment = wrapped_call_args

    # Store response in a json object
    response = {"status": "ok", "dbm_comment": dbm_comment}
    return Response(json.dumps(response))


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


@app.route("/kinesis/produce")
def produce_kinesis_message():
    stream = flask_request.args.get("stream", "DistributedTracing")
    timeout = int(flask_request.args.get("timeout", 60))

    # we only allow injection into JSON messages encoded as a string
    message = json.dumps({"message": "Hello from Python Producer: Kinesis Context Propagation Test"})
    output = kinesis_produce(stream, message, "1", timeout)
    if "error" in output:
        return output, 400
    else:
        return output, 200


@app.route("/kinesis/consume")
def consume_kinesis_message():
    stream = flask_request.args.get("stream", "DistributedTracing")
    timeout = int(flask_request.args.get("timeout", 60))
    output = kinesis_consume(stream, timeout)
    if "error" in output:
        return output, 400
    else:
        return output, 200


@app.route("/rabbitmq/produce")
def produce_rabbitmq_message():
    reset_dsm_context()

    queue = flask_request.args.get("queue", "DistributedTracingContextPropagation")
    exchange = flask_request.args.get("exchange", "DistributedTracingContextPropagation")
    routing_key = flask_request.args.get("routing_key", "DistributedTracingContextPropagationRoutingKey")
    message = "Hello from Python RabbitMQ Context Propagation Test"
    output = rabbitmq_produce(queue, exchange, routing_key, message)
    if "error" in output:
        return output, 400
    else:
        return output, 200


@app.route("/rabbitmq/consume")
def consume_rabbitmq_message():
    queue = flask_request.args.get("queue", "DistributedTracingContextPropagation")
    exchange = flask_request.args.get("exchange", "DistributedTracingContextPropagation")
    routing_key = flask_request.args.get("routing_key", "DistributedTracingContextPropagationRoutingKey")
    timeout = int(flask_request.args.get("timeout", 60))
    output = rabbitmq_consume(queue, exchange, routing_key, timeout)
    if "error" in output:
        return output, 400
    else:
        return output, 200


@app.route("/dsm")
def dsm():
    logging.basicConfig(
        format="%(asctime)s %(levelname)-8s %(message)s", level=logging.INFO, datefmt="%Y-%m-%d %H:%M:%S",
    )
    integration = flask_request.args.get("integration")
    queue = flask_request.args.get("queue")
    topic = flask_request.args.get("topic")
    stream = flask_request.args.get("stream")
    exchange = flask_request.args.get("exchange")
    routing_key = flask_request.args.get("routing_key")

    logging.info(f"[DSM] Got request with integration: {integration}")

    # force reset DSM context for global tracer and global DSM processor
    reset_dsm_context()

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
            target=rabbitmq_produce, args=(queue, exchange, routing_key, "Hello, RabbitMQ from DSM python!")
        )
        consume_thread = threading.Thread(target=rabbitmq_consume, args=(queue, exchange, routing_key, timeout))
        produce_thread.start()
        consume_thread.start()
        produce_thread.join()
        consume_thread.join()
        logging.info("[RabbitMQ] Returning response")
        response = Response("ok")
    elif integration == "sns":
        produce_thread = threading.Thread(target=sns_produce, args=(queue, topic, "Hello, SNS->SQS from DSM python!",))
        consume_thread = threading.Thread(target=sns_consume, args=(queue,))
        produce_thread.start()
        consume_thread.start()
        produce_thread.join()
        consume_thread.join()
        logging.info("[SNS->SQS] Returning response")
        response = Response("ok")
    elif integration == "kinesis":
        timeout = int(flask_request.args.get("timeout", "60"))
        message = json.dumps({"message": "Hello from Python DSM Kinesis test"})

        produce_thread = threading.Thread(target=kinesis_produce, args=(stream, message, "1", timeout))
        consume_thread = threading.Thread(target=kinesis_consume, args=(stream, timeout))
        produce_thread.start()
        consume_thread.start()
        produce_thread.join()
        consume_thread.join()
        logging.info("[Kinesis] Returning response")
        response = Response("ok")

    # force flush stats to ensure they're available to agent after test setup is complete
    tracer.data_streams_processor.periodic()
    data_streams_processor().periodic()
    return response


@app.route("/dsm/inject")
def inject_dsm_context():
    topic = flask_request.args.get("topic")
    integration = flask_request.args.get("integration")
    headers = {}

    reset_dsm_context()

    ctx = data_streams_processor().set_checkpoint(["direction:out", "topic:" + topic, "type:" + integration])
    DsmPathwayCodec.encode(ctx, headers)

    return Response(json.dumps(headers))


@app.route("/dsm/extract")
def extract_dsm_context():
    topic = flask_request.args.get("topic")
    integration = flask_request.args.get("integration")
    ctx = flask_request.args.get("ctx")

    reset_dsm_context()

    ctx = DsmPathwayCodec.decode(json.loads(ctx), data_streams_processor())
    ctx.set_checkpoint(["direction:in", "topic:" + topic, "type:" + integration])

    return Response("ok")


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
    try:
        os.mkdir(path)
    except FileExistsError:
        pass
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
