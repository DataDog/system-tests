# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import copy
import json
import threading

from utils.tools import logger, get_rid_from_user_agent, get_rid_from_span, get_rid_from_request
from utils.dd_constants import RemoteConfigApplyState
from utils.interfaces._core import ProxyBasedInterfaceValidator
from utils.interfaces._library._utils import get_trace_request_path
from utils.interfaces._library.appsec import _WafAttack, _ReportedHeader
from utils.interfaces._library.miscs import _SpanTagValidator
from utils.interfaces._library.telemetry import (
    _SeqIdLatencyValidation,
    _NoSkippedSeqId,
)

from utils.interfaces._misc_validators import HeadersPresenceValidator


class LibraryInterfaceValidator(ProxyBasedInterfaceValidator):
    """Validate library/agent interface"""

    def __init__(self, name):
        super().__init__(name)
        self.ready = threading.Event()

    def ingest_file(self, src_path):
        self.ready.set()
        return super().ingest_file(src_path)

    ################################################################
    def wait_for_remote_config_request(self, timeout=30):
        """ Used in setup functions, wait for a request oremote config endpoint with a non-empty client_config """

        def wait_function(data):
            if data["path"] == "/v0.7/config":
                if "client_configs" in data.get("response", {}).get("content", {}):
                    return True

            return False

        self.wait_for(wait_function, timeout)

    ############################################################
    def get_traces(self, request=None):
        paths = ["/v0.4/traces", "/v0.5/traces"]

        rid = get_rid_from_request(request)

        if rid:
            logger.debug(f"Try to find traces related to request {rid}")

        for data in self.get_data(path_filters=paths):
            traces = data["request"]["content"]
            for trace in traces:
                if rid is None:
                    yield data, trace
                else:
                    for span in trace:
                        if rid == get_rid_from_span(span):
                            yield data, trace
                            break

    def get_spans(self, request=None, full_trace=False):
        """Iterate over all spans reported by the tracer to the agent.

        If request is not None and full_trace is False, only span trigered by that request will be
        returned.
        If request is not None and full_trace is True, all spans from a trace triggered by that
        request will be returned.
        """
        rid = get_rid_from_request(request)

        if rid:
            logger.debug(f"Try to find spans related to request {rid}")

        for data, trace in self.get_traces(request=request):
            for span in trace:
                if rid is None or full_trace:
                    yield data, trace, span
                elif rid == get_rid_from_span(span):
                    logger.debug(f"A span is found in {data['log_filename']}")
                    yield data, trace, span

    def get_root_spans(self, request=None):
        for data, _, span in self.get_spans(request=request):
            if span.get("parent_id") in (0, None):
                yield data, span

    def get_appsec_events(self, request=None, full_trace=False):
        for data, trace, span in self.get_spans(request=request, full_trace=full_trace):
            if "appsec" in span.get("meta_struct", {}):

                if request:  # do not spam log if all data are sent to the validator
                    logger.debug(f"Try to find relevant appsec data in {data['log_filename']}; span #{span['span_id']}")

                appsec_data = span["meta_struct"]["appsec"]
                yield data, trace, span, appsec_data
            elif "_dd.appsec.json" in span.get("meta", {}):

                if request:  # do not spam log if all data are sent to the validator
                    logger.debug(f"Try to find relevant appsec data in {data['log_filename']}; span #{span['span_id']}")

                appsec_data = span["meta"]["_dd.appsec.json"]
                yield data, trace, span, appsec_data

    def get_legacy_appsec_events(self, request=None):
        paths_with_appsec_events = ["/appsec/proxy/v1/input", "/appsec/proxy/api/v2/appsecevts"]

        rid = get_rid_from_request(request)

        for data in self.get_data(path_filters=paths_with_appsec_events):
            events = data["request"]["content"]["events"]
            for event in events:
                if "trace" in event["context"] and "span" in event["context"]:

                    if rid is None:
                        yield data, event
                    else:
                        user_agents = (
                            event.get("context", {})
                            .get("http", {})
                            .get("request", {})
                            .get("headers", {})
                            .get("user-agent", [])
                        )

                        # version 1 of appsec events schema
                        if isinstance(user_agents, str):
                            user_agents = [
                                user_agents,
                            ]

                        for user_agent in user_agents:
                            if get_rid_from_user_agent(user_agent) == rid:

                                if request:  # do not spam log if all data are sent to the validator
                                    logger.debug(f"Try to find relevant appsec data in {data['log_filename']}")

                                yield data, event
                                break

    def get_telemetry_data(self, flatten_message_batches=True):
        all_data = self.get_data(path_filters="/telemetry/proxy/api/v2/apmtelemetry")
        if not flatten_message_batches:
            yield from all_data
        else:
            for data in all_data:
                if data["request"]["content"].get("request_type") == "message-batch":
                    for batch_payload in data["request"]["content"]["payload"]:
                        # create a fresh copy of the request for each payload in the
                        # message batch, as though they were all sent independently
                        copied = copy.deepcopy(data)
                        copied["request"]["content"]["request_type"] = batch_payload.get("request_type")
                        copied["request"]["content"]["payload"] = batch_payload.get("payload")
                        yield copied
                else:
                    yield data

    def get_telemetry_metric_series(self, namespace, metric):
        relevantSeries = []
        for data in self.get_telemetry_data():
            content = data["request"]["content"]
            if content.get("request_type") != "generate-metrics":
                continue
            fallback_namespace = content["payload"].get("namespace")

            for series in content["payload"]["series"]:
                computed_namespace = series.get("namespace", fallback_namespace)

                # Inject here the computed namespace considering the fallback. This simplifies later assertions.
                series["_computed_namespace"] = computed_namespace
                if computed_namespace == namespace and series["metric"] == metric:
                    relevantSeries.append(series)
        return relevantSeries

    ############################################################

    def validate_telemetry(self, validator, success_by_default=False):
        def validator_skip_onboarding_event(data):
            if data["request"]["content"].get("request_type") == "apm-onboarding-event":
                return None
            return validator(data)

        self.validate(
            validator_skip_onboarding_event,
            path_filters="/telemetry/proxy/api/v2/apmtelemetry",
            success_by_default=success_by_default,
        )

    def validate_appsec(
        self, request=None, validator=None, success_by_default=False, legacy_validator=None, full_trace=False
    ):

        if validator:
            for _, _, span, appsec_data in self.get_appsec_events(request=request, full_trace=full_trace):
                if validator(span, appsec_data):
                    return

        if legacy_validator:
            for _, event in self.get_legacy_appsec_events(request=request):
                if validator(event):
                    return

        if not success_by_default:
            raise ValueError("No appsec event has been found")

    ######################################################

    def assert_iast_implemented(self):
        for _, span in self.get_root_spans():
            if "_dd.iast.enabled" in span.get("metrics", {}):
                return

            if "_dd.iast.enabled" in span.get("meta", {}):
                return

        raise ValueError("_dd.iast.enabled has not been found in any metrics")

    def assert_headers_presence(self, path_filter, request_headers=(), response_headers=(), check_condition=None):
        validator = HeadersPresenceValidator(request_headers, response_headers, check_condition)
        self.validate(validator, path_filters=path_filter, success_by_default=True)

    def assert_receive_request_root_trace(self):  # TODO : move this in test class
        """Asserts that a trace for a request has been sent to the agent"""

        for _, span in self.get_root_spans():
            if span.get("type") == "web":
                return

        raise ValueError("Nothing has been reported. No request root span with has been found")

    def assert_all_traces_requests_forwarded(self, paths):
        # TODO : move this in test class
        paths = set(paths)

        for _, span in self.get_root_spans():
            path = get_trace_request_path(span)

            if path is None or path not in paths:
                continue

            paths.remove(path)

        if len(paths) != 0:
            for path in paths:
                logger.error(f"A path has not been transmitted: {path}")

            raise ValueError("Some path has not been transmitted")

    def assert_trace_id_uniqueness(self):
        trace_ids = {}

        for data, trace in self.get_traces():
            spans = [span for span in trace if span.get("parent_id") in ("0", 0, None)]

            if len(spans):
                log_filename = data["log_filename"]
                span = spans[0]
                assert "trace_id" in span, f"'trace_id' is missing in {log_filename}"
                trace_id = span["trace_id"]

                if trace_id in trace_ids:
                    raise ValueError(
                        f"Found duplicated trace id {trace_id} in {log_filename} and {trace_ids[trace_id]}"
                    )

                trace_ids[trace_id] = log_filename

    def assert_no_appsec_event(self, request):
        for data, _, _, appsec_data in self.get_appsec_events(request=request):
            logger.error(json.dumps(appsec_data, indent=2))
            raise ValueError(f"An appsec event has been reported in {data['log_filename']}")

        for data, event in self.get_legacy_appsec_events(request=request):
            logger.error(json.dumps(event, indent=2))
            raise ValueError(f"An appsec event has been reported in {data['log_filename']}")

    def assert_waf_attack(
        self,
        request,
        rule=None,
        pattern=None,
        value=None,
        address=None,
        patterns=None,
        key_path=None,
        full_trace=False,
        span_validator=None,
    ):
        """Asserts the WAF detected an attack on the provided request.

        If full_trace is True, all events found on the trace(s) created by the request will be looked into, otherwise
        only those with an identified User-Agent matching that of the request will be considered. It is advised to set
        full_trace to True when the events aren't expected to originate from the HTTP layer (e.g: GraphQL tests).
        """

        validator = _WafAttack(
            rule=rule,
            pattern=pattern,
            value=value,
            address=address,
            patterns=patterns,
            key_path=key_path,
            span_validator=span_validator,
        )

        self.validate_appsec(
            request,
            validator=validator.validate,
            legacy_validator=validator.validate_legacy,
            success_by_default=False,
            full_trace=full_trace,
        )

    def add_appsec_reported_header(self, request, header_name):
        validator = _ReportedHeader(header_name)

        self.validate_appsec(
            request, validator=validator.validate, legacy_validator=validator.validate_legacy, success_by_default=False,
        )

    def add_traces_validation(self, validator, success_by_default=False):
        self.validate(validator=validator, success_by_default=success_by_default, path_filters=r"/v0\.[1-9]+/traces")

    def validate_traces(self, request=None, validator=None, success_by_default=False):
        for _, trace in self.get_traces(request=request):
            if validator(trace):
                return

        if not success_by_default:
            raise ValueError("No span validates this test")

    def validate_spans(self, request=None, validator=None, success_by_default=False):
        for _, _, span in self.get_spans(request=request):
            try:
                if validator(span):
                    return
            except:
                logger.error(f"This span is failing validation: {json.dumps(span, indent=2)}")
                raise

        if not success_by_default:
            raise ValueError("No span validates this test")

    def add_span_tag_validation(self, request=None, tags=None, value_as_regular_expression=False):
        validator = _SpanTagValidator(tags=tags, value_as_regular_expression=value_as_regular_expression)
        success = False
        for _, _, span in self.get_spans(request=request):
            success = success or validator(span)

        if not success:
            raise ValueError("Can't find anything to validate this test")

    def assert_seq_ids_are_roughly_sequential(self):
        validator = _SeqIdLatencyValidation()
        self.validate_telemetry(validator, success_by_default=True)

    def assert_no_skipped_seq_ids(self):
        validator = _NoSkippedSeqId()
        self.validate_telemetry(validator, success_by_default=True)

        validator.final_check()

    def get_profiling_data(self):
        yield from self.get_data(path_filters="/profiling/v1/input")

    def assert_trace_exists(self, request, span_type=None):
        for _, _, span in self.get_spans(request=request):
            if span_type is None or span.get("type") == span_type:
                return

        raise ValueError(f"No trace has been found for request {get_rid_from_request(request)}")

    def validate_remote_configuration(self, validator, success_by_default=False):
        self.validate(validator, success_by_default=success_by_default, path_filters=r"/v\d+.\d+/config")

    def assert_rc_apply_state(self, product: str, config_id: str, apply_state: RemoteConfigApplyState) -> None:
        """
            Check that all config_id/product have the expected apply_state returned by the library
            Very simplified version of the assert_rc_targets_version_states

        """
        found = False
        for data in self.get_data(path_filters="/v0.7/config"):
            config_states = data["request"]["content"]["client"]["state"].get("config_states", [])

            for config_state in config_states:
                if config_state["id"] == config_id and config_state["product"] == product:
                    logger.debug(f"In {data['log_filename']}: found {config_state}")
                    assert config_state["apply_state"] == apply_state.value
                    found = True

        assert found, f"Nothing has been found for {config_id}/{product}"

    def assert_rc_targets_version_states(self, targets_version: int, config_states: list) -> None:
        """
            check that for a given targets_version, the config states is the one expected
            EXPERIMENTAL (is it the good testing API ?)
        """
        found = False
        for data in self.get_data(path_filters="/v0.7/config"):
            state = data["request"]["content"]["client"]["state"]

            if state["targets_version"] != targets_version:
                continue

            logger.debug(f"In {data['log_filename']}: found targets_version {targets_version}")

            assert not state.get("has_error", False), f"State error found: {state.get('error')}"

            observed_config_states = state.get("config_states", [])
            logger.debug(f"Observed: {observed_config_states}")
            logger.debug(f"expected: {config_states}")

            assert config_states == observed_config_states
            found = True

        assert found, f"Nothing has been found for targets_version {targets_version}"

    def assert_rasp_attack(self, request, rule: str, parameters=None):
        def validator(_, appsec_data):
            assert "triggers" in appsec_data, "'triggers' not found in '_dd.appsec.json'"

            triggers = appsec_data["triggers"]
            assert len(triggers) == 1, "multiple appsec events found, only one expected"

            trigger = triggers[0]
            obtained_rule_id = trigger["rule"]["id"]
            assert obtained_rule_id == rule, f"incorrect rule id, expected {rule}"

            if parameters is not None:
                rule_matches = trigger["rule_matches"]
                assert len(rule_matches) == 1, "multiple rule matches found, only one expected"

                rule_match_params = rule_matches[0]["parameters"]
                assert len(rule_match_params) == 1, "multiple parameters found, only one expected"

                obtained_parameters = rule_match_params[0]
                for name, fields in parameters.items():
                    address = fields["address"]
                    value = None
                    if "value" in fields:
                        value = fields["value"]

                    key_path = None
                    if "key_path" in fields:
                        key_path = fields["key_path"]

                    assert name in obtained_parameters, f"parameter '{name}' not in rule match"

                    obtained_param = obtained_parameters[name]

                    assert obtained_param["address"] == address, f"incorrect address for '{name}', expected '{address}'"

                    if value is not None:
                        assert obtained_param["value"] == value, f"incorrect value for '{name}', expected '{value}'"

                    if key_path is not None:
                        assert (
                            obtained_param["key_path"] == key_path
                        ), f"incorrect key_path for '{name}', expected '{key_path}'"

            return True

        self.validate_appsec(request, validator, success_by_default=False)
