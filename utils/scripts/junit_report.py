# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.
import os
import xml.etree.ElementTree as ET
from operator import attrgetter

from utils import context
from utils.tools import logger, get_log_formatter


def junit_modifyreport(
    json_report, junit_report_path, failed_nodeids, _skip_reasons, _docs, _rfcs, _coverages, _release_versions
):
    """Add extra information to auto generated JUnit xml file"""

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
        test_doc = _docs[nodeid]

        # Get rfc for the test
        test_rfc = None
        if search_class in _rfcs:
            test_rfc = _rfcs[search_class]

        # Get coverage for the test
        test_coverage = None
        if search_class in _coverages:
            test_coverage = _coverages[search_class]

        # Get release versions for the test
        test_release = None
        if search_class in _release_versions:
            test_release = _release_versions[search_class]

        skip_reason = _skip_reasons.get(nodeid)
        error_trace = ""

        if nodeid in failed_nodeids:
            outcome = "failed"
            if len(failed_nodeids[nodeid].logs) != 0:
                f = get_log_formatter()
                # There is a some invalid ascill characters
                error_trace = "\n".join(
                    [f.format(elem).replace("\x1b", "") for i, elem in enumerate(failed_nodeids[nodeid].logs)]
                )

        elif outcome in ("xfail", "xfailed"):
            # it means that the synchronous test is marked as expected failure
            # but all asynchronous test are ok
            outcome = "xpassed"

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
        testsuite.set("name", classname)
        # New properties node to add our custom tags
        ts_props = ET.SubElement(testsuite, "properties")
        _create_junit_testsuite_context(ts_props)
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
        # testcase.set("name", testclass_name + "." + testcase_name)

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
                    value=test_release[library_name],
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


def _create_junit_testsuite_context(testsuite_props):

    ET.SubElement(
        testsuite_props, "property", name="dd_tags[systest.suite.context.agent]", value=str(context.agent_version or "")
    )
    ET.SubElement(
        testsuite_props,
        "property",
        name="dd_tags[systest.suite.context.library.name]",
        value=str(context.library.library or ""),
    )
    ET.SubElement(
        testsuite_props,
        "property",
        name="dd_tags[systest.suite.context.library.version]",
        value=str(context.library.version or ""),
    )
    ET.SubElement(
        testsuite_props,
        "property",
        name="dd_tags[systest.suite.context.weblog_variant]",
        value=str(context.weblog_variant or ""),
    )
    ET.SubElement(
        testsuite_props,
        "property",
        name="dd_tags[systest.suite.context.sampling_rate]",
        value=str(context.sampling_rate or ""),
    )
    ET.SubElement(
        testsuite_props,
        "property",
        name="dd_tags[systest.suite.context.libddwaf_version]",
        value=str(context.libddwaf_version or ""),
    )
    ET.SubElement(
        testsuite_props,
        "property",
        name="dd_tags[systest.suite.context.appsec_rules_file]",
        value=str(context.appsec_rules_file or ""),
    )
    ET.SubElement(
        testsuite_props,
        "property",
        name="dd_tags[systest.suite.context.scenario]",
        value=os.environ.get("SYSTEMTESTS_SCENARIO", ""),
    )


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
