# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import xml.etree.ElementTree as ET
from operator import attrgetter

from utils.tools import logger
import json


def junit_modifyreport(json_report_path, junit_report_path, junit_properties):
    """Add extra information to auto generated JUnit xml file"""

    json_report = json.load(open(json_report_path))
    # Open XML Junit report
    junit_report = ET.parse(junit_report_path)
    # get root element
    junit_report_root = junit_report.getroot()
    for test in json_report["tests"]:
        outcome = test["outcome"]
        nodeid = test["nodeid"]
        words = nodeid.split("::")
        if len(words) < 3:
            logger.warning(f"test nodeid cannot be parse: {nodeid}")
            continue
        classname = words[0].replace("/", ".").replace(".py", ".") + words[1]
        testcasename = words[2]

        # Util to search for rfcs and coverages
        search_class = words[0] + "::" + words[1]

        # Get doc/description for the test
        test_doc = None
        if nodeid in json_report["docs"]:
            test_doc = json_report["docs"][nodeid]

        # Get rfc for the test
        test_rfc = None
        if search_class in json_report["rfcs"]:
            test_rfc = json_report["rfcs"][search_class]

        # Get coverage for the test
        test_coverage = None
        if search_class in json_report["coverages"]:
            test_coverage = json_report["coverages"][search_class]

        # Get release versions for the test
        test_release = None
        if search_class in json_report["release_versions"]:
            test_release = json_report["release_versions"][search_class]

        skip_reason = test["skip_reason"]
        error_trace = ""

        _create_testcase_results(
            junit_report_root,
            classname,
            testcasename,
            outcome,
            skip_reason,
            error_trace,
            test_doc,
            test_rfc,
            test_coverage,
            test_release,
        )

    for testsuite in junit_report_root.findall("testsuite"):
        # Test suite name will be the scanario name
        # testsuite.set("name", os.environ.get("SYSTEMTESTS_SCENARIO", "EMPTY_SCENARIO"))
        # New properties node to add our custom tags
        ts_props = ET.SubElement(testsuite, "properties")
        _create_junit_testsuite_context(ts_props, junit_properties)
        _create_junit_testsuite_summary(ts_props, json_report["summary"])
        # I must to order tags: suite level tags works if they come up in the file before the testcase elements.
        # This is because we need to parse the XMLs incrementally we don't load all the tests in memory or
        # we would have to limit the number of supported tests per file.
        testsuite[:] = sorted(testsuite, key=attrgetter("tag"))

    junit_report.write(junit_report_path)


def _create_testcase_results(
    junit_xml_root,
    testclass_name,
    testcase_name,
    outcome,
    skip_reason,
    error_trace,
    test_doc,
    test_rfc,
    test_coverage,
    test_release,
):

    testcase = junit_xml_root.find(f"testsuite/testcase[@classname='{testclass_name}'][@name='{testcase_name}']")
    if testcase is not None:
        # Change name att because CI Visibility uses identifier: testsuite+name
        testcase.set("name", testclass_name + "." + testcase_name)

        # Add custom tags
        tc_props = ET.SubElement(testcase, "properties")

        ET.SubElement(tc_props, "property", name="dd_tags[systest.case.outcome]", value=outcome)
        ET.SubElement(tc_props, "property", name="dd_tags[systest.case.skip_reason]", value=str(skip_reason or ""))

        ET.SubElement(tc_props, "property", name="dd_tags[systest.case.doc]", value=str(test_doc or ""))
        ET.SubElement(tc_props, "property", name="dd_tags[systest.case.rfc]", value=str(test_rfc or ""))
        ET.SubElement(tc_props, "property", name="dd_tags[systest.case.coverage]", value=str(test_coverage or ""))
        if test_release:
            for library_name in test_release:
                ET.SubElement(
                    tc_props,
                    "property",
                    name=f"dd_tags[systest.case.release.library.{library_name}]",
                    value=str(test_release[library_name]),
                )
        if outcome == "failed":
            if skip_reason:
                tc_skipped = ET.SubElement(testcase, "skipped")
                tc_skipped.text = skip_reason
            else:
                tc_failure = ET.SubElement(testcase, "failure")
                tc_failure.text = error_trace

    else:
        logger.error(f"Not found in Junit xml report. Test class:{testclass_name} and test case name:{testcase_name}")


def _create_junit_testsuite_context(testsuite_props, junit_properties):
    for key, value in junit_properties.items():
        ET.SubElement(testsuite_props, "property", name=key, value=str(value or ""))


def _create_junit_testsuite_summary(testsuite_props, summary_json):
    if "passed" in summary_json:
        ET.SubElement(
            testsuite_props,
            "property",
            name="dd_tags[systest.suite.summary.passed]",
            value=str(summary_json.get("passed", 0)),
        )
    if "xfail" in summary_json:
        ET.SubElement(
            testsuite_props,
            "property",
            name="dd_tags[systest.suite.summary.xfail]",
            value=str(summary_json.get("xfail", 0)),
        )
    if "skipped" in summary_json:
        ET.SubElement(
            testsuite_props,
            "property",
            name="dd_tags[systest.suite.summary.skipped]",
            value=str(summary_json.get("skipped")),
        )
    ET.SubElement(
        testsuite_props,
        "property",
        name="dd_tags[systest.suite.summary.total]",
        value=str(summary_json.get("total", 0)),
    )
    ET.SubElement(
        testsuite_props,
        "property",
        name="dd_tags[systest.suite.summary.collected]",
        value=str(summary_json.get("collected", 0)),
    )
