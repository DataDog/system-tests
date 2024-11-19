import base64
import http.client
import json
import logging
import os
import random
import subprocess
import sys
import threading
import urllib.request

import boto3
from moto import mock_aws
import mock
import urllib3
import xmltodict


if os.environ.get("INCLUDE_POSTGRES", "true") == "true":
    import asyncpg
    import psycopg2

if os.environ.get("INCLUDE_MYSQL", "true") == "true":
    import aiomysql
    import mysql
    import MySQLdb
    import pymysql

from flask import Flask
from flask import Response
from flask import jsonify
from flask import request
from flask import request as flask_request
from flask_login import LoginManager
from flask_login import login_user
from iast import weak_cipher
from iast import weak_cipher_secure_algorithm
from iast import weak_hash
from iast import weak_hash_duplicates
from iast import weak_hash_multiple
from iast import weak_hash_secure_algorithm
import requests


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
from ddtrace import Pin
from ddtrace import tracer
from ddtrace.appsec import trace_utils as appsec_trace_utils
from ddtrace.internal.datastreams import data_streams_processor
from ddtrace.internal.datastreams.processor import DsmPathwayCodec
from ddtrace.data_streams import set_consume_checkpoint
from ddtrace.data_streams import set_produce_checkpoint

from debugger_controller import debugger_blueprint

# Patch kombu and urllib3 since they are not patched automatically
ddtrace.patch_all(kombu=True, urllib3=True)

try:
    from ddtrace.contrib.trace_utils import set_user
except ImportError:
    set_user = lambda *args, **kwargs: None

POSTGRES_CONFIG = dict(
    host="postgres",
    port="5433",
    user="system_tests_user",
    password="system_tests",
    dbname="system_tests_dbname",
)
ASYNCPG_CONFIG = dict(POSTGRES_CONFIG)
ASYNCPG_CONFIG["database"] = ASYNCPG_CONFIG["dbname"]  # asyncpg uses 'database' instead of 'dbname'
del ASYNCPG_CONFIG["dbname"]

MYSQL_CONFIG = dict(
    host="mysqldb",
    port=3306,
    user="mysqldb",
    password="mysqldb",
    database="mysql_dbname",
)
AIOMYSQL_CONFIG = dict(MYSQL_CONFIG)
AIOMYSQL_CONFIG["db"] = AIOMYSQL_CONFIG["database"]
del AIOMYSQL_CONFIG["database"]

MARIADB_CONFIG = dict(AIOMYSQL_CONFIG)
MARIADB_CONFIG["collation"] = "utf8mb4_unicode_520_ci"

app = Flask(__name__)
app.secret_key = "SECRET_FOR_TEST"
app.config["SESSION_TYPE"] = "memcached"
app.register_blueprint(debugger_blueprint)
login_manager = LoginManager()
login_manager.login_view = "login"
login_manager.init_app(app)
DB_AUTH = set()


@login_manager.user_loader
def load_user(user_id):
    return User.get(user_id)


class User:
    def __init__(self, uid, login, passwd, email):
        self.uid, self.login, self.passwd, self.email = uid, login, passwd, email

    def get_id(self):
        return self.uid

    @property
    def is_anonymous(self):
        return False

    @property
    def is_active(self):
        return True

    @property
    def is_authenticated(self):
        return self.uid in DB_AUTH

    @staticmethod
    def check(name, passwd):
        if name in DB_USER:
            return passwd == DB_USER[name].passwd, DB_USER[name]
        return False, None

    @staticmethod
    def get(uid):
        for user in DB_USER.values():
            if uid == user.uid:
                return user


DB_USER = {
    "test": User("social-security-id", "test", "1234", "testuser@ddog.com"),
    "testuuid": User("591dc126-8431-4d0f-9509-b23318d3dce4", "testuuid", "1234", "testuseruuid@ddog.com"),
}

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


def flush_dsm_checkpoints():
    # force flush stats to ensure they're available to agent after test setup is complete
    tracer.data_streams_processor.periodic()
    data_streams_processor().periodic()


@app.route("/")
def hello_world():
    return "Hello, World!\\n"


