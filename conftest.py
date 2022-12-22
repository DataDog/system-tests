# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.
import os
import json

from pytest_jsonreport.plugin import JSONReport

from utils import context, data_collector, interfaces
from utils.tools import logger
from utils.scripts.junit_report import junit_modifyreport
from utils._context.library_version import LibraryVersion

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

        if context.uds_mode:
            print_info(f"UDS socket: {context.uds_socket}")

        print_info(f"Weblog variant: {context.weblog_variant}")
        print_info(f"Backend: {context.dd_site}")
        print_info(f"Scenario: {context.scenario}")

        # connect interface validators to data collector
        data_collector.proxy_callbacks["agent"].append(interfaces.agent.append_data)
        data_collector.proxy_callbacks["library"].append(interfaces.library.append_data)
        data_collector.start()


# called when each test item is collected
def _collect_item_metadata(item):

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
            logger.debug(f"{item.nodeid} => {skip_reason} => skipped")
            _skip_reasons[item.nodeid] = skip_reason
            break


def _get_skip_reason_from_marker(marker):
    if marker.name == "skipif":
        if all(marker.args):
            return marker.kwargs.get("reason", "")
    elif marker.name in ("skip", "xfail"):
        if len(marker.args):  # if un-named arguments are present, the first one is the reason
            return marker.args[0]

        # otherwise, search in named arguments
        return marker.kwargs.get("reason", "")

    return None


def pytest_collection_modifyitems(session, config, items):
    """unselect items that are not included in the current scenario"""

    def get_declared_scenario(item):
        for marker in item.own_markers:
            if marker.name == "scenario":
                return marker.args[0]

        for marker in item.parent.own_markers:
            if marker.name == "scenario":
                return marker.args[0]

        return None

    scenario = os.environ.get("SYSTEMTESTS_SCENARIO", "DEFAULT")

    if scenario == "CUSTOM":
        # user has specifed which test to run, do nothing
        return

    selected = []
    deselected = []

    for item in items:
        declared_scenario = get_declared_scenario(item)

        if declared_scenario == scenario or declared_scenario is None and scenario == "DEFAULT":
            logger.info(f"{item.nodeid} is included in scenario {scenario}")
            selected.append(item)
            _collect_item_metadata(item)
        else:
            logger.debug(f"{item.nodeid} is not included in scenario {scenario}")
            deselected.append(item)

    items[:] = selected
    config.hook.pytest_deselected(items=deselected)


def pytest_collection_finish(session):

    if session.config.option.collectonly:
        return

    terminal = session.config.pluginmanager.get_plugin("terminalreporter")

    terminal.write_line("Executing weblog warmup...")
    context.execute_warmups()

    last_file = ""
    for item in session.items:

        if item.instance:  # item is a method bounded to a class

            # the test metohd name is like test_xxxx
            # we replace the test_ by setup_, and call it if it exists

            setup_method_name = f"setup_{item.name[5:]}"

            if hasattr(item.instance, setup_method_name):

                if last_file != item.location[0]:
                    if len(last_file) == 0:
                        terminal.write_sep("-", "Tests setup", bold=True)

                    terminal.write(f"\n{item.location[0]} ")
                    last_file = item.location[0]

                setup_method = getattr(item.instance, setup_method_name)
                logger.debug(f"Call {setup_method} for {item}")
                try:
                    setup_method()
                except Exception:
                    logger.exception("Unexpected failure during setup method call")
                    terminal.write("x", bold=True, red=True)
                    raise
                else:
                    terminal.write(".", bold=True, green=True)

    terminal.write("\n\n")

    _wait_interface(interfaces.library, session)
    _wait_interface(interfaces.library_stdout, session)
    _wait_interface(interfaces.library_dotnet_managed, session)
    _wait_interface(interfaces.agent, session)
    _wait_interface(interfaces.backend, session)


def _wait_interface(interface, session):
    terminal = session.config.pluginmanager.get_plugin("terminalreporter")
    terminal.write_sep("-", f"Wait for {interface} ({interface.timeout}s)")
    terminal.flush()

    interface.wait()


def pytest_json_modifyreport(json_report):

    try:
        logger.debug("Modifying JSON report")

        # populate and adjust some data
        for test in json_report["tests"]:
            test["skip_reason"] = _skip_reasons.get(test["nodeid"])

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

    json.dump(
        {library: sorted(versions) for library, versions in LibraryVersion.known_versions.items()},
        open("logs/known_versions.json", "w", encoding="utf-8"),
        indent=2,
    )

    _pytest_junit_modifyreport()

    if "SYSTEMTESTS_SCENARIO" in os.environ:  # means the we are running test_the_test
        data_collector.shutdown()
        data_collector.join(timeout=10)

        # Is it really a test ?
        if data_collector.is_alive():
            logger.error("Can't terminate data collector")


def _pytest_junit_modifyreport():
    json_report_path = "logs/report.json"
    junit_report_path = "logs/reportJunit.xml"

    with open(json_report_path, encoding="utf-8") as f:
        json_report = json.load(f)
        junit_modifyreport(
            json_report,
            junit_report_path,
            _skip_reasons,
            _docs,
            _rfcs,
            _coverages,
            _release_versions,
        )
