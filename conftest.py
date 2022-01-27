# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import collections
import inspect

from utils import context, data_collector, interfaces
from utils.tools import logger, o, w, m, get_log_formatter, get_exception_traceback
from utils._xfail import xfails

from pytest_jsonreport.plugin import JSONReport

# Monkey patch JSON-report plugin to avoid noise in report
JSONReport.pytest_terminal_summary = lambda *args, **kwargs: None

_docs = {}
_skip_reasons = {}
_release_versions = {}
_rfcs = {}


def pytest_sessionstart(session):

    logger.debug(f"Library: {context.library}")
    logger.debug(f"Agent: {context.agent_version}")
    if context.library == "php":
        logger.debug(f"AppSec: {context.php_appsec}")

    logger.debug(f"libddwaf: {context.libddwaf_version}")
    logger.debug(f"Weblog variant: {context.weblog_variant}")
    logger.debug(f"Backend: {context.dd_site}")

    # connect interface validators to data collector
    data_collector.proxy_callbacks["agent"].append(interfaces.agent.append_data)
    data_collector.proxy_callbacks["library"].append(interfaces.library.append_data)
    data_collector.start()


def pytest_report_header(config):
    headers = [f"Library: {context.library}", f"Agent: {context.agent_version}"]

    if context.library == "php":
        headers.append(f"AppSec: {context.php_appsec}")

    if context.libddwaf_version:
        headers.append(f"libddwaf: {context.libddwaf_version}")

    if context.appsec_rules:
        headers.append(f"AppSec rules: {context.appsec_rules}")

    headers += [
        f"Weblog variant: {context.weblog_variant}",
        f"Backend: {context.dd_site}",
    ]
    return headers


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


def pytest_itemcollected(item):

    _docs[item.nodeid] = item.obj.__doc__
    _docs[item.parent.nodeid] = item.parent.obj.__doc__

    _release_versions[item.parent.nodeid] = getattr(item.parent.obj, "__released__", None)

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


def _wait_interface(interface, session, timeout=None):
    terminal = session.config.pluginmanager.get_plugin("terminalreporter")

    # side note : do NOT skip this function even if interface has no validations
    # internal errors may cause no validation in interface

    if timeout:
        terminal.write_line(f"Wait {timeout}s for {interface}: {interface.validations_count} to be validated")
        interface.wait(timeout=timeout)
    else:
        terminal.write_line(f"Wait for {interface}: {interface.validations_count} to be validated")
        interface.wait()

    if not interface.is_success:
        session.shouldfail = f"{interface} is not validated"
        terminal.write_line(f"{interface}: failure")
        return False

    return True


def pytest_runtestloop(session):

    terminal = session.config.pluginmanager.get_plugin("terminalreporter")

    terminal.write_line(f"Executing weblog warmup...")
    context.execute_warmups()

    """From https://github.com/pytest-dev/pytest/blob/33c6ad5bf76231f1a3ba2b75b05ea2cd728f9919/src/_pytest/main.py#L337"""
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

    if context.library == "java":
        timeout = 80
    elif context.library.library in ("php", "nodejs"):
        timeout = 5
    else:
        timeout = 40

    terminal.write_line("")
    terminal.write_sep("-", f"Wait for async validations")

    success = True

    success = _wait_interface(interfaces.library, session, timeout) and success
    success = _wait_interface(interfaces.library_stdout, session) and success
    success = _wait_interface(interfaces.library_dotnet_managed, session) and success

    timeout = 5 if context.library.library in ("php", "nodejs") else 40
    success = _wait_interface(interfaces.agent, session, timeout) and success

    if not success:
        raise session.Failed(session.shouldfail)

    return True


def pytest_json_modifyreport(json_report):

    try:
        logger.debug("Modifying JSON report")

        # report test with a failing asyn validation as failed
        failed_nodeids = set()

        for interface in interfaces.all:
            for validation in interface._validations:
                if validation.closed and not validation.is_success:
                    filename, klass, function = validation.get_test_source_info()
                    nodeid = f"{filename}::{klass}::{function}"
                    failed_nodeids.add(nodeid)

        for test in json_report["tests"]:
            test["skip_reason"] = _skip_reasons.get(test["nodeid"])
            if test["nodeid"] in failed_nodeids:
                test["outcome"] = "failed"

        # add usefull data for reporting
        json_report["docs"] = _docs
        json_report["context"] = context.serialize()
        json_report["release_versions"] = _release_versions
        json_report["rfcs"] = _rfcs

        # clean useless and volumetric data
        del json_report["collectors"]

        for test in json_report["tests"]:
            if test["nodeid"] in failed_nodeids:
                test["outcome"] = "failed"

            for k in ("setup", "call", "teardown", "keywords", "lineno"):
                if k in test:
                    del test[k]

        logger.debug("Modifying JSON report finished")
    except Exception as e:
        logger.error(f"Fail to modify json report", exc_info=True)


def pytest_terminal_summary(terminalreporter, exitstatus, config):

    passed = []
    failed = []
    xpassed = []
    xfailed = []

    for interface in interfaces.all:

        if interface.system_test_error is not None:
            terminalreporter.write_sep("=", f"INTERNAL ERROR ON SYSTEM TESTS", red=True, bold=True)
            terminalreporter.line("Traceback (most recent call last):", red=True)
            for line in get_exception_traceback(interface.system_test_error):
                terminalreporter.line(line, red=True)
            return

        passed += interface.passed
        failed += interface.failed
        xpassed += interface.xpassed
        xfailed += interface.xfailed

    _print_async_failure_report(terminalreporter, failed, passed)


def pytest_sessionfinish(session, exitstatus):

    data_collector.shutdown()
    data_collector.join(timeout=10)

    # Is it really a test ?
    if data_collector.is_alive():
        logger.error("Can't terminate data collector")


def _print_async_failure_report(terminalreporter, failed, passed):
    """Given a list of validation, build a fancy report of source code that instanciate each validation object"""

    # Create a tree filename > functions > fails
    files = collections.defaultdict(lambda: collections.defaultdict(list))

    if len(failed) != 0:
        terminalreporter.line("")
        terminalreporter.write_sep("=", "ASYNC FAILURE" if len(failed) == 1 else "ASYNC FAILURES", red=True, bold=True)

        for fail in failed:
            filename, _, function = fail.get_test_source_info()
            files[filename][function].append(fail)

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
                        f":{fail.frame.lineno}: {m(fail.message)} not validated on {fail._interface} interface"
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
        if len([v for v in validations if not v.is_success]) == 0 and len(validations) != 0:
            xpassed_methods.append(validations[0])

    xpassed_classes = []
    for validations in xfails.classes.values():
        if len([v for v in validations if not v.is_success]) == 0 and len(validations) != 0:
            xpassed_classes.append(validations[0])

    if len(failed) != 0 or len(xpassed_methods) != 0 or len(xpassed_classes) != 0:
        terminalreporter.write_sep("=", "short async test summary info")

        for filename, functions in files.items():
            for function, fails in functions.items():
                filename, klass, function = fails[0].get_test_source_info()
                terminalreporter.line(f"FAILED {filename}::{klass}::{function} - {len(fails)} fails")

        for validation in xpassed_methods:
            filename, klass, function = validation.get_test_source_info()
            terminalreporter.line(
                f"XPASSED {filename}::{klass}::{function} - Expected to fail, but all is ok", yellow=True
            )

        for validation in xpassed_classes:
            filename, klass, function = validation.get_test_source_info()
            terminalreporter.line(f"XPASSED {filename}::{klass} - Expected to fail, but all is ok", yellow=True)

        terminalreporter.line("")
