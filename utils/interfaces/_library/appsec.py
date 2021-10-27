# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

""" AppSec validations """
import traceback

from utils.interfaces._core import BaseValidation
from utils.interfaces._library._utils import get_spans_related_to_rid, get_rid_from_user_agent


class _BaseAppSecValidation(BaseValidation):
    # TODO : remove this horrible span/trace identification once we have user agent in appsec event
    path_filters = ["/v0.4/traces", "/appsec/proxy/v1/input", "/appsec/proxy/api/v2/appsecevts"]

    def __init__(self, request):
        super().__init__(request=request)
        self.spans = []  # list of (trace_id, span_id) related to rid
        self.appSecEvents = []  # list of (trace_id, span_id) where an appsec event is seen

    def check(self, data):
        if data["path"] == "/v0.4/traces":
            content = data["request"]["content"]

            for span in get_spans_related_to_rid(content, self.rid):
                self.spans.append(f'{span["trace_id"]}#{span["span_id"]}')

        elif data["path"] in ("/appsec/proxy/v1/input", "/appsec/proxy/api/v2/appsecevts"):
            events = data["request"]["content"]["events"]
            events = [event for event in events if "trace" in event["context"] and "span" in event["context"]]

            self.appSecEvents += events

    def _getRelatedAppSecEvents(self):

        return [event for event in self.appSecEvents if self._is_related_to_spans(event) or self._is_my_rid(event)]

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
            self.set_failure(f"{self.message} not validated: Can't fin any related event")

        for event in events:
            try:
                if self.validator(event):
                    self.is_success_on_expiry = True
            except Exception as e:
                msg = traceback.format_exception_only(type(e), e)[0]
                self.set_failure(f"{self.message} not validated: {msg}\n")


class _NoAppsecEvent(_BaseAppSecValidation):
    def final_check(self):
        if len(self._getRelatedAppSecEvents()):
            self.set_failure(f"{self.message} => request has been reported")
            return

        self.set_status(True)


class _WafAttack(_BaseAppSecValidation):
    def __init__(self, request, rule_id=None, pattern=None, patterns=None, address=None):
        super().__init__(request=request)
        self.rule_id = rule_id
        self.pattern = pattern

        self.address = address

        if patterns:
            raise NotImplementedError

    @staticmethod
    def _get_addresses(event):
        result = []

        for parameter in event.get("rule_match", {}).get("parameters", []):
            # don't care about event version, it's the schemas' job
            if "name" in parameter:
                address = parameter["name"]
            elif "address" in parameter:
                address = parameter["address"]
            else:
                continue

            if "key_path" in parameter:
                for key_path in parameter["key_path"]:
                    result.append(f"{address}:{key_path}")
            else:
                result.append(address)

        return result

    def final_check(self):
        events = self._getRelatedAppSecEvents()

        if len(events) == 0:
            self.set_failure(f"{self.message} => nothing has been reported")
            return

        # looking for at least one event that matches all conditions
        for event in events:

            addresses = self._get_addresses(event)
            patterns = event.get("rule_match", {}).get("highlight", [])
            event_version = event.get("event_version", "0.1.0")
            rule_id = event.get("rule", {}).get("id")

            if self.address and event_version == "0.1.0" and ":" in self.address and self.address not in addresses:
                # be nice with very first AppSec data model, do not check key_path if needed
                address, _ = self.address.split(":")
            else:
                address = self.address

            if self.rule_id and self.rule_id != rule_id:
                self.log_info(f"{self.message} => saw {rule_id}")
            elif self.pattern and self.pattern not in patterns:
                self.log_info(f"{self.message} => saw {patterns}, expecting {self.pattern}")
            elif address and address not in addresses:
                self.log_info(f"{self.message} => saw {addresses}, expecting {address}")
            else:
                self.set_status(True)

        if not self.closed:
            # the only way to be closed here is a success
            # so if it's not closed, it's a failure
            self.set_status(False)