@app.route("/healthcheck")
def healthcheck():
    return {
        "status": "ok",
        "library": {
            "language": "python",
            "version": ddtrace.__version__,
        },
    }


@app.route("/sample_rate_route/<i>")
def sample_rate(i):
    return "OK"


_TRACK_CUSTOM_APPSEC_EVENT_NAME = "system_tests_appsec_event"


@app.route("/waf", methods=["GET", "POST", "OPTIONS"])
@app.route("/waf/", methods=["GET", "POST", "OPTIONS"])
@app.route("/waf/<path:url>", methods=["GET", "POST", "OPTIONS"])
@app.route("/params/<path>", methods=["GET", "POST", "OPTIONS"])
@app.route(
    "/tag_value/<string:tag_value>/<int:status_code>",
    methods=["GET", "POST", "OPTIONS"],
)
def waf(*args, **kwargs):
    if "tag_value" in kwargs:
        appsec_trace_utils.track_custom_event(
            tracer,
            event_name=_TRACK_CUSTOM_APPSEC_EVENT_NAME,
            metadata={"value": kwargs["tag_value"]},
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


@app.route("/rasp/sqli", methods=["GET", "POST"])
def rasp_sqli(*args, **kwargs):
    user_id = None
    if request.method == "GET":
        user_id = flask_request.args.get("user_id")
    elif request.method == "POST":
        try:
            user_id = (request.form or request.json or {}).get("user_id")
        except Exception as e:
            print(repr(e), file=sys.stderr)
        try:
            if user_id is None:
                user_id = xmltodict.parse(flask_request.data).get("user_id")
        except Exception as e:
            print(repr(e), file=sys.stderr)
            pass

    if user_id is None:
        return "missing user_id parameter", 400
    try:
        import sqlite3

        DB = sqlite3.connect(":memory:")
        print(f"SELECT * FROM users WHERE id='{user_id}'")
        cursor = DB.execute(f"SELECT * FROM users WHERE id='{user_id}'")
        print("DB request with {len(list(cursor))} results")
        return f"DB request with {len(list(cursor))} results"
    except Exception as e:
        print(f"DB request failure: {e!r}", file=sys.stderr)
        return f"DB request failure: {e!r}", 201


@app.route("/rasp/shi", methods=["GET", "POST"])
def rasp_shi(*args, **kwargs):
    list_dir = None
    if request.method == "GET":
        list_dir = flask_request.args.get("list_dir")
    elif request.method == "POST":
        try:
            list_dir = (request.form or request.json or {}).get("list_dir")
        except Exception as e:
            print(repr(e), file=sys.stderr)
        try:
            if list_dir is None:
                list_dir = xmltodict.parse(flask_request.data).get("list_dir")
        except Exception as e:
            print(repr(e), file=sys.stderr)
            pass

    if list_dir is None:
        return "missing user_id parameter", 400
    try:
        command = f"ls {list_dir}"
        res = os.system(command)
        return f"Shell command [{command}] with result: {res}", 200
    except Exception as e:
        print(f"Shell command failure: {e!r}", file=sys.stderr)
        return f"Shell command failure: {e!r}", 201


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


@app.route("/stats-unique")
def stats_unique():
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


MAGIC_SESSION_KEY = "random_session_id"


@app.route("/session/new")
def session_new():
    response = Response("OK")
    response.set_cookie("session_id", MAGIC_SESSION_KEY)
    return response


@app.route("/session/user")
def session_user():
    user = flask_request.args.get("sdk_user", "")
    if user and flask_request.cookies.get("session_id", "") == MAGIC_SESSION_KEY:
        appsec_trace_utils.track_user_login_success_event(tracer, user_id=user, session_id=f"session_{user}")
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
        conn = mysql.connector.connect(**MARIADB_CONFIG)
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
    message = flask_request.args.get("message", "Hello from Python SQS")

    output = sqs_produce(queue, message)
    if "error" in output:
        return output, 400
    else:
        return output, 200


@app.route("/sqs/consume")
def consume_sqs_message():
    queue = flask_request.args.get("queue", "DistributedTracing")
    timeout = int(flask_request.args.get("timeout", 60))
    message = flask_request.args.get("message", "Hello from Python SQS")

    output = sqs_consume(queue, message, timeout)
    if "error" in output:
        return output, 400
    else:
        return output, 200


@app.route("/sns/produce")
def produce_sns_message():
    queue = flask_request.args.get("queue", "DistributedTracing SNS")
    topic = flask_request.args.get("topic", "DistributedTracing SNS Topic")
    message = flask_request.args.get("message", "Hello from Python SNS -> SQS")

    output = sns_produce(queue, topic, message)
    if "error" in output:
        return output, 400
    else:
        return output, 200


@app.route("/sns/consume")
def consume_sns_message():
    queue = flask_request.args.get("queue", "DistributedTracing SNS")
    timeout = int(flask_request.args.get("timeout", 60))
    message = flask_request.args.get("message", "Hello from Python SNS -> SQS")

    output = sns_consume(queue, message, timeout)
    if "error" in output:
        return output, 400
    else:
        return output, 200


@app.route("/kinesis/produce")
def produce_kinesis_message():
    stream = flask_request.args.get("stream", "DistributedTracing")
    timeout = int(flask_request.args.get("timeout", 60))
    message = flask_request.args.get("message", "Hello from Python Producer: Kinesis Context Propagation Test")

    output = kinesis_produce(stream, message, "1", timeout)
    if "error" in output:
        return output, 400
    else:
        return output, 200


@app.route("/kinesis/consume")
def consume_kinesis_message():
    stream = flask_request.args.get("stream", "DistributedTracing")
    timeout = int(flask_request.args.get("timeout", 60))
    message = flask_request.args.get("message", "Hello from Python Producer: Kinesis Context Propagation Test")

    output = kinesis_consume(stream, message, timeout)
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
        format="%(asctime)s %(levelname)-8s %(message)s",
        level=logging.INFO,
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    integration = flask_request.args.get("integration")
    queue = flask_request.args.get("queue")
    topic = flask_request.args.get("topic")
    stream = flask_request.args.get("stream")
    exchange = flask_request.args.get("exchange")
    routing_key = flask_request.args.get("routing_key")
    message = flask_request.args.get("message")

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
            target=kafka_produce,
            args=(
                queue,
                b"Hello, Kafka from DSM python!",
                delivery_report,
            ),
        )
        consume_thread = threading.Thread(
            target=kafka_consume,
            args=(
                queue,
                "testgroup1",
            ),
        )
        produce_thread.start()
        consume_thread.start()
        produce_thread.join()
        consume_thread.join()
        logging.info("[kafka] Returning response")
        response = Response("ok")
    elif integration == "sqs":
        produce_thread = threading.Thread(
            target=sqs_produce,
            args=(
                queue,
                message,
            ),
        )
        consume_thread = threading.Thread(
            target=sqs_consume,
            args=(
                queue,
                message,
            ),
        )
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
        produce_thread = threading.Thread(
            target=sns_produce,
            args=(
                queue,
                topic,
                message,
            ),
        )
        consume_thread = threading.Thread(
            target=sns_consume,
            args=(
                queue,
                message,
            ),
        )
        produce_thread.start()
        consume_thread.start()
        produce_thread.join()
        consume_thread.join()
        logging.info("[SNS->SQS] Returning response")
        response = Response("ok")
    elif integration == "kinesis":
        timeout = int(flask_request.args.get("timeout", "60"))

        produce_thread = threading.Thread(target=kinesis_produce, args=(stream, message, "1", timeout))
        consume_thread = threading.Thread(target=kinesis_consume, args=(stream, message, timeout))
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


