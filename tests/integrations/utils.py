import hashlib
import os
import struct
import time
from typing import Callable

import boto3
import botocore.exceptions

from utils import weblog, interfaces
from utils.tools import logger


class BaseDbIntegrationsTestClass:
    """ define a setup function that perform a request to the weblog for each operation: select, update... """

    db_service = None
    requests = {}

    def _setup(self):
        """ 
            Make request to weblog for each operation: select, update... 
            those requests will be permored only one time for the entire test run
        """

        assert self.db_service is not None, "db_service must be defined"

        if self.db_service in BaseDbIntegrationsTestClass.requests:
            return  #  requests has been made ...

        BaseDbIntegrationsTestClass.requests[self.db_service] = {}

        # Initiaze DB
        logger.info("Initializing DB...")
        response_db_creation = weblog.get(
            "/db", params={"service": self.db_service, "operation": "init"}, timeout=20
        )  # DB initialization can take more time ( mssql )
        logger.info(f"Response from de init endpoint: {response_db_creation.text}")

        # Request for db operations
        logger.info("Perform queries.....")
        for db_operation in ["select", "insert", "update", "delete", "procedure", "select_error"]:
            BaseDbIntegrationsTestClass.requests[self.db_service][db_operation] = weblog.get(
                "/db", params={"service": self.db_service, "operation": db_operation}
            )
        if self.db_service == "mssql":
            # Nodejs opentelemetry-instrumentation-mssql is too old and select query is not tracer allways
            # see https://github.com/mnadeem/opentelemetry-instrumentation-mssql
            # Retry to avoid flakyness
            logger.debug("Retry select query for mssql .....")
            BaseDbIntegrationsTestClass.requests[self.db_service]["select"] = weblog.get(
                "/db", params={"service": self.db_service, "operation": "select"}
            )

    # Setup methods. We set here to avoid duplication in child classes, even if some test metohs doesn't exists
    setup_properties = _setup
    setup_sql_traces = _setup
    setup_resource = _setup
    setup_db_type = _setup
    setup_db_name = _setup
    setup_error = _setup
    setup_db_mssql_instance_name = _setup
    setup_db_jdbc_drive_classname = _setup
    setup_db_password = _setup
    setup_db_row_count = _setup
    setup_db_sql_table = _setup
    setup_db_operation = _setup
    setup_db_instance = _setup
    setup_db_user = _setup
    setup_db_connection_string = _setup
    setup_db_system = _setup
    setup_runtime_id = _setup
    setup_span_kind = _setup
    setup_sql_traces = _setup
    setup_resource = _setup
    setup_db_type = _setup
    setup_db_name = _setup
    setup_error_type_and_stack = _setup
    setup_error_message = _setup
    setup_obfuscate_query = _setup
    setup_sql_query = _setup
    setup_sql_success = _setup
    setup_NOT_obfuscate_query = _setup

    def get_requests(self, excluded_operations=(), operations=None):
        for db_operation, request in self.requests[self.db_service].items():
            if operations is not None and db_operation not in operations:
                continue

            if db_operation not in excluded_operations:
                yield db_operation, request

    @staticmethod
    def get_span_from_tracer(weblog_request):
        for _, _, span in interfaces.library.get_spans(weblog_request):
            logger.info(f"Span found with trace id: {span['trace_id']} and span id: {span['span_id']}")

            # iterate over all trace to be sure to miss nothing
            for _, _, span_child in interfaces.library.get_spans():
                if span_child["trace_id"] != span["trace_id"]:
                    continue

                logger.debug(f"Check if span {span_child['span_id']} could match")

                if span_child["resource"] == "SELECT 1;":  # workaround to avoid conflicts on connection check on mssql
                    logger.debug(f"Wrong resource:{span_child.get('resource')}, continue...")
                    continue

                if span_child.get("type") != "sql":
                    logger.debug(f"Wrong type:{span_child.get('type')}, continue...")
                    continue

                logger.info(f"Span type==sql found: {span_child['span_id']}")
                return span_child

        raise ValueError(f"Span is not found for {weblog_request.request.url}")

    @staticmethod
    def get_span_from_agent(weblog_request):
        for data, span in interfaces.agent.get_spans(weblog_request):
            logger.debug(f"Span found: trace id={span['traceID']}; span id={span['spanID']} ({data['log_filename']})")

            # iterate over everything to be sure to miss nothing
            for _, span_child in interfaces.agent.get_spans():
                if span_child["traceID"] != span["traceID"]:
                    continue

                logger.debug(f"Checking if span {span_child['spanID']} could match")

                if span_child.get("type") not in ("sql", "db"):
                    logger.debug(f"Wrong type:{span_child.get('type')}, continue...")
                    # no way it's the span we're looking for
                    continue

                # workaround to avoid conflicts on connection check on mssql
                # workaround to avoid conflicts on connection check on mssql + nodejs + opentelemetry (there is a bug in the sql obfuscation)
                if span_child["resource"] in ("SELECT ?", "SELECT 1;"):
                    logger.debug(f"Wrong resource:{span_child.get('resource')}, continue...")
                    continue

                # workaround to avoid conflicts on postgres + nodejs + opentelemetry
                if span_child["name"] == "pg.connect":
                    logger.debug(f"Wrong name:{span_child.get('name')}, continue...")
                    continue

                # workaround to avoid conflicts on mssql + nodejs + opentelemetry
                if span_child["meta"].get("db.statement") == "SELECT 1;":
                    logger.debug(f"Wrong db.statement:{span_child.get('meta', {}).get('db.statement')}, continue...")
                    continue

                logger.info(f"Span type==sql found: spanId={span_child['spanID']}")

                return span_child

        raise ValueError(f"Span is not found for {weblog_request.request.url}")
    

