from collections.abc import Generator, Sequence
import hashlib
import struct

from utils import weblog, interfaces, logger, HttpResponse


class BaseDbIntegrationsTestClass:
    """define a setup function that perform a request to the weblog for each operation: select, update..."""

    db_service: str
    requests: dict[str, dict[str, HttpResponse]] = {}

    def _setup(self):
        """Make request to weblog for each operation: select, update...
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
            # Node.js opentelemetry-instrumentation-mssql is too old and select query is not tracer allways
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
    setup_error_type_and_stack = _setup
    setup_error_message = _setup
    setup_obfuscate_query = _setup
    setup_sql_query = _setup
    setup_sql_success = _setup
    setup_not_obfuscate_query = _setup

    def get_requests(
        self, excluded_operations: Sequence[str] = (), operations: Sequence[str] | None = None
    ) -> Generator[tuple[str, HttpResponse], None, None]:
        for db_operation, request in self.requests[self.db_service].items():
            if operations is not None and db_operation not in operations:
                continue

            if db_operation not in excluded_operations:
                yield db_operation, request

    @staticmethod
    def get_span_from_tracer(weblog_request: HttpResponse) -> dict:
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
    def get_span_from_agent(weblog_request: HttpResponse) -> dict:
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


def fnv(data: bytes, hval_init: int, fnv_prime: int, fnv_size: int) -> int:
    """Core FNV hash algorithm used in FNV0 and FNV1."""
    hval = hval_init
    for byte in data:
        hval = (hval * fnv_prime) % fnv_size
        hval = hval ^ byte
    return hval


FNV_64_PRIME = 0x100000001B3
FNV1_64_INIT = 0xCBF29CE484222325


def fnv1_64(data: bytes) -> int:
    """Returns the 64 bit FNV-1 hash value for the given data."""
    return fnv(data, FNV1_64_INIT, FNV_64_PRIME, 2**64)


def compute_dsm_hash(parent_hash: int, tags: tuple[str, str, str]) -> int:
    def get_bytes(s: str) -> bytes:
        return bytes(s, encoding="utf-8")

    b = get_bytes("weblog") + get_bytes("system-tests")
    for t in tags:
        b += get_bytes(t)
    node_hash = fnv1_64(b)
    return fnv1_64(struct.pack("<Q", node_hash) + struct.pack("<Q", parent_hash))


def sha_hash(checkpoint_string: str | bytes) -> bytes:
    if isinstance(checkpoint_string, str):
        checkpoint_string = checkpoint_string.encode("utf-8")
    return hashlib.md5(checkpoint_string).digest()[:8]


# def compute_dsm_hash_nodejs(parent_hash, edge_tags) -> int:
#     current_hash = sha_hash(f"{'weblog'}{'system-tests'}{''.join(edge_tags)}")
#     parent_hash_buf = struct.pack(">Q", parent_hash)
#     buf = current_hash + parent_hash_buf

#     val = sha_hash(buf)
#     return int.from_bytes(val, "big")
