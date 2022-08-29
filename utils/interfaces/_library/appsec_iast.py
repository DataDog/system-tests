# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

""" AppSec IAST validations """
import traceback
import json
from collections import namedtuple
from collections import Counter
from utils.interfaces._core import BaseValidation
from utils.interfaces._library._utils import get_spans_related_to_rid, get_rid_from_user_agent
from utils.tools import m


class _BaseAppSecIastValidation(BaseValidation):
    """Base class for all IAST validations"""

    path_filters = ["/v0.4/traces"]

    def __init__(self, request):
        super().__init__(request=request)
        self.spans = []  # list of (trace_id, span_id): span related to rid
        self.appsec_iast_events = []  # list of all appsec iast events

    def check(self, data):
        if data["path"] == "/v0.4/traces":
            content = data["request"]["content"]

            for i, span in enumerate(get_spans_related_to_rid(content, self.rid)):
                self.log_debug(f'Found span with rid={self.rid}: span_id={span["span_id"]}')
                self.spans.append(f'{span["trace_id"]}#{span["span_id"]}')

                # I would like to make validations even if there aren't iast events
                # if "_dd.iast.json" in span.get("meta", {}):
                self.appsec_iast_events.append({"span": span, "i": i, "log_filename": data["log_filename"]})

    def _get_related_spans(self):
        return [event for event in self.appsec_iast_events if "span" in event]

    def final_check(self):
        spans = self._get_related_spans()

        # Yes, i want to make some validations were there is not iast event. For example, if i use a secure hashing algoritm, i will want to check that there is no event.
        # if len(spans) == 0 and not self.is_success_on_expiry:
        #    self.set_failure(f"{self.message} not validated: Can't find any related IAST event")

        def vulnerabilityDecoder(vulDict):
            return namedtuple("X", vulDict.keys())(*vulDict.values())

        for span in spans:
            if not self.closed:
                span_data = span["span"]
                vulnerabilities = []
                if "_dd.iast.json" in span_data["meta"].keys():
                    appsec_iast_data = json.loads(span_data["meta"]["_dd.iast.json"], object_hook=vulnerabilityDecoder)
                    vulnerabilities = appsec_iast_data.vulnerabilities
                try:
                    if self.validate(vulnerabilities):
                        self.log_debug(f"{self} is validated by {span['log_filename']}")
                        self.is_success_on_expiry = True
                except Exception as e:
                    msg = traceback.format_exception_only(type(e), e)[0]
                    self.set_failure(
                        f"{m(self.message)} not validated on {span['log_filename']}, event #{span['i']}: {msg}"
                    )

    def validate(self, vulnerabilities):
        raise NotImplementedError


class _AppSecIastValidation(_BaseAppSecIastValidation):
    """

    Validator function can :
    * returns true => validation will be validated at the end (but trace will continue to be checked)
    * returns False or None => nothing is done
    * raise an exception => validation will fail
    """

    def __init__(self, request, validator, is_success_on_expiry=False):
        super().__init__(request=request)
        self.validator = validator
        self.is_success_on_expiry = is_success_on_expiry

    def validate(self, vulnerabilities):
        if self.validator:
            return self.validator(vulnerabilities)
        else:
            raise NotImplementedError