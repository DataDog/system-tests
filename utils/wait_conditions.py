import time

from utils.tools import logger

# Time to sleep between iterations. We'd like this to be as slow as possible,
# but given that we ingest requests at intervals of 1 seconds, it does not make
# sense to go much lower than that.
_ITER_SLEEP_TIME = 0.5


# List of custom wait conditions to be added by tests.
_WAIT_CONDITIONS = []


def add(timeout, condition):
    """Sets up a wait condition that will be checked after setup."""
    _WAIT_CONDITIONS.append(WaitCondition(timeout=timeout, condition=condition))


class WaitCondition:
    def __init__(self, timeout, condition) -> None:
        self.timeout = timeout
        self.condition = condition


def wait_for_all(library_name, post_setup_timeout, tracer_sampling_rate, proxy_state):
    """Wait for all wait conditions."""
    start_time = time.time()
    deadline = start_time + post_setup_timeout

    if library_name == "php":
        # php-fpm and apache has multiple workers with separate trace flushes
        # so waiting for a single request is not enough, we'll wait for all known rids
        _wait_for_test_requests(deadline=deadline)

    watermark_n = _wait_for_request(deadline=deadline, tracer_sampling_rate=tracer_sampling_rate)
    _wait_for_request_in_agent(deadline=deadline)
    _wait_for_telemetry(skip_n=watermark_n, deadline=deadline)
    _wait_for_remote_config(deadline=deadline, proxy_state=proxy_state)
    _wait_for_custom_conditions(start_time=start_time, post_setup_timeout=post_setup_timeout)


def wait_for_all_otel(post_setup_timeout):
    deadline = time.time() + post_setup_timeout
    _wait_for_otel_request(deadline=deadline)


def _print_log(msg):
    logger.debug(msg)
    print(msg, file=logger.terminal)
    logger.terminal.flush()


def _wait_for_test_requests(deadline):
    """
    Wait to see all requests in weblog. This usually not needed, except
    when the weblog is multi-process and/or has multiple flush queues.
    """
    from utils import interfaces, weblog

    remaining_time = round(max(0, deadline - time.time()))
    _print_log(f"Waiting for all traces, remaining time: {remaining_time}s")

    all_rids = set(weblog.get_all_seen_rids())
    logger.debug(f"Waiting for traces with rids: {all_rids}")
    unseen_rids = all_rids
    while True:
        tracer_rids = set(interfaces.library.get_all_rids())
        unseen_rids -= tracer_rids
        if not unseen_rids:
            return
        if time.time() >= deadline:
            break

    _print_log(f"Waiting for all traces exceeded the deadline, unseen rids: {unseen_rids}")


def _wait_for_request(deadline, tracer_sampling_rate):
    """
    Do one request and wait until we receive its trace. We assume that by
    that time, other traces will also have been received. We return the
    number of messages received at that point to use it as a watermark for
    other message types.
    """
    from utils import interfaces
    from utils import weblog
    from utils.tools import get_rid_from_span, get_rid_from_request

    remaining_time = round(max(0, deadline - time.time()))
    _print_log(f"Waiting for watermark trace, remaining time: {remaining_time}s")

    watermark_rids = set()

    while True:
        if not watermark_rids or tracer_sampling_rate:
            # If we're using sampling rate, our trace might be discarded, so
            # in that case we make one request per interval.
            watermark_request = weblog.get("/", post_setup=True)
            watermark_rid = get_rid_from_request(watermark_request)
            watermark_rids.add(watermark_rid)

        messages = list(interfaces.library.get_data())
        for n, msg in enumerate(messages):
            if msg["path"] not in ("/v0.4/traces", "/v0.5/traces"):
                continue
            traces = msg["request"]["content"]
            for trace in traces:
                for span in trace:
                    if get_rid_from_span(span) in watermark_rids:
                        return n
        if time.time() >= deadline:
            break
        time.sleep(_ITER_SLEEP_TIME)

    _print_log("Waiting for watermark trace exceeded the deadline")


def _wait_for_request_in_agent(deadline):
    """
    Wait until the last request seen in the library is also seen in the agent.
    """
    from utils import interfaces
    from utils.tools import get_rid_from_span

    remaining_time = round(max(0, deadline - time.time()))
    _print_log(f"Waiting for watermark trace in agent, remaining time: {remaining_time}s")

    messages = list(interfaces.library.get_data(path_filters=["/v0.4/traces", "/v0.5/traces"]))
    if not messages:
        return

    last_message = messages[-1]
    rid = None
    for trace in last_message["request"]["content"]:
        for span in trace:
            rid = get_rid_from_span(span)
            if rid:
                break
    if not rid:
        logger.warning(f"Last library trace has no rid: {last_message['log_filename']}")
        return
    while True:
        if list(interfaces.agent.get_spans(request=rid)):
            return
        if time.time() >= deadline:
            break
        time.sleep(_ITER_SLEEP_TIME)

    _print_log("Waiting for trace in agent exceeded the deadline")


