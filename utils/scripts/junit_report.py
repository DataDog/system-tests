# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import xml.etree.ElementTree as ET
from operator import attrgetter


def junit_modifyreport(junit_report_path: str) -> None:
    """Add extra information to auto generated JUnit xml file"""

    # Open XML Junit report
    junit_report = ET.parse(junit_report_path)  # noqa: S314
    # get root element
    junit_report_root: ET.Element = junit_report.getroot()
    for testsuite in junit_report_root.findall("testsuite"):
        # Test suite name will be the scanario name
        # testsuite.set("name", os.environ.get("SYSTEMTESTS_SCENARIO", "EMPTY_SCENARIO"))
        # New properties node to add our custom tags
        ts_props = testsuite.find("properties")
        if ts_props is None:
            ts_props = ET.SubElement(testsuite, "properties")

        # I must to order tags: suite level tags works if they come up in the file before the testcase elements.
        # This is because we need to parse the XMLs incrementally we don't load all the tests in memory or
        # we would have to limit the number of supported tests per file.
        testsuite[:] = sorted(testsuite, key=attrgetter("tag"))

        for testcase in testsuite.findall("testcase"):
            if "classname" in testcase.attrib:
                testcase.attrib["name"] = testcase.attrib["classname"] + "." + testcase.attrib["name"]
                del testcase.attrib["classname"]

    junit_report.write(junit_report_path)
