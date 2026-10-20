from collections.abc import Callable

from utils import interfaces, logger, remote_config
from utils._weblog import HttpResponse


def _has_schemas(request: HttpResponse, addresses: tuple[str, ...]) -> bool:
    """True if a root span of the request carries every _dd.appsec.s.<address> tag. Never asserts."""
    for _, span in interfaces.library.get_root_spans(request=request):
        meta = span.get("meta", {})
        if all(f"_dd.appsec.s.{address}" in meta for address in addresses):
            return True
    return False


def _has_root_span(request: HttpResponse) -> bool:
    return any(True for _ in interfaces.library.get_root_spans(request=request))


class _TraceWait:
    # set after the first timeout: if traces stop arriving, later setups must not wait again,
    # so the whole session pays at most one timeout
    disabled = False


def _wait_for_root_span(request: HttpResponse, timeout: int) -> bool:
    if _TraceWait.disabled:
        return False
    trace_paths = interfaces.library.trace_paths
    # wait_for evaluates every existing payload before waiting: skip the ones already checked here,
    # so each wait costs one scan per new trace payload instead of one per existing payload
    checked = {data["log_filename"] for data in interfaces.library.get_data(path_filters=trace_paths)}
    if _has_root_span(request):
        return True

    def trace_arrived(data: dict) -> bool:
        return data["path"] in trace_paths and data["log_filename"] not in checked and _has_root_span(request)

    if interfaces.library.wait_for(trace_arrived, timeout=timeout):
        return True
    logger.warning("No trace received while waiting for a schema; disabling further waits")
    _TraceWait.disabled = True
    return False


def send_until_schema(
    send: Callable[[], HttpResponse], *addresses: str, attempts: int = 3, timeout: int = 5
) -> list[HttpResponse]:
    """Send a request until its root span carries a schema for every address (use in setup_*).

    API Security sampling is best-effort: a library may skip a request under load. Back-to-back
    retries tend to be skipped together (same trace flush window), so the decision to retry needs
    the previous request's trace: this is an event-driven wait, not a sleep, and it ends as soon as
    the trace arrives. After one timeout no further waits happen in the session.
    Retries only help in scenarios with DD_API_SECURITY_SAMPLE_DELAY=0, otherwise the sampler
    deduplicates the endpoint. Stops early if the weblog fails or no trace shows up. Never asserts
    or raises: a setup failure aborts the scenario.
    """
    responses: list[HttpResponse] = []
    for attempt in range(1, attempts + 1):
        response = send()
        responses.append(response)

        if response.status_code is None or response.status_code >= 400:
            break

        if not _wait_for_root_span(response, timeout):
            break

        if _has_schemas(response, addresses):
            break

        if attempt < attempts:
            logger.warning(f"No schema for {addresses} on attempt {attempt}/{attempts}, retrying")

    return responses


def get_sampled_response(requests: list[HttpResponse], *addresses: str) -> HttpResponse:
    """Return the first response whose root span carries every address schema (use in test_*)."""
    for request in requests:
        if _has_schemas(request, addresses):
            return request
    attempts = [
        f"rid={r.get_rid()} status={r.status_code} trace={'yes' if _has_root_span(r) else 'no'}" for r in requests
    ]
    raise AssertionError(f"no schema in {len(requests)} attempts for addresses {addresses}: {attempts}")


class BaseAppsecApiSecurityRcTest:
    states = None

    def setup_scenario(self) -> None:
        if BaseAppsecApiSecurityRcTest.states is None:
            rc_state = remote_config.tracer_rc_state
            rc_state.set_config(
                "datadog/2/ASM/ASM-base/config",
                {
                    "processor_overrides": [
                        {
                            "target": [{"id": "extract-content"}],
                            "scanners": {
                                "include": [{"id": "test-scanner-001"}, {"id": "test-scanner-custom-001"}],
                                "exclude": [],
                            },
                        }
                    ],
                    "scanners": [
                        {
                            "id": "test-scanner-custom-001",
                            "name": "Custom scanner",
                            "key": {
                                "operator": "match_regex",
                                "parameters": {
                                    "regex": "\\btestcard\\b",
                                    "options": {"case_sensitive": False, "min_length": 2},
                                },
                            },
                            "value": {
                                "operator": "match_regex",
                                "parameters": {
                                    "regex": "\\b1234567890\\b",
                                    "options": {"case_sensitive": False, "min_length": 5},
                                },
                            },
                            "tags": {"type": "card", "category": "testcategory"},
                        }
                    ],
                },
            )
            rc_state.set_config(
                "datadog/2/ASM_DD/ASM_DD-base/config",
                {
                    "version": "2.2",
                    "metadata": {"rules_version": "1.10.0"},
                    "rules": [
                        {
                            "id": "test-001",
                            "name": "Test 001 rule",
                            "tags": {"type": "commercial_scanner", "category": "attack_attemp"},
                            "conditions": [
                                {
                                    "parameters": {
                                        "inputs": [
                                            {"address": "server.request.query"},
                                            {"address": "server.request.uri.raw"},
                                            {"address": "server.request.body"},
                                        ],
                                        "regex": "testattack",
                                        "options": {"case_sensitive": False},
                                    },
                                    "operator": "match_regex",
                                }
                            ],
                        }
                    ],
                    "processors": [
                        {
                            "id": "extract-content",
                            "generator": "extract_schema",
                            "conditions": [
                                {
                                    "operator": "equals",
                                    "parameters": {
                                        "inputs": [
                                            {"address": "waf.context.processor", "key_path": ["extract-schema"]}
                                        ],
                                        "type": "boolean",
                                        "value": True,
                                    },
                                }
                            ],
                            "parameters": {
                                "mappings": [
                                    {
                                        "inputs": [{"address": "server.request.query"}],
                                        "output": "_dd.appsec.s.req.querytest",
                                    },
                                    {
                                        "inputs": [{"address": "server.request.body"}],
                                        "output": "_dd.appsec.s.req.bodytest",
                                    },
                                ],
                                "scanners": [{"tags": {"category": "pii"}}],
                            },
                            "evaluate": True,
                            "output": True,
                        }
                    ],
                    "scanners": [
                        {
                            "id": "test-scanner-001",
                            "name": "Standard E-mail Address",
                            "key": {
                                "operator": "match_regex",
                                "parameters": {
                                    "regex": "\\b(?:(?:e[-\\s]?)?mail|address|sender|\\bto\\b|from|recipient)\\b",
                                    "options": {"case_sensitive": False, "min_length": 2},
                                },
                            },
                            "value": {
                                "operator": "match_regex",
                                "parameters": {
                                    "regex": "\\b[\\w!#$%&'*+/=?`{|}~^-]+(?:\\.[\\w!#$%&'*+/=?`{|}~^-]+)*"
                                    "(%40|@)(?:[a-zA-Z0-9-]+\\.)+[a-zA-Z]{2,6}\\b",
                                    "options": {"case_sensitive": False, "min_length": 5},
                                },
                            },
                            "tags": {"type": "email", "category": "pii"},
                        }
                    ],
                },
            )
            rc_state.set_config(
                "datadog/2/ASM_FEATURES/ASM_FEATURES-base/config",
                {"asm": {"enabled": True}},
            )

            BaseAppsecApiSecurityRcTest.states = rc_state.apply()
