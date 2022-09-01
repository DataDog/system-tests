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
    Validator filters vulnerabilities found in the iast message and check the expected counter
    Validator function can :
    * returns true => validation will be validated at the end (but trace will continue to be checked)
    * returns False or None => nothing is done
    * raise an exception => validation will fail
    """

    def __init__(
        self, request, type=None, location_path=None, location_line=None, evidence=None, vulnarability_count=None
    ):

        super().__init__(request=request)
        self.type = type
        self.location_path = location_path
        self.location_line = location_line
        self.evidence = evidence
        self.vulnarability_count = vulnarability_count

    def validate(self, vulnerabilities):
        filters = self.__get_vulnerability_filters()
        filteredVulnerabilities = list(filter(lambda x: all(f(x) for f in filters), vulnerabilities))
        countFiltered = len(filteredVulnerabilities)

        if not self.__check_count_conditions(countFiltered):
            raise Exception(
                f"""Expected assertion failed:
    Expected:  {str(self)} 
    All vulnerabilities: {self.__str_vulnerabilties(vulnerabilities)} 
    Filtered vulnerabilitites: {self.__str_vulnerabilties(filteredVulnerabilities)}  """
            )
        return True

    def __get_vulnerability_filters(self):
        filters = []

        if self.type:
            filters.append(lambda vul: vul.type == self.type)

        if self.evidence:
            filters.append(lambda vul: vul.evidence.value == self.evidence)

        if self.location_path:
            filters.append(lambda vul: vul.location.path == self.location_path)
            if self.location_line:
                filters.append(lambda vul: vul.location.line == self.location_line)
        return filters

    def __check_count_conditions(self, countFiltered):
        if self.vulnarability_count is None:
            return countFiltered > 0
        else:
            return self.vulnarability_count == countFiltered

    def __str_vulnerabilties(self, vulnerabilities):
        return f" \n count:" + str(len(vulnerabilities)) + ", " + json.dumps(vulnerabilities)

    def __str__(self):
        return f" \n Expect count: {self.vulnarability_count},[ type: {self.type}, evidence:{self.evidence}, location: {self.location_path}({self.location_line}) )]"
