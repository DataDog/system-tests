# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

""" AppSec validations """
import traceback
import json

from collections import Counter
from utils.interfaces._core import BaseValidation
from utils.interfaces._library._utils import get_spans_related_to_rid, get_rid_from_user_agent
from utils.tools import m
from utils.interfaces._library.appsec_data import rule_id_to_type


class _BaseAppSecValidation(BaseValidation):
    path_filters = ["/v0.4/traces", "/appsec/proxy/v1/input", "/appsec/proxy/api/v2/appsecevts"]

    def __init__(self, request):
        super().__init__(request=request)
        self.spans = []  # list of (trace_id, span_id): span related to rid
        self.appsec_events = []  # list of all appsec events

    def check(self, data):
        if data["path"] == "/v0.4/traces":
            content = data["request"]["content"]

            for i, span in enumerate(get_spans_related_to_rid(content, self.rid)):
                self.log_debug(f'Found span with rid={self.rid}: span_id={span["span_id"]}')
                self.spans.append(f'{span["trace_id"]}#{span["span_id"]}')

                if "_dd.appsec.json" in span.get("meta", {}):
                    self.appsec_events.append({"span": span, "i": i, "log_filename": data["log_filename"]})

        elif data["path"] in ("/appsec/proxy/v1/input", "/appsec/proxy/api/v2/appsecevts"):
            events = data["request"]["content"]["events"]
            for i, event in enumerate(events):
                if "trace" in event["context"] and "span" in event["context"]:
                    self.appsec_events.append({"legacy_event": event, "i": i, "log_filename": data["log_filename"]})

    def _get_related_spans(self):
        return [
            event
            for event in self.appsec_events
            if "span" in event
            or self._is_related_to_spans(event["legacy_event"])
            or self._is_my_rid(event["legacy_event"])
        ]

    def _is_related_to_spans(self, event):
        return f'{event["context"]["trace"]["id"]}#{event["context"]["span"]["id"]}' in self.spans

    def _is_my_rid(self, event):

        if self.rid is None:
            return True

        user_agents = (
            event.get("context", {}).get("http", {}).get("request", {}).get("headers", {}).get("user-agent", [])
        )

        # version 1 of appsec events schema
        if isinstance(user_agents, str):
            user_agents = [
                user_agents,
            ]

        for user_agent in user_agents:
            if get_rid_from_user_agent(user_agent) == self.rid:
                return True

        return False

    def final_check(self):
        spans = self._get_related_spans()

        if len(spans) == 0 and not self.is_success_on_expiry:
            self.set_failure(f"{self.message} not validated: Can't find any related event")

        for span in spans:
            if not self.closed:
                if "legacy_event" in span:
                    event = span["legacy_event"]
                    try:
                        if self.validate_legacy(event):
                            self.log_debug(f"{self} is validated (legacy) by {span['log_filename']}")
                            self.is_success_on_expiry = True
                    except Exception as e:
                        msg = traceback.format_exception_only(type(e), e)[0]
                        self.set_failure(
                            f"{m(self.message)} not validated on {span['log_filename']}, event #{span['i']}: {msg}"
                        )
                else:
                    span_data = span["span"]
                    appsec_data = json.loads(span_data["meta"]["_dd.appsec.json"])
                    try:
                        if self.validate(span_data, appsec_data):
                            self.log_debug(f"{self} is validated by {span['log_filename']}")
                            self.is_success_on_expiry = True
                    except Exception as e:
                        msg = traceback.format_exception_only(type(e), e)[0]
                        self.set_failure(
                            f"{m(self.message)} not validated on {span['log_filename']}, event #{span['i']}: {msg}"
                        )

    def validate_legacy(self, event):
        raise NotImplementedError

    def validate(self, span, appsec_data):
        raise NotImplementedError


class _AppSecValidation(_BaseAppSecValidation):
    """ will run an arbitrary check on appsec event. If a request is provided, only events
        related to this request will be checked.

        Validator function can :
        * returns true => validation will be validated at the end (but trace will continue to be checked)
        * returns False or None => nothing is done
        * raise an exception => validation will fail
    """

    def __init__(self, request, validator, legacy_validator, is_success_on_expiry=False):
        super().__init__(request=request)
        self.legacy_validator = legacy_validator
        self.validator = validator
        self.is_success_on_expiry = is_success_on_expiry

    def validate_legacy(self, event):
        if self.legacy_validator:
            return self.legacy_validator(event)
        else:
            raise NotImplementedError

    def validate(self, span, appsec_data):
        if self.validator:
            return self.validator(span, appsec_data)
        else:
            raise NotImplementedError


class _NoAppsecEvent(_BaseAppSecValidation):
    is_success_on_expiry = True

    def validate_legacy(self, event):
        self.set_failure(f"{m(self.message)} => request has been reported")

    def validate(self, span, appsec_data):
        self.set_failure(f"{m(self.message)} => request has been reported")


