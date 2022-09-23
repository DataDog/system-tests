# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

""" AppSec IAST validations """
import traceback
import json
from collections import namedtuple
from utils.interfaces._core import BaseValidation
from utils.interfaces._library._utils import get_spans_related_to_rid
from utils.tools import m


class _BaseAppSecIastValidation(BaseValidation):
    """Base class for all IAST validations"""

    path_filters = ["/v0.4/traces"]

    def __init__(self, request):
        super().__init__(request=request)
        self.appsec_iast_events = []  # list of all appsec iast events
        self.request = request

    def check(self, data):
        if data["path"] == "/v0.4/traces":
            content = data["request"]["content"]

            for i, span in enumerate(get_spans_related_to_rid(content, self.rid)):
                self.log_debug(f'Found span with rid={self.rid}: span_id={span["span_id"]}')

                if "_dd.iast.json" in span.get("meta", {}):
                    self.appsec_iast_events.append({"span": span, "i": i, "log_filename": data["log_filename"]})

    def final_check(self):
        def vulnerability_dict(vulDict):
            return namedtuple("X", vulDict.keys())(*vulDict.values())

        if self.request.status_code == 404:
            self.set_failure(f"Called endpoint wasn't available. Status code: 404")
        for span in self.appsec_iast_events:
            if not self.closed:
                appsec_iast_data = json.loads(span["span"]["meta"]["_dd.iast.json"], object_hook=vulnerability_dict)
                vulnerabilities = appsec_iast_data.vulnerabilities
                try:
                    if self.validate(vulnerabilities):
                        self.log_debug(f"{self} is validated by {span['log_filename']}")
                        self.set_status(True)
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
        self, request, type=None, location_path=None, location_line=None, evidence=None, vulnerability_count=None
    ):

        super().__init__(request=request)
        self.type = type
        self.location_path = location_path
        self.location_line = location_line
        self.evidence = evidence
        self.vulnerability_count = vulnerability_count
        self.filters = []

        if self.type:
            self.filters.append(lambda vul: vul.type == self.type)

        if self.evidence:
            self.filters.append(lambda vul: vul.evidence.value == self.evidence)

        if self.location_path:
            self.filters.append(lambda vul: vul.location.path == self.location_path)
            if self.location_line:
                self.filters.append(lambda vul: vul.location.line == self.location_line)

    def validate(self, vulnerabilities):

        filtered_vulnerabilities = list(filter(lambda x: all(f(x) for f in self.filters), vulnerabilities))
        count_filtered = len(filtered_vulnerabilities)

        if not self._check_count_conditions(count_filtered):
            raise Exception(
                f"""Expected assertion failed:
    Expect count: {self.vulnerability_count},[ type: {self.type}, evidence:{self.evidence}, location: {self.location_path}({self.location_line}) )] 
    
    All vulnerabilities: \n count:{len(vulnerabilities)},[ {(vulnerabilities)}]
    
    Filtered vulnerabilities: \n count:{len(filtered_vulnerabilities)},[ {(filtered_vulnerabilities)}] """
            )
        return True

    def _check_count_conditions(self, count_filtered):
        if self.vulnerability_count is None:
            return count_filtered > 0
        else:
            return self.vulnerability_count == count_filtered


class _NoIastEvent(_BaseAppSecIastValidation):
    """Validator to be used when no IAST vulnerabilities are expected in a request"""

    is_success_on_expiry = True

    def validate(self, vulnerabilities):
        self.set_failure(f"{m(self.message)} => Vulnerabilites has been found : {vulnerabilities}")