# set AWS credentials for runner
os.environ["AWS_ACCESS_KEY_ID"] = os.environ.get("SYSTEM_TESTS_AWS_ACCESS_KEY_ID", "")
os.environ["AWS_SECRET_ACCESS_KEY"] = os.environ.get("SYSTEM_TESTS_AWS_SECRET_ACCESS_KEY", "")
os.environ["AWS_DEFAULT_REGION"] = os.environ.get("SYSTEM_TESTS_AWS_REGION", "us-east-1")


def delete_aws_resource(
    delete_callable: Callable,
    resource_identifier: str,
    resource_type: str,
    error_name: str,
    get_callable: Callable = None,
):
    """
    Generalized function to delete AWS resources.
    
    :param delete_callable: A callable to delete the AWS resource.
    :param resource_identifier: The identifier of the resource (e.g., QueueUrl, TopicArn, StreamName).
    :param resource_type: The type of the resource (e.g., SQS, SNS, Kinesis).
    :param error_name: The name of the error to handle (e.g., 'QueueDoesNotExist').
    :param get_callable: An optional get callable to get the AWS resource, used to trigger an exception
    confirming the resource is deleted (in cases where the delete resource returns void).
    """
    timeout = 20
    end = time.time() + timeout
    while time.time() < end:
        try:
            # Call the delete function
            _ = delete_callable(resource_identifier)

            if get_callable:
                # if the resource is not found via the getter, it will throw an error with the error name
                _ = get_callable(resource_identifier)

        except botocore.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == error_name:
                logger.info(f"{resource_type} {resource_identifier} already deleted.")
                return
            else:
                logger.error(f"Unexpected error while deleting {resource_type}: {e}")
                raise
        except Exception as e:
            logger.error(f"Unexpected error while deleting {resource_type}: {e}")
            raise


def delete_sqs_queue(queue_name):
    queue_url = f"https://sqs.us-east-1.amazonaws.com/601427279990/{queue_name}"
    sqs_client = boto3.client("sqs")
    delete_callable = lambda url: sqs_client.delete_queue(QueueUrl=url)
    get_callable = lambda url: sqs_client.get_queue_attributes(QueueUrl=url)
    delete_aws_resource(
        delete_callable, queue_url, "SQS Queue", "AWS.SimpleQueueService.NonExistentQueue", get_callable=get_callable
    )


def delete_sns_topic(topic_name):
    topic_arn = f"arn:aws:sns:us-east-1:601427279990:{topic_name}"
    sns_client = boto3.client("sns")
    get_callable = lambda arn: sns_client.get_topic_attributes(TopicArn=arn)
    delete_callable = lambda arn: sns_client.delete_topic(TopicArn=arn)
    delete_aws_resource(delete_callable, topic_arn, "SNS Topic", "NotFound", get_callable=get_callable)


def delete_kinesis_stream(stream_name):
    kinesis_client = boto3.client("kinesis")
    delete_callable = lambda name: kinesis_client.delete_stream(StreamName=name, EnforceConsumerDeletion=True)
    delete_aws_resource(delete_callable, stream_name, "Kinesis Stream", "ResourceNotFoundException")


def fnv(data, hval_init, fnv_prime, fnv_size):
    # type: (bytes, int, int, int) -> int
    """
    Core FNV hash algorithm used in FNV0 and FNV1.
    """
    hval = hval_init
    for byte in data:
        hval = (hval * fnv_prime) % fnv_size
        hval = hval ^ byte
    return hval


FNV_64_PRIME = 0x100000001B3
FNV1_64_INIT = 0xCBF29CE484222325


def fnv1_64(data):
    # type: (bytes) -> int
    """
    Returns the 64 bit FNV-1 hash value for the given data.
    """
    return fnv(data, FNV1_64_INIT, FNV_64_PRIME, 2 ** 64)


def compute_dsm_hash(parent_hash, tags):
    def get_bytes(s):
        return bytes(s, encoding="utf-8")

    b = get_bytes("weblog") + get_bytes("system-tests")
    for t in tags:
        b += get_bytes(t)
    node_hash = fnv1_64(b)
    return fnv1_64(struct.pack("<Q", node_hash) + struct.pack("<Q", parent_hash))


def sha_hash(checkpoint_string):
    if isinstance(checkpoint_string, str):
        checkpoint_string = checkpoint_string.encode("utf-8")
    hash_obj = hashlib.md5(checkpoint_string).digest()[:8]
    return hash_obj


def compute_dsm_hash_nodejs(parent_hash, edge_tags):
    current_hash = sha_hash(f"{'weblog'}{'system-tests'}{''.join(edge_tags)}")
    parent_hash_buf = struct.pack(">Q", parent_hash)
    buf = current_hash + parent_hash_buf

    val = sha_hash(buf)
    return int.from_bytes(val, "big")