class _WafAttack(_BaseAppSecValidation):
    def __init__(self, request, rule=None, pattern=None, patterns=None, value=None, address=None, key_path=None):
        super().__init__(request=request)

        # rule can be a rule id, or a rule type
        if rule is None:
            self.rule_id = None
            self.rule_type = None

        elif isinstance(rule, str):
            self.rule_id = rule
            self.rule_type = None

        else:
            self.rule_id = None
            self.rule_type = rule.__name__

        self.pattern = pattern
        self.patterns = patterns
        self.value = value

        self.address = address
        self.key_path = key_path

    @staticmethod
    def _get_parameters(event):
        result = []

        for parameter in event.get("rule_match", {}).get("parameters", []):
            if "address" in parameter:  # 1.0.0
                address = parameter["address"]

            elif "name" in parameter:  # 0.1.0
                parts = parameter["name"].split(":", 1)
                address = parts[0]

            else:
                continue

            key_path = parameter.get("key_path", [])

            # depending on the lang/framework, the last element may be an array, or not
            # So, a tailing 0 is added to the key path
            if key_path and key_path[-1] == 0:
                key_path = key_path[:-1]

            result.append((address, key_path))

        return result

    def validate(self, span, appsec_data):
        for trigger in appsec_data.get("triggers", []):
            patterns = []
            values = []
            addresses = []
            full_addresses = []
            rule_id = trigger.get("rule", {}).get("id")
            rule_type = trigger.get("rule", {}).get("tags", {}).get("type")

            # Some agent does not report rule type ??
            if not rule_type:
                rule_type = rule_id_to_type.get(rule_id)

            for match in trigger.get("rule_matches", []):
                for parameter in match.get("parameters", []):
                    patterns += parameter["highlight"]
                    values.append(parameter["value"])
                    addresses.append(parameter["address"])
                    key_path = parameter["key_path"]
                    full_addresses.append((parameter["address"], key_path))
                    if isinstance(key_path, list) and len(key_path) != 0 and key_path[-1] == 0:
                        # on some framework, headers values can be arrays. In this case,
                        # key_path contains a tailing 0. Remove it and add it as possible use case.
                        key_path = key_path[:-1]
                        full_addresses.append((parameter["address"], key_path))

            if self.rule_id and self.rule_id != rule_id:
                self.log_info(f"{self.message} => saw {rule_id}, expecting {self.rule_id}")

            elif self.rule_type and self.rule_type != rule_type:
                self.log_info(f"{self.message} => saw rule type {rule_type}, expecting {self.rule_type}")

            elif self.pattern and self.pattern not in patterns:
                self.log_info(f"{self.message} => saw {patterns}, expecting {self.pattern}")

            elif self.patterns and Counter(self.patterns) != Counter(patterns):
                self.log_info(f"{self.message} => saw {patterns}, expecting {self.patterns}")

            elif self.value and self.value not in values:
                self.log_info(f"{self.message} => saw {values}, expecting {self.value}")

            elif self.address and self.key_path is None and self.address not in addresses:
                self.log_info(f"{self.message} => saw {addresses}, expecting {self.address}")

            elif self.address and self.key_path and (self.address, self.key_path) not in full_addresses:
                self.log_info(f"{self.message} => saw {full_addresses}, expecting {(self.address, self.key_path)}")

            else:
                self.set_status(True)

    def validate_legacy(self, event):
        event_version = event.get("event_version", "0.1.0")
        parameters = self._get_parameters(event)
        rule_match = event.get("rule_match", {})
        patterns = rule_match.get("highlight", rule_match.get("parameters", [{}])[0].get("highlight", []))
        rule_id = event.get("rule", {}).get("id")
        rule_type = event.get("rule", {}).get("tags", {}).get("type")
        addresses = [address for address, _ in parameters]

        # Some agent does not report rule type
        if not rule_type:
            rule_type = rule_id_to_type.get(rule_id)

        # be nice with very first AppSec data model, do not check key_path or rule_type
        key_path = self.key_path if event_version != "0.1.0" else None

        if self.rule_id and self.rule_id != rule_id:
            self.log_info(f"{self.message} => saw rule id {rule_id}, expecting {self.rule_id}")

        elif self.rule_type and self.rule_type != rule_type:
            self.log_info(f"{self.message} => saw rule type {rule_type}, expecting {self.rule_type}")

        elif self.pattern and self.pattern not in patterns:
            self.log_info(f"{self.message} => saw {patterns}, expecting {self.pattern}")

        elif self.address and key_path is None and self.address not in addresses:
            self.log_info(f"{self.message} => saw {addresses}, expecting {self.address}")

        elif self.address and key_path and (self.address, key_path) not in parameters:
            self.log_info(f"{self.message} => saw {parameters}, expecting {(self.address, key_path)}")

        else:
            self.set_status(True)


class _ReportedHeader(_BaseAppSecValidation):
    def __init__(self, request, header_name):
        super().__init__(request)
        self.header_name = header_name.lower()

    def validate_legacy(self, event):
        headers = [n.lower() for n in event["context"]["http"]["request"]["headers"].keys()]
        assert self.header_name in headers, f"header {self.header_name} not reported"

        return True

    def validate(self, span, appsec_data):
        headers = [n.lower() for n in span["meta"].keys() if n.startswith("http.request.headers.")]
        assert f"http.request.headers.{self.header_name}" in headers, f"header {self.header_name} not reported"

        return True
