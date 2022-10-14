# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import os
import collections
import inspect

from pytest_jsonreport.plugin import JSONReport

from utils import context, data_collector, interfaces
from utils.tools import logger, m, get_log_formatter, get_exception_traceback
from utils._xfail import xfails
from os.path import exists

import pytest
import json
import xml.etree.ElementTree as ET
from operator import attrgetter


# Monkey patch JSON-report plugin to avoid noise in report
JSONReport.pytest_terminal_summary = lambda *args, **kwargs: None

_docs = {}
_skip_reasons = {}
_release_versions = {}
_coverages = {}
_rfcs = {}

# Called at the very begening
def pytest_sessionstart(session):
    terminal = session.config.pluginmanager.get_plugin("terminalreporter")

    def print_info(info):
        logger.debug(info)
        terminal.write_line(info)

    if "SYSTEMTESTS_SCENARIO" in os.environ:  # means the we are running test_the_test
        terminal.write_sep("=", "Tested components", bold=True)
        print_info(f"Library: {context.library}")
        print_info(f"Agent: {context.agent_version}")
        if context.library == "php":
            print_info(f"AppSec: {context.php_appsec}")

        if context.libddwaf_version:
            print_info(f"libddwaf: {context.libddwaf_version}")

        if context.appsec_rules_file:
            print_info(f"AppSec rules version: {context.appsec_rules_version}")

        print_info(f"Weblog variant: {context.weblog_variant}")
        print_info(f"Backend: {context.dd_site}")

        # connect interface validators to data collector
        data_collector.proxy_callbacks["agent"].append(interfaces.agent.append_data)
        data_collector.proxy_callbacks["library"].append(interfaces.library.append_data)
        data_collector.start()


# called when each test item is collected
def pytest_itemcollected(item):

    _docs[item.nodeid] = item.obj.__doc__
    _docs[item.parent.nodeid] = item.parent.obj.__doc__

    _release_versions[item.parent.nodeid] = getattr(item.parent.obj, "__released__", None)

    if hasattr(item.parent.obj, "__coverage__"):
        _coverages[item.parent.nodeid] = getattr(item.parent.obj, "__coverage__")

    if hasattr(item.parent.obj, "__rfc__"):
        _rfcs[item.parent.nodeid] = getattr(item.parent.obj, "__rfc__")
    if hasattr(item.obj, "__rfc__"):
        _rfcs[item.nodeid] = getattr(item.obj, "__rfc__")

    if hasattr(item.parent.parent, "obj"):
        _docs[item.parent.parent.nodeid] = item.parent.parent.obj.__doc__
    else:
        _docs[item.parent.parent.nodeid] = "Unexpected structure"

    markers = item.own_markers

    parent = item.parent
    while parent is not None:
        markers += parent.own_markers
        parent = parent.parent

    for marker in reversed(markers):
        skip_reason = _get_skip_reason_from_marker(marker)
        if skip_reason:
            _skip_reasons[item.nodeid] = skip_reason
            break


def _get_skip_reason_from_marker(marker):
    if marker.name == "skipif":
        if all(marker.args):
            return marker.kwargs.get("reason", "")
    elif marker.name in ("skip", "expected_failure"):
        if len(marker.args):  # if un-named arguments are present, the first one is the reason
            return marker.args[0]

        # otherwise, search in named arguments
        return marker.kwargs.get("reason", "")

    return None


def pytest_runtestloop(session):

    terminal = session.config.pluginmanager.get_plugin("terminalreporter")

    terminal.write_line("Executing weblog warmup...")
    context.execute_warmups()

    # From https://github.com/pytest-dev/pytest/blob/33c6ad5bf76231f1a3ba2b75b05ea2cd728f9919/src/_pytest/main.py#L337

    if session.testsfailed and not session.config.option.continue_on_collection_errors:
        raise session.Interrupted(f"{session.testsfailed} error(s) during collection")

    if session.config.option.collectonly:
        return True

    for i, item in enumerate(session.items):
        nextitem = session.items[i + 1] if i + 1 < len(session.items) else None
        item.config.hook.pytest_runtest_protocol(item=item, nextitem=nextitem)
        if session.shouldfail:
            raise session.Failed(session.shouldfail)
        if session.shouldstop:
            raise session.Interrupted(session.shouldstop)

    terminal.write_line("")

    success = True

    success = _wait_interface(interfaces.library, session) and success
    success = _wait_interface(interfaces.library_stdout, session) and success
    success = _wait_interface(interfaces.library_dotnet_managed, session) and success
    success = _wait_interface(interfaces.agent, session) and success
    success = _wait_interface(interfaces.backend, session) and success

    if not success:
        raise session.Failed(session.shouldfail)

    return True