@app.route("/dsm/manual/produce")
def dsm_manual_checkpoint_produce():
    reset_dsm_context()
    typ = flask_request.args.get("type")
    target = flask_request.args.get("target")
    headers = {}

    def setter(k, v):
        headers[k] = v

    set_produce_checkpoint(typ, target, setter)
    flush_dsm_checkpoints()

    # headers = quote(headers)

    logging.info(f"[DSM Manual Produced with Thread] Injected Headers: {headers}")

    return Response("ok", headers=headers)


@app.route("/dsm/manual/produce_with_thread")
def dsm_manual_checkpoint_produce_with_thread():
    reset_dsm_context()

    def worker(typ, target, headers):
        def setter(k, v):
            headers[k] = v

        set_produce_checkpoint(typ, target, setter)

    typ = flask_request.args.get("type")
    target = flask_request.args.get("target")
    headers = {}

    # Start a new thread to run the worker function
    thread = threading.Thread(target=worker, args=(typ, target, headers))
    thread.start()
    thread.join()  # Wait for the thread to complete for this example
    flush_dsm_checkpoints()

    # headers = quote(headers)

    logging.info(f"[DSM Manual Produce with Thread] Injected Headers: {headers}")

    return Response("ok", headers=headers)


@app.route("/dsm/manual/consume")
def dsm_manual_checkpoint_consume():
    reset_dsm_context()

    typ = flask_request.args.get("type")
    source = flask_request.args.get("source")
    carrier = json.loads(flask_request.headers.get("_datadog"))
    logging.info(f"[DSM Manual Consume] Received Headers: {carrier}")

    def getter(k):
        return carrier[k]

    set_consume_checkpoint(typ, source, getter)
    flush_dsm_checkpoints()
    return Response("ok")


