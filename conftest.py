# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.
import json

import pytest
from pytest_jsonreport.plugin import JSONReport

from utils import context
from utils._context._scenarios import scenarios
from utils.tools import logger
from utils.scripts.junit_report import junit_modifyreport
from utils._context.library_version import LibraryVersion

# Monkey patch JSON-report plugin to avoid noise in report
JSONReport.pytest_terminal_summary = lambda *args, **kwargs: None


class ReportMetadata:
    def __init__(self):
        self._docs = {}
        self._skip_reasons = {}
        self._release_versions = {}
        self._coverages = {}
        self._rfcs = {}


reportMetadata = ReportMetadata()


def _JSON_REPORT_FILE():
    return f"{context.scenario.host_log_folder}/report.json"


def _XML_REPORT_FILE():
    return f"{context.scenario.host_log_folder}/reportJunit.xml"


def _JSON_METADATA_REPORT_FILE():
    return f"{context.scenario.host_log_folder}/report_metadata.json"


def pytest_addoption(parser):
    parser.addoption(
        "--scenario", "-S", type=str, action="store", default="DEFAULT", help="Unique identifier of scenario"
    )
    parser.addoption("--replay", "-R", action="store_true", help="Replay tests based on logs")
    parser.addoption(
        "--force-execute", "-F", action="append", default=[], help="Item to execute, even if they are skipped"
    )


def pytest_configure(config):

    # First of all, we must get the current scenario
    for name in dir(scenarios):
        if name.upper() == config.option.scenario:
            context.scenario = getattr(scenarios, name)
            break

    if context.scenario is None:
        pytest.exit(f"Scenario {config.option.scenario} does not exists", 1)

    # collect only : we collect tests. As now, it only works with replay mode
    # on collectonly mode, the configuration step is exactly the step on replay mode
    # so let's tell the scenario we are in replay mode
    context.scenario.configure(config.option.replay or config.option.collectonly)

    if not config.option.replay and not config.option.collectonly:
        config.option.json_report_file = _JSON_REPORT_FILE()
        config.option.xmlpath = _XML_REPORT_FILE()


# Called at the very begening
def pytest_sessionstart(session):

    if session.config.option.collectonly:
        return

    context.scenario.session_start(session)


# called when each test item is collected
def _collect_item_metadata(item):

    reportMetadata._docs[item.nodeid] = item.obj.__doc__
    reportMetadata._docs[item.parent.nodeid] = item.parent.obj.__doc__

    reportMetadata._release_versions[item.parent.nodeid] = getattr(item.parent.obj, "__released__", None)

    if hasattr(item.parent.obj, "__coverage__"):
        reportMetadata._coverages[item.parent.nodeid] = getattr(item.parent.obj, "__coverage__")

    if hasattr(item.parent.obj, "__rfc__"):
        reportMetadata._rfcs[item.parent.nodeid] = getattr(item.parent.obj, "__rfc__")
    if hasattr(item.obj, "__rfc__"):
        reportMetadata._rfcs[item.nodeid] = getattr(item.obj, "__rfc__")

    if hasattr(item.parent.parent, "obj"):
        reportMetadata._docs[item.parent.parent.nodeid] = item.parent.parent.obj.__doc__
    else:
        reportMetadata._docs[item.parent.parent.nodeid] = "Unexpected structure"

    markers = item.own_markers

    parent = item.parent
    while parent is not None:
        markers += parent.own_markers
        parent = parent.parent

    for marker in reversed(markers):
        skip_reason = _get_skip_reason_from_marker(marker)
        if skip_reason:
            logger.debug(f"{item.nodeid} => {skip_reason} => skipped")
            reportMetadata._skip_reasons[item.nodeid] = skip_reason
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

        for marker in item.parent.parent.own_markers:
            if marker.name == "scenario":
                return marker.args[0]

        return None

    selected = []
    deselected = []

    for item in items:
        declared_scenario = get_declared_scenario(item)

        if (
            declared_scenario == context.scenario.name
            or declared_scenario is None
            and context.scenario.name == "DEFAULT"
        ):
            logger.info(f"{item.nodeid} is included in {context.scenario}")
            selected.append(item)
            _collect_item_metadata(item)

            for forced in config.option.force_execute:
                if item.nodeid.startswith(forced):
                    logger.info(f"{item.nodeid} is normally skipped, but forced thanks to -F {forced}")
                    item.own_markers = [m for m in item.own_markers if m.name not in ("skip", "skipif")]

        else:
            logger.debug(f"{item.nodeid} is not included in {context.scenario}")
            deselected.append(item)

    items[:] = selected
    config.hook.pytest_deselected(items=deselected)


