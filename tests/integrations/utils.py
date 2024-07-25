from datetime import datetime
import hashlib
import struct

from utils import weblog, interfaces
from utils.tools import logger

import boto3


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


def delete_sqs_queue(queue_name):
    queue_url = f"https://sqs.us-east-1.amazonaws.com/601427279990/{queue_name}"
    sqs_client = boto3.client("sqs")
    try:
        sqs_client.delete_queue(QueueUrl=queue_url)
    except Exception:
        pass


def delete_sns_topic(topic_name):
    topic_arn = f"arn:aws:sns:us-east-1:601427279990:{topic_name}"
    sns_client = boto3.client("sns")
    try:
        sns_client.delete_topic(TopicArn=topic_arn)
    except Exception:
        pass


def delete_kinesis_stream(stream_name):
    kinesis_client = boto3.client("kinesis")
    try:
        kinesis_client.delete_stream(StreamName=stream_name, EnforceConsumerDeletion=True)
    except Exception:
        pass


def generate_time_string():
    # Get the current time
    current_time = datetime.now()

    # Format the time string to include only two digits of seconds
    time_str = current_time.strftime("%Y-%m-%d_%H-%M-%S") + f"-{int(current_time.microsecond / 10000):00d}"

    return time_str


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
    for t in sorted(tags):
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