@app.route("/dsm/manual/consume_with_thread")
def dsm_manual_checkpoint_consume_with_thread():
    reset_dsm_context()

    def worker(typ, target, headers):
        logging.info(f"[DSM Manual Consume With Thread] Received Headers: {headers}")

        def getter(k):
            return headers[k]

        set_consume_checkpoint(typ, target, getter)

    typ = flask_request.args.get("type")
    source = flask_request.args.get("source")
    carrier = json.loads(flask_request.headers.get("_datadog"))

    # Start a new thread to run the worker function
    thread = threading.Thread(target=worker, args=(typ, source, carrier))
    thread.start()
    thread.join()  # Wait for the thread to complete for this example
    flush_dsm_checkpoints()

    return Response("ok")


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


def _sink_point_sqli(table="user", id="1"):
    sql = "SELECT * FROM " + table + " WHERE id = '" + id + "'"
    postgres_db = psycopg2.connect(**POSTGRES_CONFIG)
    cursor = postgres_db.cursor()
    try:
        cursor.execute(sql)
    except Exception:
        pass


def _sink_point_path_traversal(tainted_str="user"):
    try:
        m = open(tainted_str)
        _ = m.read()
    except Exception:
        pass


@app.route("/iast/source/body/test", methods=["POST"])
def view_iast_source_body():
    table = flask_request.json.get("name")
    _sink_point_sqli(table=table)
    return Response("OK")


@app.route("/iast/source/cookiename/test")
def view_iast_source_cookie_name():
    param = [key for key in flask_request.cookies.keys() if key == "table"]
    _sink_point_path_traversal(param[0])
    return Response("OK")


@app.route("/iast/source/cookievalue/test")
def view_iast_source_cookie_value():
    table = flask_request.cookies.get("table")
    _sink_point_sqli(table=table)
    return Response("OK")


@app.route("/iast/source/headername/test")
def view_iast_source_header_name():
    param = [key for key in flask_request.headers.keys() if key == "User"]
    _sink_point_sqli(id=param[0])
    return Response("OK")


@app.route("/iast/source/header/test")
def view_iast_source_header_value():
    table = flask_request.headers.get("table")
    _sink_point_sqli(table=table)
    return Response("OK")


@app.route("/iast/source/parametername/test", methods=["GET"])
def view_iast_source_parametername_get():
    param = [key for key in flask_request.args.keys() if key == "user"]
    _sink_point_sqli(id=param[0])
    return Response("OK")


@app.route("/iast/source/parametername/test", methods=["POST"])
def view_iast_source_parametername_post():
    param = [key for key in flask_request.form.keys() if key == "user"]
    _sink_point_sqli(id=param[0])
    return Response("OK")


@app.route("/iast/source/parameter/test", methods=["GET", "POST"])
def view_iast_source_parameter():
    if flask_request.args:
        table = flask_request.args.get("table")
    else:
        table = flask_request.form.get("table")
    _sink_point_sqli(table=table)
    return Response("OK")


