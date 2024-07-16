import os
import random
import subprocess

# set Datadog as Otel Trace Provider
if os.environ.get("DD_TRACE_OTEL_ENABLED", False):
    from opentelemetry.trace import set_tracer_provider
    from ddtrace.opentelemetry import TracerProvider

    set_tracer_provider(TracerProvider())

    # when using ddtrace with otel, we need to manually patch otel contribs
    from opentelemetry.instrumentation.botocore import BotocoreInstrumentor
    from opentelemetry.instrumentation.confluent_kafka import ConfluentKafkaInstrumentor
    from opentelemetry.instrumentation.flask import FlaskInstrumentor

    BotocoreInstrumentor().instrument()
    ConfluentKafkaInstrumentor().instrument()
    FlaskInstrumentor().instrument()

import psycopg2
import requests

from flask import Flask
from flask import request as flask_request

from integrations.db.mssql import executeMssqlOperation
from integrations.db.mysqldb import executeMysqlOperation
from integrations.db.postgres import executePostgresOperation

if os.environ.get("INCLUDE_KAFKA", "true") == "true":
    from integrations.messaging.kafka import kafka_consume
    from integrations.messaging.kafka import kafka_produce


from integrations.messaging.aws.sqs import sqs_consume
from integrations.messaging.aws.sqs import sqs_produce


app = Flask(__name__)


@app.route("/")
def hello_world():
    return "Hello, World!\\n"


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


@app.route("/kafka/produce")
def produce_kafka_message():
    """
    The goal of this endpoint is to trigger kafka producer calls
    """
    topic = flask_request.args.get("topic", "DistributedTracing")
    message = b"Distributed Tracing Test from Python OpenTelemetry for Kafka!"
    output = kafka_produce(topic, message)
    print(output)
    if "error" in output:
        return output, 400
    else:
        return output, 200


@app.route("/kafka/consume")
def consume_kafka_message():
    """
    The goal of this endpoint is to trigger Python OpenTelemetry kafka consumer calls
    """
    topic = flask_request.args.get("topic", "DistributedTracing")
    timeout = int(flask_request.args.get("timeout", 60))
    output = kafka_consume(topic, "apm_test", timeout)
    print(output)
    if "error" in output:
        return output, 400
    else:
        return output, 200


@app.route("/sqs/produce")
def produce_sqs_message():
    queue = flask_request.args.get("queue", "DistributedTracing")
    message = "Hello from Python Otel SQS"
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