def _wait_for_telemetry(skip_n, deadline):
    """
    Wait until we receive two heartbeats after N messages. N should be the
    number of messages received before the watermark request. This should be
    enough to receive any relevant event triggered by previous requests.
    """
    from utils import interfaces

    remaining_time = round(max(0, deadline - time.time()))

    # If we have not received at least one telemetry message by now (e.g. app-started), then telemetry
    # is either disabled, not implemented, or not working at all. So we can stop waiting already.
    # We test this only for app-heartbeat and app-started, rather than any telemetry message. This is a
    # workaround to Ruby tracer (see # https://github.com/DataDog/system-tests/pull/1315), which is sending
    # some telemetry messages, but not heartbeats.
    messages = list(interfaces.library.get_data(path_filters="/telemetry/proxy/api/v2/apmtelemetry"))
    messages = [m for m in messages if m["request"]["content"].get("request_type") in ("app-heartbeat", "app-started")]
    if not messages:
        logger.debug("Did not receive any telemetry message")
        return

    _print_log(f"Waiting for telemetry heartbeats, remaining time: {remaining_time}s")

    while True:
        messages = list(interfaces.library.get_data())
        messages = messages[skip_n:]
        heartbeats = 0
        for msg in messages:
            if msg["path"] != "/telemetry/proxy/api/v2/apmtelemetry":
                continue
            if msg["request"]["content"]["request_type"] == "app-heartbeat":
                heartbeats += 1
        if heartbeats >= 2:
            return
        if time.time() >= deadline:
            break
        time.sleep(_ITER_SLEEP_TIME)

    _print_log("Waiting for telemetry exceeded the deadline")


def _wait_for_remote_config(deadline, proxy_state):
    """
    If we are using mocked remote config, wait until we received all the required responses plus 2.
    """
    if not proxy_state:
        return
    rc_scenario = proxy_state.get("mock_remote_config_backend")
    if not rc_scenario:
        return

    from utils.proxy.rc_mock import MOCKED_RESPONSES

    mocked_responses = MOCKED_RESPONSES.get(rc_scenario)
    if not mocked_responses:
        return

    from utils import interfaces

    remaining_time = round(max(0, deadline - time.time()))
    _print_log(f"Waiting for remote config, remaining time: {remaining_time}s")

    n_requests = len(mocked_responses) + 2
    while True:
        actual_n_requests = len(list(interfaces.library.get_data(path_filters=r"/v\d+.\d+/config")))
        if actual_n_requests >= n_requests:
            return
        if time.time() >= deadline:
            break
        time.sleep(_ITER_SLEEP_TIME)

    _print_log("Waiting for remote config exceeded the deadline")


def _wait_for_otel_request(deadline):
    from utils import interfaces, weblog

    remaining_time = round(max(0, deadline - time.time()))
    _print_log(f"Waiting for watermark otel trace, remaining time: {remaining_time}s")

    request = weblog.get("/basic/trace", post_setup=True)
    while True:
        otel_trace_ids = list(interfaces.open_telemetry.get_otel_trace_id(request=request))
        if otel_trace_ids:
            return
        if time.time() >= deadline:
            break
        time.sleep(_ITER_SLEEP_TIME)

    _print_log("Waiting for watermark otel trace exceeded the deadline")


def _wait_for_custom_conditions(start_time, post_setup_timeout):
    global _WAIT_CONDITIONS

    if not _WAIT_CONDITIONS:
        logger.debug("No wait conditions")
        return

    deadline = start_time + post_setup_timeout
    elapsed_time = time.time() - start_time
    default_timeout = max(0, deadline - time.time())

    timeout = max(c.timeout for c in _WAIT_CONDITIONS)
    timeout = max(timeout, default_timeout)
    timeout = max(0, timeout - elapsed_time)

    deadline = time.time() + timeout

    _print_log(f"Waiting for {len(_WAIT_CONDITIONS)} conditions, remaining time: {round(timeout)}s")
    while True:
        _WAIT_CONDITIONS = [c for c in _WAIT_CONDITIONS if not c.condition()]
        if not _WAIT_CONDITIONS:
            return
        if time.time() >= deadline:
            break
        time.sleep(_ITER_SLEEP_TIME)
    _print_log(f"Waiting for custom conditions exceeded deadline ({len(_WAIT_CONDITIONS)} not met)")