def _item_is_skipped(item):
    for marker in item.own_markers:
        if marker.name in ("skip",):
            return True

    for marker in item.parent.own_markers:
        if marker.name in ("skip",):
            return True

    return False


def pytest_collection_finish(session):
    from utils import weblog

    if session.config.option.collectonly:
        return

    terminal = session.config.pluginmanager.get_plugin("terminalreporter")

    last_file = ""
    for item in session.items:

        if _item_is_skipped(item):
            continue

        if not item.instance:  # item is a method bounded to a class
            continue

        # the test metohd name is like test_xxxx
        # we replace the test_ by setup_, and call it if it exists

        setup_method_name = f"setup_{item.name[5:]}"

        if not hasattr(item.instance, setup_method_name):
            continue

        if last_file != item.location[0]:
            if len(last_file) == 0:
                terminal.write_sep("-", "tests setup", bold=True)

            terminal.write(f"\n{item.location[0]} ")
            last_file = item.location[0]

        setup_method = getattr(item.instance, setup_method_name)
        logger.debug(f"Call {setup_method} for {item}")
        try:
            weblog.current_nodeid = item.nodeid
            setup_method()
            weblog.current_nodeid = None
        except Exception:
            logger.exception("Unexpected failure during setup method call")
            terminal.write("x", bold=True, red=True)
            context.scenario.close_targets()
            raise
        else:
            terminal.write(".", bold=True, green=True)
        finally:
            weblog.current_nodeid = None

    terminal.write("\n\n")

    context.scenario.post_setup()

    # Serialize metadata to json file to add later to report.json
    json.dump(
        reportMetadata.__dict__, open(_JSON_METADATA_REPORT_FILE(), "w", encoding="utf-8"), indent=2,
    )


def pytest_runtest_call(item):
    from utils import weblog

    if item.nodeid in weblog.responses:
        for response in weblog.responses[item.nodeid]:
            request = response["request"]
            if "method" in request:
                logger.info(f"weblog {request['method']} {request['url']} -> {response['status_code']}")
            else:
                logger.info("weblog GRPC request")


def pytest_json_modifyreport(json_report):

    try:
        logger.debug("Modifying JSON report")
        metadata = json.load(open(_JSON_METADATA_REPORT_FILE()))
        # populate and adjust some data
        for test in json_report["tests"]:
            test["skip_reason"] = metadata["_skip_reasons"].get(test["nodeid"])

        # add usefull data for reporting
        json_report["docs"] = metadata["_docs"]
        json_report["context"] = context.serialize()
        json_report["release_versions"] = metadata["_release_versions"]
        json_report["rfcs"] = metadata["_rfcs"]
        json_report["coverages"] = metadata["_coverages"]

        # clean useless and volumetric data
        json_report.pop("collectors", None)

        for test in json_report["tests"]:
            for k in ("setup", "call", "teardown", "keywords", "lineno"):
                if k in test:
                    del test[k]

        logger.debug("Modifying JSON report finished")
    except:
        logger.error("Fail to modify json report", exc_info=True)


def pytest_sessionfinish(session, exitstatus):

    context.scenario.pytest_sessionfinish(session)
    if session.config.option.collectonly or session.config.option.replay:
        return

    json.dump(
        {library: sorted(versions) for library, versions in LibraryVersion.known_versions.items()},
        open(f"{context.scenario.host_log_folder}/known_versions.json", "w", encoding="utf-8"),
        indent=2,
    )

    _pytest_junit_modifyreport()


def _pytest_junit_modifyreport():
    metadata = json.load(open(_JSON_METADATA_REPORT_FILE()))
    with open(_JSON_REPORT_FILE(), encoding="utf-8") as f:
        json_report = json.load(f)
        junit_modifyreport(
            json_report,
            _XML_REPORT_FILE(),
            metadata["_skip_reasons"],
            metadata["_docs"],
            metadata["_rfcs"],
            metadata["_coverages"],
            metadata["_release_versions"],
            junit_properties=context.scenario.get_junit_properties(),
        )
