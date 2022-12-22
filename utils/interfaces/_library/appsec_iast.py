# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

""" AppSec IAST validations """


class _AppSecIastValidator:
    """Base class for all IAST validations"""

    def __init__(
        self, vulnerability_type=None, location_path=None, location_line=None, evidence=None, vulnerability_count=None,
    ):

        self.type = vulnerability_type
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

    def __call__(self, vulnerabilities):

        filtered_vulnerabilities = list(filter(lambda x: all(f(x) for f in self.filters), vulnerabilities))
        count_filtered = len(filtered_vulnerabilities)

        if not self._check_count_conditions(count_filtered):
            raise Exception(
                f"""Expected assertion failed:
    Expect count: {self.vulnerability_count},
    [ type: {self.type}, evidence:{self.evidence}, location: {self.location_path}({self.location_line}) )]
    All vulnerabilities: \n count:{len(vulnerabilities)},[ {(vulnerabilities)}]
    Filtered vulnerabilities: \n count:{len(filtered_vulnerabilities)},[ {(filtered_vulnerabilities)}] """
            )
        return True

    def _check_count_conditions(self, count_filtered):
        if self.vulnerability_count is None:
            return count_filtered > 0

        return self.vulnerability_count == count_filtered