@app.route("/iast/source/path/test", methods=["GET", "POST"])
def view_iast_source_path():
    table = flask_request.path
    _sink_point_sqli(table=table)
    return Response("OK")


@app.route("/iast/source/path_parameter/test/<string:table>", methods=["GET", "POST"])
def view_iast_source_path_parameter(table):
    _sink_point_sqli(table=table)
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


@app.route("/iast/header_injection/test_insecure", methods=["POST"])
def view_iast_header_injection_insecure():
    header = flask_request.form["test"]
    resp = Response("OK")
    resp.headers["Header-Injection"] = header
    return resp


@app.route("/iast/header_injection/test_secure", methods=["POST"])
def view_iast_header_injection_secure():
    header = flask_request.form["test"]
    resp = Response("OK")
    resp.headers["Vary"] = header
    return resp


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
        tracer,
        user_id=_TRACK_USER,
        exists=True,
        metadata=_TRACK_METADATA,
    )
    return Response("OK")


@app.route("/login", methods=["GET", "POST"])
def login():
    username = flask_request.form.get("username")
    password = flask_request.form.get("password")
    sdk_event = flask_request.args.get("sdk_event")
    if sdk_event:
        sdk_user = flask_request.args.get("sdk_user")
        sdk_mail = flask_request.args.get("sdk_mail")
        sdk_user_exists = flask_request.args.get("sdk_user_exists")
        if sdk_event == "success":
            appsec_trace_utils.track_user_login_success_event(tracer, user_id=sdk_user, email=sdk_mail)
            return Response("OK")
        elif sdk_event == "failure":
            appsec_trace_utils.track_user_login_failure_event(
                tracer, user_id=sdk_user, email=sdk_mail, exists=sdk_user_exists
            )
            return Response("login failure", status=401)
    authorisation = flask_request.headers.get("Authorization")
    if authorisation:
        username, password = base64.b64decode(authorisation[6:]).decode().split(":")
    success, user = User.check(username, password)
    if success:
        login_user(user)
        appsec_trace_utils.track_user_login_success_event(tracer, user_id=user.uid, login_events_mode="auto")
        return Response("OK")
    elif user:
        appsec_trace_utils.track_user_login_failure_event(
            tracer,
            user_id=user.uid,
            exists=True,
            login_events_mode="auto",
        )
    else:
        appsec_trace_utils.track_user_login_failure_event(
            tracer, user_id=username, exists=False, login_events_mode="auto"
        )
    return Response("login failure", status=401)


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


@app.route("/set_cookie", methods=["GET"])
def set_cookie():
    name = flask_request.args.get("name")
    value = flask_request.args.get("value")
    resp = Response("OK")
    resp.headers["Set-Cookie"] = f"{name}={value}"
    return resp


@app.route("/iast/insecure-cookie/test_insecure")
def test_insecure_cookie():
    resp = Response("OK")
    resp.set_cookie("insecure", "cookie", secure=False, httponly=True, samesite="Strict")
    return resp


@app.route("/iast/insecure-cookie/test_secure")
def test_secure_cookie():
    resp = Response("OK")
    resp.set_cookie(key="secure3", value="value", secure=True, httponly=True, samesite="Strict")
    return resp


@app.route("/iast/insecure-cookie/test_empty_cookie")
def test_insecure_cookie_empty_cookie():
    resp = Response("OK")
    resp.set_cookie("insecure", "", secure=False, httponly=True, samesite="Strict")
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
    resp.set_cookie(key="secure3", value="", secure=True, httponly=False, samesite="Strict")
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


@app.route("/iast/no-samesite-cookie/test_empty_cookie")
def test_no_samesite_empty_cookie():
    resp = Response("OK")
    resp.set_cookie("insecure", "", secure=True, httponly=True, samesite="None")
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


@app.route("/requestdownstream", methods=["GET", "POST", "OPTIONS"])
@app.route("/requestdownstream/", methods=["GET", "POST", "OPTIONS"])
def request_downstream():
    # Propagate the received headers to the downstream service
    http = urllib3.PoolManager()
    # Sending a GET request and getting back response as HTTPResponse object.
    response = http.request("GET", "http://localhost:7777/returnheaders")
    return Response(response.data)


