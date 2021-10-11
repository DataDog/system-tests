# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import collections
import pytest
import inspect
import traceback

from utils import context, data_collector, interfaces
from utils.tools import logger, o, w, m, get_log_formatter

_docs = {}
_skip_reasons = {}


def pytest_sessionstart(session):
    logger.debug(f"Library: {context.library}")
    logger.debug(f"Weblog variant: {context.weblog_variant}")
    logger.debug(f"Backend: {context.dd_site}")

    # connect interface validators to data collector
    data_collector.proxy_callbacks["agent"].append(interfaces.agent.append_data)
    data_collector.proxy_callbacks["library"].append(interfaces.library.append_data)
    data_collector.start()


def pytest_report_header(config):
    return f"Library: {context.library}\nWeblog variant: {context.weblog_variant}\nBackend: {context.dd_site}"


def pytest_itemcollected(item):
    _docs[item.nodeid] = item.obj.__doc__
    _docs[item.parent.nodeid] = item.parent.obj.__doc__

    if hasattr(item.parent.parent, "obj"):
        _docs[item.parent.parent.nodeid] = item.parent.parent.obj.__doc__
    else:
        _docs[item.parent.parent.nodeid] = "Unexpected structure"

    for marker in item.own_markers:
        if marker.name == "skipif":
            if all(marker.args):
                _skip_reasons[item.nodeid] = marker.kwargs.get("reason", "")
        elif marker.name == "skip":
            _skip_reasons[item.nodeid] = marker.kwargs.get("reason", "")
            break

    for marker in item.parent.own_markers:
        if marker.name == "skipif":
            if all(marker.args):
                _skip_reasons[item.nodeid] = marker.kwargs.get("reason", "")
        elif marker.name == "skip":
            if len(marker.args):  # if un-named arguments are present, the first one is the reason
                _skip_reasons[item.nodeid] = marker.args[0]
            else:  #  otherwise, search in named arguments
                _skip_reasons[item.nodeid] = marker.kwargs.get("reason", "")

            break


def pytest_runtestloop(session):

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

    interfaces.library.wait(timeout=80 if context.library == "java" else 40)
    interfaces.library_stdout.wait()
    interfaces.library_dotnet_managed.wait()

    if (
        not interfaces.library_stdout.is_success
        or not interfaces.library.is_success
        or not interfaces.library_dotnet_managed.is_success
    ):
        session.shouldfail = "Library's interface is not validated"
        raise session.Failed(session.shouldfail)

    interfaces.agent.wait(timeout=40)
    if not interfaces.agent.is_success:
        session.shouldfail = "Agent's interface is not validated"
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

    if exitstatus != pytest.ExitCode.OK:
        validations = []

        for interface in interfaces.all:
            if interface.system_test_error is not None:
                terminalreporter.write_sep("=", f"INTERNAL ERROR ON SYSTEM TESTS", red=True, bold=True)
                terminalreporter.line("Traceback (most recent call last):", red=True)
                for line in traceback.format_tb(interface.system_test_error.__traceback__):
                    for subline in line.split("\n"):
                        if subline.strip():
                            terminalreporter.line(subline.replace('File "/app/', 'File "'), red=True)
                terminalreporter.line(str(interface.system_test_error), red=True)
                return

            validations += interface._validations

        failed = [v for v in validations if v.closed and not v.is_success]
        validated = [v for v in validations if v.closed and v.is_success]

        if len(failed) != 0:
            _print_async_failure_report(terminalreporter, failed, validated)


def pytest_sessionfinish(session, exitstatus):

    data_collector.shutdown()
    data_collector.join(timeout=10)

    # Is it really a test ?
    if data_collector.is_alive():
        logger.error("Can't terminate data collector")


def _print_async_failure_report(terminalreporter, failed, validated):
    """Given a list of validation, build a fancy report of source code that instanciate each validation object"""

    terminalreporter.line("")
    terminalreporter.write_sep("=", "ASYNC FAILURE" if len(failed) == 1 else "ASYNC FAILURES")

    # Create a tree filename > functions > fails
    files = collections.defaultdict(lambda: collections.defaultdict(list))
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
    terminalreporter.write_sep("=", "short async test summary info")

    for filename, functions in files.items():
        for function, fails in functions.items():
            filename, klass, function = fails[0].get_test_source_info()
            terminalreporter.line(f"FAILED {filename}::{klass}::{function} - {len(fails)} fails")

    msg = ", ".join(
        [
            terminalreporter._tw.markup(f"{len(failed)} failed", red=True, bold=True),
            terminalreporter._tw.markup(f"{len(validated)} passed", green=True, bold=True),
        ]
    )

    terminalreporter.write_sep("=", msg, fullwidth=terminalreporter._tw.fullwidth + 23, red=True)

    terminalreporter.line("")