def pytest_report_teststatus(report, config):
    if report.when != "call":
        return

    if report.keywords.get("expected_failure") == 1:
        return "xfail", "x", "XFAIL"


def _wait_interface(interface, session):
    terminal = session.config.pluginmanager.get_plugin("terminalreporter")

    # side note : do NOT skip this function even if interface has no validations
    # internal errors may cause no validation in interface

    timeout = interface.get_expected_timeout(context=context)

    try:
        if len(interface.validations) != 0:
            terminal.write_sep("-", f"Async validations for {interface} (wait {timeout}s)")

        interface.wait(timeout=timeout)

    except Exception as e:
        session.shouldfail = f"{interface} is not validated"
        terminal.write_line(f"{interface}: unexpected failure")
        interface.system_test_error = e
        return False

    if not interface.is_success:
        session.shouldfail = f"{interface} is not validated"
        return False

    return True


def pytest_terminal_summary(terminalreporter, exitstatus, config):

    validations = []
    passed = []
    failed = []
    xpassed = []
    xfailed = []

    for interface in interfaces.all_interfaces:

        if interface.system_test_error is not None:
            terminalreporter.write_sep("=", "INTERNAL ERROR ON SYSTEM TESTS", red=True, bold=True)
            for line in get_exception_traceback(interface.system_test_error):
                terminalreporter.line(line, red=True)
            return

        validations += interface.validations
        passed += interface.passed
        failed += interface.failed
        xpassed += interface.xpassed
        xfailed += interface.xfailed

    _print_async_test_list(terminalreporter, validations, passed, failed, xpassed, xfailed)
    _print_async_failure_report(terminalreporter, failed, passed)
    _pytest_junit_modifyreport()


def _print_async_test_list(terminal, validations, passed, failed, xpassed, xfailed):
    """build list of test file, with a letter for each test method describing
    the state of the method regarding async validations"""

    # Create a tree filename > methods > fails
    files = collections.defaultdict(lambda: collections.defaultdict(list))

    for validation in validations:
        filename, _, method = validation.get_test_source_info()
        files[filename][method].append(validation)

    terminal_column_count = int(os.environ.get("COLUMNS", "80"))

    for filename, methods in files.items():
        terminal.write(f"{filename} ")
        current_column = len(filename)

        for method, local_validations in methods.items():
            is_passed = len([v for v in local_validations if v in passed]) == len(local_validations)
            is_failed = len([v for v in local_validations if v in failed]) != 0
            is_xpassed = len([v for v in local_validations if v in xpassed]) == len(local_validations)
            is_xfailed = len([v for v in local_validations if v in xfailed]) != 0

            current_column += 1
            if (current_column) % terminal_column_count == 0:
                terminal.write_line("")
                current_column = 0

            if is_passed:
                terminal.write(".", bold=True, green=True)
            elif is_failed:
                terminal.write("F", bold=True, red=True)
            elif is_xpassed:
                terminal.write("X", yellow=True)
            elif is_xfailed:
                terminal.write("x", green=True)
            else:
                terminal.write("O", red=True)

        terminal.write_line("")

    terminal.write_line("")


def _print_async_failure_report(terminalreporter, failed, passed):
    """Given a list of validation, build a fancy report of source code that instanciate each validation object"""

    # Create a tree filename > functions > fails
    files = collections.defaultdict(lambda: collections.defaultdict(list))

    for fail in failed:
        filename, _, function = fail.get_test_source_info()
        files[filename][function].append(fail)

    if len(failed) != 0:
        terminalreporter.line("")
        terminalreporter.write_sep("=", "ASYNC FAILURE" if len(failed) == 1 else "ASYNC FAILURES", red=True, bold=True)

        for filename, functions in files.items():

            for function, fails in functions.items():
                terminalreporter.write_sep("_", function, red=True, bold=True)
                terminalreporter.line("")
                fails = sorted(fails, key=lambda v: v.frame.lineno)

                latest_frame = fails[-1].frame
                lines, function_line = inspect.findsource(latest_frame[0])

                lines = [f"    {line[:-1]}" for line in lines]  # add padding, remove endline

                for fail in fails:
                    line = lines[fail.frame.lineno - 1]
                    lines[fail.frame.lineno - 1] = "E" + line[1:]

                lines = lines[function_line : latest_frame.lineno]

                for line in lines:
                    terminalreporter.line(line, red=line.startswith("E"), bold=line.startswith("E"))

                terminalreporter.line("")
                logs = []
                for fail in fails:
                    filename = filename.replace("/app/", "")

                    terminalreporter.write(filename, bold=True, red=True)
                    terminalreporter.line(
                        f":{fail.frame.lineno}: {m(fail.message)} not validated on {fail.interface} interface"
                    )

                    logs += fail.logs

                if len(logs) != 0:
                    terminalreporter.write_sep("-", "Captured stdout call")
                    f = get_log_formatter()
                    for log in logs:
                        terminalreporter.line(f.format(log))
                    terminalreporter.line("")

    xpassed_methods = []
    for validations in xfails.methods.values():

        failed_validations = [v for v in validations if not v.is_success]

        if len(failed_validations) == 0 and len(validations) != 0:
            filename, klass, function = validations[0].get_test_source_info()

            if _coverages.get(f"{filename}::{klass}") != "not-implemented":
                xpassed_methods.append(f"{filename}::{klass}::{function}")

    if len(failed) != 0 or len(xpassed_methods) != 0:
        terminalreporter.write_sep("=", "short async test summary info")

        for filename, functions in files.items():
            for function, fails in functions.items():
                filename, klass, function = fails[0].get_test_source_info()
                terminalreporter.line(f"FAILED {filename}::{klass}::{function} - {len(fails)} fails", red=True)

        for method in xpassed_methods:
            terminalreporter.line(f"XPASSED {method} - Expected to fail, but all is ok", yellow=True)

        terminalreporter.line("")


