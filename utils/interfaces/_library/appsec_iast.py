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
from utils.interfaces._library.appsec_data import rule_id_to_type


class _BaseAppSecIastValidation(BaseValidation):
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


class VulnerabilityAsserts:
    """Verify the IAST features"""

    def __init__(
        self,
        count=1,
        type=None,
        location_path=None,
        location_line=None,
        evidence_value=None,
        only_these_vulnerabilities=False,
        least_count=False,
        any_match=False,
        count_exact=False,
    ):
        self.count = count
        self.type = type
        self.location_path = location_path
        self.location_line = location_line
        self.evidence_value = evidence_value
        self.only_these_vulnerabilities = only_these_vulnerabilities
        self.least_count = least_count
        self.any_match = any_match
        self.count_exact = count_exact

    def expect_exact_count(self, count):
        self.count_exact = True
        self.count = count
        return self

    def expect_at_least_count(self, count):
        self.count = count
        self.least_count = True
        return self

    def expect_any_match(self):
        self.any_match = True
        return self

    def filter_by_type(self, type):
        self.type = type
        return self

    def filter_by_location(self, location_path, location_line=None):
        self.location_path = location_path
        self.location_line = location_line
        return self

    def filter_by_evidence(self, evidence_value):
        self.evidence_value = evidence_value
        return self

    def expect_only_these_vulnerabilities(self):
        self.only_these_vulnerabilities = True
        return self

    def __check_filter_only_these_vulnerabilities(self, countTotal, countFiltered):
        return self.only_these_vulnerabilities and countTotal != countFiltered

    def __check_filter_any_match(self, countFiltered):
        return self.any_match and countFiltered == 0

    def __check_filter_at_least(self, countFiltered):
        return self.least_count and self.count > countFiltered

    def __check_filter_exact_count(self, countFiltered):
        if not self.any_match and not self.least_count and (not self.only_these_vulnerabilities or self.count_exact):
            return countFiltered != self.count
        return False

    def __getVulnerabilityFilters(self):
        filters = []

        if self.type:
            filters.append(lambda vul: vul.type == self.type)

        if self.evidence_value:
            filters.append(lambda vul: vul.evidence.value == self.evidence_value)

        if self.location_path:
            filters.append(lambda vul: vul.location.path == self.location_path)

            if self.location_line:
                filters.append(lambda vul: vul.location.line == self.location_line)
        return filters

    def __str__(self):
        return f" \n [ Vul count:{self.count}, type: {self.type}, evidence:{self.evidence_value}, location: {self.location_path}({self.location_line}), only_these_vulnerabilities:{self.only_these_vulnerabilities}, any_match:{self.any_match}, at_least_count:{self.least_count}]"

    def __str_vulnerabilties(self, vulnerabilities):
        return f" \n vulnerabilities_count:" + str(len(vulnerabilities)) + ", " + json.dumps(vulnerabilities)

    def validate(self, vulnerabilities):
        filters = self.__getVulnerabilityFilters()
        filteredVulnerabilities = list(filter(lambda x: all(f(x) for f in filters), vulnerabilities))

        countTotal = len(vulnerabilities)
        countFiltered = len(filteredVulnerabilities)

        if (
            self.__check_filter_only_these_vulnerabilities(countTotal, countFiltered)
            or self.__check_filter_any_match(countFiltered)
            or self.__check_filter_at_least(countFiltered)
            or self.__check_filter_exact_count(countFiltered)
        ):

            raise Exception(
                f"""Expected assertion failed:
Expected:  {str(self)} 
Current all vulnerabilities: {self.__str_vulnerabilties(vulnerabilities)} 
Current filtered vulnerabilitites: {self.__str_vulnerabilties(filteredVulnerabilities)}  """
            )
        return True
