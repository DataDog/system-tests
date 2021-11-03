# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

""" AppSec validations """
import traceback

from utils.interfaces._core import BaseValidation
from utils.interfaces._library._utils import get_spans_related_to_rid, get_rid_from_user_agent
from utils.tools import m


class _BaseAppSecValidation(BaseValidation):
    # TODO : remove this horrible span/trace identification once we have user agent in appsec event
    path_filters = ["/v0.4/traces", "/appsec/proxy/v1/input", "/appsec/proxy/api/v2/appsecevts"]

    def __init__(self, request):
        super().__init__(request=request)
        self.spans = []  # list of (trace_id, span_id) related to rid
        self.appSecEvents = []  # list of all appsec events

    def check(self, data):
        if data["path"] == "/v0.4/traces":
            content = data["request"]["content"]

            for span in get_spans_related_to_rid(content, self.rid):
                self.spans.append(f'{span["trace_id"]}#{span["span_id"]}')

        elif data["path"] in ("/appsec/proxy/v1/input", "/appsec/proxy/api/v2/appsecevts"):
            events = data["request"]["content"]["events"]
            for i, event in enumerate(events):
                if "trace" in event["context"] and "span" in event["context"]:
                    self.appSecEvents.append({"event": event, "i": i, "log_filename": data["log_filename"]})

    def _getRelatedAppSecEvents(self):
        return [
            event
            for event in self.appSecEvents
            if self._is_related_to_spans(event["event"]) or self._is_my_rid(event["event"])
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


class _AppSecValidation(_BaseAppSecValidation):
    """ will run an arbitrary check on appsec event. If a request is provided, only events
        related to this request will be checked.

        Validator function can :
        * returns true => validation will be validated at the end (but trace will continue to be checked)
        * returns False or None => nothing is done
        * raise an exception => validation will fail
    """

    def __init__(self, request, validator):
        super().__init__(request=request)
        self.validator = validator

    def final_check(self):
        events = self._getRelatedAppSecEvents()

        if len(events) == 0 and not self.is_success_on_expiry:
            self.set_failure(f"{self.message} not validated: Can't find any related event")

        for event_data in events:
            event = event_data["event"]
            try:
                if self.validator(event):
                    self.is_success_on_expiry = True
            except Exception as e:
                msg = traceback.format_exception_only(type(e), e)[0]
                self.set_failure(
                    f"{m(self.message)} not validated on {event_data['log_filename']}, event #{event_data['i']}: {msg}"
                )


class _NoAppsecEvent(_BaseAppSecValidation):
    def final_check(self):
        if len(self._getRelatedAppSecEvents()):
            self.set_failure(f"{self.message} => request has been reported")
            return

        self.set_status(True)


class _WafAttack(_BaseAppSecValidation):
    def __init__(self, request, rule_id=None, pattern=None, patterns=None, address=None, key_path=None):
        super().__init__(request=request)
        self.rule_id = rule_id
        self.pattern = pattern

        self.address = address
        self.key_path = key_path

        if patterns:
            raise NotImplementedError

    @staticmethod
    def _get_parameters(event):
        result = []

        for parameter in event.get("rule_match", {}).get("parameters", []):
            key_path = parameter.get("key_path")
            # don't care about event version, it's the schemas' job
            if "address" in parameter:
                address = parameter["address"]
            elif "name" in parameter:
                parts = parameter["name"].split(":", 1)
                address = parts[0]
                if key_path is None and len(parts) > 1:
                    key_path = parts[1].split(".")
            else:
                continue

            result.append((address, key_path or []))

        return result

    def final_check(self):
        events = self._getRelatedAppSecEvents()

        if len(events) == 0:
            self.set_failure(f"{self.message} => nothing has been reported")
            return

        # looking for at least one event that matches all conditions
        for event_data in events:
            event = event_data["event"]

            parameters = self._get_parameters(event)
            addresses = [address for address, _ in parameters]
            patterns = event.get("rule_match", {}).get("highlight", [])
            rule_id = event.get("rule", {}).get("id")

            if self.rule_id and self.rule_id != rule_id:
                self.log_info(f"{self.message} => saw {rule_id}")
            elif self.pattern and self.pattern not in patterns:
                self.log_info(f"{self.message} => saw {patterns}, expecting {self.pattern}")
            elif self.key_path is not None and (self.address, self.key_path) not in parameters:
                self.log_info(f"{self.message} => saw {parameters}, expecting ({self.address}, {self.key_path})")
            elif self.address and self.address not in addresses:
                self.log_info(f"{self.message} => saw {addresses}, expecting {self.address}")
            else:
                self.set_status(True)

        if not self.closed:
            # the only way to be closed here is a success
            # so if it's not closed, it's a failure
            self.set_status(False)