def pytest_json_modifyreport(json_report):

    try:
        logger.debug("Modifying JSON report")

        # report test with a failing asyn validation as failed
        failed_nodeids = set()

        for interface in interfaces.all_interfaces:
            for validation in interface.validations:
                if validation.closed and not validation.is_success:
                    filename, klass, function = validation.get_test_source_info()
                    nodeid = f"{filename}::{klass}::{function}"
                    failed_nodeids.add(nodeid)

        # populate and adjust some data
        for test in json_report["tests"]:
            test["skip_reason"] = _skip_reasons.get(test["nodeid"])
            if test["nodeid"] in failed_nodeids:
                test["outcome"] = "failed"
            elif test["outcome"] in ("xfail", "xfailed"):
                # it means that the synchronous test is marked as expected failure
                # but all asynchronous test are ok
                test["outcome"] = "xpassed"

        # add usefull data for reporting
        json_report["docs"] = _docs
        json_report["context"] = context.serialize()
        json_report["release_versions"] = _release_versions
        json_report["rfcs"] = _rfcs
        json_report["coverages"] = _coverages

        # clean useless and volumetric data
        del json_report["collectors"]

        for test in json_report["tests"]:
            for k in ("setup", "call", "teardown", "keywords", "lineno"):
                if k in test:
                    del test[k]

        logger.debug("Modifying JSON report finished")
    except:
        logger.error("Fail to modify json report", exc_info=True)


def pytest_sessionfinish(session, exitstatus):

    if "SYSTEMTESTS_SCENARIO" in os.environ:  # means the we are running test_the_test
        data_collector.shutdown()
        data_collector.join(timeout=10)

        # Is it really a test ?
        if data_collector.is_alive():
            logger.error("Can't terminate data collector")


def _pytest_junit_modifyreport():

    json_report_path = "logs/report.json"
    junit_report_path = "logs/reportJunit.xml"

    if not os.path.exists(json_report_path) or not os.path.exists(junit_report_path):
        logger.warning("Not all required output reports found(report.json or reportJunit.xml)")
        return

    # Opening JSON file
    f = open(json_report_path)
    json_report = json.load(f)

    # Open XML Junit report
    junit_report = ET.parse(junit_report_path)
    # get root element
    junit_report_root = junit_report.getroot()

    for test in json_report["tests"]:
        words = test["nodeid"].split("::")
        if len(words) < 3:
            logger.warning(f"test nodeid cannot be parse: {test['nodeid']}")
            continue
        classname = words[0].replace("/", ".").replace(".py", ".") + words[1]
        testcasename = words[2]

        # Util to search for rfcs and coverages
        search_class = words[0] + "::" + words[1]

        # Get doc/description for the test
        test_doc = json_report["docs"][test["nodeid"]]

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

        _create_testcase_results(
            junit_report_root,
            classname,
            testcasename,
            test["outcome"],
            test["skip_reason"],
            test_doc,
            test_rfc,
            test_coverage,
            test_release,
        )

    for testsuite in junit_report_root.findall("testsuite"):
        # Test suite name will be the scanario name
        testsuite.set("name", f"{os.environ.get('SYSTEMTESTS_SCENARIO','EMPTY_SCENARIO')}")
        # New properties node to add our custom tags
        ts_props = ET.SubElement(testsuite, "properties")
        _create_junit_testsuite_context(ts_props)
        _create_junit_testsuite_summary(ts_props, json_report["summary"])
        # I must to order tags: the tags at suite level only work if they come up in the file before the testcase elements.
        # This is because we need to parse the XMLs incrementally we don't load all the tests in memory or we would have to limit the number of supported tests per file.
        testsuite[:] = sorted(testsuite, key=attrgetter("tag"))

    junit_report.write("logs/reportJunit.xml")