@app.route("/returnheaders", methods=["GET", "POST", "OPTIONS"])
@app.route("/returnheaders/", methods=["GET", "POST", "OPTIONS"])
def return_headers(*args, **kwargs):
    headers = {}
    for key, value in flask_request.headers.items():
        headers[key] = value
    return jsonify(headers)


@app.route("/vulnerablerequestdownstream", methods=["GET", "POST", "OPTIONS"])
@app.route("/vulnerablerequestdownstream/", methods=["GET", "POST", "OPTIONS"])
def vulnerable_request_downstream():
    weak_hash()
    # Propagate the received headers to the downstream service
    http = urllib3.PoolManager()
    # Sending a GET request and getting back response as HTTPResponse object.
    response = http.request("GET", "http://localhost:7777/returnheaders")
    return Response(response.data)


@app.route("/mock_s3/put_object", methods=["GET", "POST", "OPTIONS"])
def s3_put_object():
    bucket = flask_request.args.get("bucket")
    key = flask_request.args.get("key")
    body: str = flask_request.args.get("key")

    with mock_aws():
        conn = boto3.resource("s3", region_name="us-east-1")
        conn.create_bucket(Bucket=bucket)
        response = conn.Bucket(bucket).put_object(Bucket=bucket, Key=key, Body=body.encode("utf-8"))

        # boto adds double quotes to the ETag
        # so we need to remove them to match what would have done AWS
        result = {
            "result": "ok",
            "object": {
                "e_tag": response.e_tag.replace('"', ""),
            },
        }

    return jsonify(result)


@app.route("/mock_s3/copy_object", methods=["GET", "POST", "OPTIONS"])
def s3_copy_object():
    original_bucket = flask_request.args.get("original_bucket")
    original_key = flask_request.args.get("original_key")
    body: str = flask_request.args.get("original_key")

    copy_source = {
        "Bucket": original_bucket,
        "Key": original_key,
    }

    bucket = flask_request.args.get("bucket")
    key = flask_request.args.get("key")

    with mock_aws():
        conn = boto3.resource("s3", region_name="us-east-1")
        conn.create_bucket(Bucket=original_bucket)
        conn.Bucket(original_bucket).put_object(Bucket=original_bucket, Key=original_key, Body=body.encode("utf-8"))

        if bucket != original_bucket:
            conn.create_bucket(Bucket=bucket)
        response = conn.Object(bucket, key).copy_from(CopySource=copy_source)

        # boto adds double quotes to the ETag
        # so we need to remove them to match what would have done AWS
        result = {
            "result": "ok",
            "object": {
                "e_tag": response["CopyObjectResult"]["ETag"].replace('"', ""),
            },
        }

    return jsonify(result)


@app.route("/mock_s3/multipart_upload", methods=["GET", "POST", "OPTIONS"])
def s3_multipart_upload():
    bucket = flask_request.args.get("bucket")
    key = flask_request.args.get("key")
    body_base: str = flask_request.args.get("key")
    body = (body_base + "x" * 15_000_000).encode("utf-8")  # 15MB of padding

    split_index = len(body) // 2
    body_part_1 = body[:split_index]
    body_part_2 = body[split_index:]

    with mock_aws():
        conn = boto3.resource("s3", region_name="us-east-1")
        conn.create_bucket(Bucket=bucket)

        multipart_upload = conn.Object(bucket, key).initiate_multipart_upload()
        part_1_response = multipart_upload.Part(1).upload(Body=body_part_1)
        part_2_response = multipart_upload.Part(2).upload(Body=body_part_2)
        response = multipart_upload.complete(
            MultipartUpload={
                "Parts": [
                    {"PartNumber": 1, "ETag": part_1_response["ETag"]},
                    {"PartNumber": 2, "ETag": part_2_response["ETag"]},
                ],
            },
        )

        # boto adds double quotes to the ETag
        # so we need to remove them to match what would have done AWS
        result = {
            "result": "ok",
            "object": {
                "e_tag": response.e_tag.replace('"', ""),
            },
        }

    return jsonify(result)
