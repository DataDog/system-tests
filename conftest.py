# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import os
import collections
import inspect
import time

from pytest_jsonreport.plugin import JSONReport
import _pytest

from utils import context, data_collector, interfaces
from utils.tools import logger, m, get_log_formatter, get_exception_traceback
from utils._xfail import xfails


# Monkey patch JSON-report plugin to avoid noise in report
JSONReport.pytest_terminal_summary = lambda *args, **kwargs: None


class CustomTerminalReporter(_pytest.terminal.TerminalReporter):
    def pytest_sessionstart(self, session):
        self._session = session
        self._sessionstarttime = time.time()

        self.write_sep("=", "test session starts", bold=True)
        self.write_line(f"Library: {context.library}")
        self.write_line(f"Agent: {context.agent_version}")

        if context.library == "php":
            self.write_line(f"AppSec: {context.php_appsec}")

        if context.libddwaf_version:
            self.write_line(f"libddwaf: {context.libddwaf_version}")

        if context.appsec_rules_file:
            self.write_line(f"AppSec rules file: {context.appsec_rules_file}")

        self.write_line(f"AppSec rules version: {context.appsec_rules_version}")
        self.write_line(f"Weblog variant: {context.weblog_variant}")
        self.write_line(f"Backend: {context.dd_site}")


_pytest.terminal.TerminalReporter = CustomTerminalReporter

_docs = {}
_skip_reasons = {}
_release_versions = {}
_coverages = {}
_rfcs = {}

# Called at the very begening
def pytest_sessionstart(session):

    logger.debug(f"Library: {context.library}")
    logger.debug(f"Agent: {context.agent_version}")
    if context.library == "php":
        logger.debug(f"AppSec: {context.php_appsec}")

    logger.debug(f"libddwaf: {context.libddwaf_version}")
    logger.debug(f"AppSec rules version: {context.appsec_rules_version}")
    logger.debug(f"Weblog variant: {context.weblog_variant}")
    logger.debug(f"Backend: {context.dd_site}")

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
        else:  #  otherwise, search in named arguments
            return marker.kwargs.get("reason", "")

    return None


def pytest_runtestloop(session):

    terminal = session.config.pluginmanager.get_plugin("terminalreporter")

    terminal.write_line("Executing weblog warmup...")
    context.execute_warmups()

    # From https://github.com/pytest-dev/pytest/blob/33c6ad5bf76231f1a3ba2b75b05ea2cd728f9919/src/_pytest/main.py#L337

    if session.testsfailed and not session.config.option.continue_on_collection_errors:
        raise session.Interrupted(
            "%d error%s during collection" % (session.testsfailed, "s" if session.testsfailed != 1 else "")
        )

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

    timeout = interface.expected_timeout

    try:
        if len(interface.validations) != 0:
            if timeout:
                terminal.write_sep("-", f"Async validations for {interface} (wait {timeout}s)")
            else:
                terminal.write_sep("-", f"Async validations for {interface}")

        if timeout:
            interface.wait(timeout=timeout)
        else:
            interface.wait()

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

        for method, validations in methods.items():
            is_passed = len([v for v in validations if v in passed]) == len(validations)
            is_failed = len([v for v in validations if v in failed]) != 0
            is_xpassed = len([v for v in validations if v in xpassed]) == len(validations)
            is_xfailed = len([v for v in validations if v in xfailed]) != 0

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
            for validation in interface._validations:
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

    data_collector.shutdown()
    data_collector.join(timeout=10)

    # Is it really a test ?
    if data_collector.is_alive():
        logger.error("Can't terminate data collector")