def _create_junit_testsuite_context(testsuite_props):

    ET.SubElement(
        testsuite_props, "property", name="dd_tags[systest.suite.context.agent]", value=f"{context.agent_version}"
    )
    ET.SubElement(
        testsuite_props,
        "property",
        name="dd_tags[systest.suite.context.library.name]",
        value=f"{context.library.library}",
    )
    ET.SubElement(
        testsuite_props,
        "property",
        name="dd_tags[systest.suite.context.library.version]",
        value=f"{context.library.version}",
    )
    ET.SubElement(
        testsuite_props,
        "property",
        name="dd_tags[systest.suite.context.weblog_variant]",
        value=f"{context.weblog_variant}",
    )
    ET.SubElement(
        testsuite_props, "property", name="dd_tags[systest.suite.context.dd_site]", value=f"{context.dd_site}"
    )
    ET.SubElement(
        testsuite_props,
        "property",
        name="dd_tags[systest.suite.context.sampling_rate]",
        value=f"{context.sampling_rate}",
    )
    ET.SubElement(
        testsuite_props,
        "property",
        name="dd_tags[systest.suite.context.libddwaf_version]",
        value=f"{context.libddwaf_version}",
    )
    ET.SubElement(
        testsuite_props,
        "property",
        name="dd_tags[systest.suite.context.appsec_rules_file]",
        value=f"{context.appsec_rules_file}",
    )
    ET.SubElement(
        testsuite_props,
        "property",
        name="dd_tags[systest.suite.context.scenario]",
        value=f"{os.environ.get('SYSTEMTESTS_SCENARIO')}",
    )


def _create_junit_testsuite_summary(testsuite_props, summary_json):
    if "passed" in summary_json:
        ET.SubElement(
            testsuite_props,
            "property",
            name="dd_tags[systest.suite.summary.passed]",
            value=f"{ summary_json['passed']}",
        )
    if "xfail" in summary_json:
        ET.SubElement(
            testsuite_props, "property", name="dd_tags[systest.suite.summary.xfail]", value=f"{ summary_json['xfail']}"
        )
    if "skipped" in summary_json:
        ET.SubElement(
            testsuite_props,
            "property",
            name="dd_tags[systest.suite.summary.skipped]",
            value=f"{ summary_json['skipped']}",
        )
    ET.SubElement(
        testsuite_props, "property", name="dd_tags[systest.suite.summary.total]", value=f"{ summary_json['total']}"
    )
    ET.SubElement(
        testsuite_props,
        "property",
        name="dd_tags[systest.suite.summary.collected]",
        value=f"{ summary_json['collected']}",
    )


def _create_testcase_results(
    junit_xml_root, testclass_name, testcase_name, outcome, skip_reason, test_doc, test_rfc, test_coverage, test_release
):

    testcase = junit_xml_root.find(f"testsuite/testcase[@classname='{testclass_name}'][@name='{testcase_name}']")
    if testcase:
        # Change name att because CI Visibility uses identifier: testsuite+name
        testcase.set("name", testclass_name + "." + testcase_name)
        # Add custom tags
        tc_props = ET.SubElement(testcase, "properties")
        ET.SubElement(tc_props, "property", name="dd_tags[systest.case.outcome]", value=f"{outcome}")
        ET.SubElement(tc_props, "property", name="dd_tags[systest.case.skip_reason]", value=f"{skip_reason}")
        ET.SubElement(tc_props, "property", name="dd_tags[systest.case.doc]", value=f"{test_doc}")
        ET.SubElement(tc_props, "property", name="dd_tags[systest.case.rfc]", value=f"{test_rfc}")
        ET.SubElement(tc_props, "property", name="dd_tags[systest.case.coverage]", value=f"{test_coverage}")
        if test_release:
            for library_name in test_release:
                ET.SubElement(
                    tc_props,
                    "property",
                    name=f"dd_tags[systest.case.release.library.{library_name}]",
                    value=f"{test_release[library_name]}",
                )
        if outcome == "failed":
            if bool(skip_reason):
                tc_skipped = ET.SubElement(testcase, "skipped")
                tc_skipped.text = skip_reason
            else:
                tc_failure = ET.SubElement(testcase, "failure")
                tc_failure.text = "failed test"

    else:
        logger.error(f"Not found in Junit xml report. Test class:{testclass_name} and test case name:{testcase_name}")
