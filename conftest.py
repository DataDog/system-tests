# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.
import json
import os
import time
import types

import pytest
from pytest_jsonreport.plugin import JSONReport

from manifests.parser.core import load as load_manifests
from utils import context
from utils._context._scenarios import scenarios
from utils.tools import logger
from utils.scripts.junit_report import junit_modifyreport
from utils._context.library_version import LibraryVersion
from utils._decorators import released
from utils.properties_serialization import SetupProperties

# Monkey patch JSON-report plugin to avoid noise in report
JSONReport.pytest_terminal_summary = lambda *args, **kwargs: None

# pytest does not keep a trace of deselected items, so we keep it in a global variable
_deselected_items = []
setup_properties = SetupProperties()


def pytest_addoption(parser):
    parser.addoption(
        "--scenario", "-S", type=str, action="store", default="DEFAULT", help="Unique identifier of scenario"
    )
    parser.addoption("--replay", "-R", action="store_true", help="Replay tests based on logs")
    parser.addoption("--sleep", action="store_true", help="Startup scenario without launching the tests (keep running)")
    parser.addoption(
        "--force-execute", "-F", action="append", default=[], help="Item to execute, even if they are skipped"
    )
    parser.addoption("--scenario-report", action="store_true", help="Produce a report on nodeids and their scenario")

    # Onboarding scenarios mandatory parameters
    parser.addoption("--vm-weblog", type=str, action="store", help="Set virtual machine weblog")
    parser.addoption("--vm-library", type=str, action="store", help="Set virtual machine library to test")
    parser.addoption("--vm-env", type=str, action="store", help="Set virtual machine environment")
    parser.addoption("--vm-provider", type=str, action="store", help="Set provider for VMs")
    parser.addoption("--vm-only-branch", type=str, action="store", help="Filter to execute only one vm branch")
    parser.addoption("--vm-skip-branches", type=str, action="store", help="Filter exclude vm branches")

    # Docker ssi scenarios
    parser.addoption("--ssi-weblog", type=str, action="store", help="Set docker ssi weblog")
    parser.addoption("--ssi-library", type=str, action="store", help="Set docker ssi library to test")
    parser.addoption("--ssi-base-image", type=str, action="store", help="Set docker ssi base image to build")
    parser.addoption("--ssi-arch", type=str, action="store", help="Set docker ssi archictecture of the base image")
    parser.addoption(
        "--ssi-installable-runtime",
        type=str,
        action="store",
        help="Set the language runtime to install on the docker base image.Empty if we don't want to install any runtime",
    )
    parser.addoption("--ssi-push-base-images", "-P", action="store_true", help="Push docker ssi base images")
    parser.addoption("--ssi-force-build", "-B", action="store_true", help="Force build ssi base images")

    # Parametric scenario options
    parser.addoption(
        "--library",
        "-L",
        type=str,
        action="store",
        default="",
        help="Library to test (e.g. 'python', 'ruby')",
        choices=["cpp", "golang", "dotnet", "java", "nodejs", "php", "python", "ruby"],
    )

    # report data to feature parity dashboard
    parser.addoption(
        "--report-run-url", type=str, action="store", default=None, help="URI of the run who produced the report",
    )
    parser.addoption(
        "--report-environment", type=str, action="store", default=None, help="The environment the test is run under",
    )


def pytest_configure(config):

    # handle options that can be filled by environ
    if not config.option.report_environment and "SYSTEM_TESTS_REPORT_ENVIRONMENT" in os.environ:
        config.option.report_environment = os.environ["SYSTEM_TESTS_REPORT_ENVIRONMENT"]

    if not config.option.report_run_url and "SYSTEM_TESTS_REPORT_RUN_URL" in os.environ:
        config.option.report_run_url = os.environ["SYSTEM_TESTS_REPORT_RUN_URL"]

    # First of all, we must get the current scenario
    for name in dir(scenarios):
        if name.upper() == config.option.scenario:
            context.scenario = getattr(scenarios, name)
            break

    if context.scenario is None:
        pytest.exit(f"Scenario {config.option.scenario} does not exist", 1)

    context.scenario.pytest_configure(config)

    if not config.option.replay and not config.option.collectonly:
        config.option.json_report_file = f"{context.scenario.host_log_folder}/report.json"
        config.option.xmlpath = f"{context.scenario.host_log_folder}/reportJunit.xml"


# Called at the very begening
def pytest_sessionstart(session):

    # get the terminal to allow logging directly in stdout
    setattr(logger, "terminal", session.config.pluginmanager.get_plugin("terminalreporter"))

    # if only collect tests, do not start the scenario
    if not session.config.option.collectonly:
        context.scenario.pytest_sessionstart(session)

    if session.config.option.sleep:
        logger.terminal.write("\n ********************************************************** \n")
        logger.terminal.write(" *** .:: Sleep mode activated. Press Ctrl+C to exit ::. *** ")
        logger.terminal.write("\n ********************************************************** \n\n")


# called when each test item is collected
def _collect_item_metadata(item):

    result = {
        "details": None,
        "testDeclaration": None,
        "features": [marker.kwargs["feature_id"] for marker in item.iter_markers("features")],
    }

    # get the reason form skip before xfail
    markers = [*item.iter_markers("skip"), *item.iter_markers("skipif"), *item.iter_markers("xfail")]
    for marker in markers:
        skip_reason = _get_skip_reason_from_marker(marker)

        if skip_reason is not None:
            # if any irrelevant declaration exists, it is the one we need to expose
            if skip_reason.startswith("irrelevant"):
                result["details"] = skip_reason

            # otherwise, we keep the first one we found
            elif result["details"] is None:
                result["details"] = skip_reason

    if result["details"]:
        logger.debug(f"{item.nodeid} => {result['details']} => skipped")

        if result["details"].startswith("irrelevant"):
            result["testDeclaration"] = "irrelevant"
        elif result["details"].startswith("flaky"):
            result["testDeclaration"] = "flaky"
        elif result["details"].startswith("bug"):
            result["testDeclaration"] = "bug"
        elif result["details"].startswith("missing_feature"):
            result["testDeclaration"] = "notImplemented"
        else:
            raise ValueError(f"Unexpected test declaration for {item.nodeid} : {result['details']}")

    return result


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


def pytest_pycollect_makemodule(module_path, parent):

    # As now, declaration only works for tracers at module level

    library = context.scenario.library.library

    manifests = load_manifests()

    nodeid = str(module_path.relative_to(module_path.cwd()))

    if nodeid in manifests and library in manifests[nodeid]:
        declaration = manifests[nodeid][library]

        logger.info(f"Manifest declaration found for {nodeid}: {declaration}")

        mod: pytest.Module = pytest.Module.from_parent(parent, path=module_path)

        if declaration.startswith("irrelevant") or declaration.startswith("flaky"):
            mod.add_marker(pytest.mark.skip(reason=declaration))
            logger.debug(f"Module {nodeid} is skipped by manifest file because {declaration}")
        else:
            mod.add_marker(pytest.mark.xfail(reason=declaration))
            logger.debug(f"Module {nodeid} is xfailed by manifest file because {declaration}")

        return mod


@pytest.hookimpl(tryfirst=True)
def pytest_pycollect_makeitem(collector, name, obj):

    if collector.istestclass(obj, name):

        manifest = load_manifests()

        nodeid = f"{collector.nodeid}::{name}"

        if nodeid in manifest:
            declaration = manifest[nodeid]
            logger.info(f"Manifest declaration found for {nodeid}: {declaration}")

            released(**declaration)(obj)


def pytest_collection_modifyitems(session, config, items: list[pytest.Item]):
    """unselect items that are not included in the current scenario"""

    logger.debug("pytest_collection_modifyitems")

    selected = []
    deselected = []

    declared_scenarios = {}

    def iter_markers(self, name=None):
        return (x[1] for x in self.iter_markers_with_node(name=name) if x[1].name not in ("skip", "skipif", "xfail"))

    for item in items:
        scenario_markers = list(item.iter_markers("scenario"))
        declared_scenario = scenario_markers[0].args[0] if len(scenario_markers) != 0 else "DEFAULT"

        declared_scenarios[item.nodeid] = declared_scenario

        # If we are running scenario with the option sleep, we deselect all
        if session.config.option.sleep:
            deselected.append(item)
            continue

        if context.scenario.is_part_of(declared_scenario):
            logger.info(f"{item.nodeid} is included in {context.scenario}")
            selected.append(item)

            for forced in config.option.force_execute:
                if item.nodeid.startswith(forced):
                    logger.info(f"{item.nodeid} is normally skipped, but forced thanks to -F {forced}")
                    # when user specified a test to be forced, we need to run it if it is skipped/xfailed, but also
                    # if any of it's parent is marked as skipped/xfailed. The trick is to monkey path the
                    # iter_markers method (this method is used by pytest internally to get all markers of a test item,
                    # including parent's markers) to exclude the skip, skipif and xfail markers.
                    item.iter_markers = types.MethodType(iter_markers, item)

        else:
            logger.debug(f"{item.nodeid} is not included in {context.scenario}")
            deselected.append(item)
    items[:] = selected
    config.hook.pytest_deselected(items=deselected)

    if config.option.scenario_report:
        with open(f"{context.scenario.host_log_folder}/scenarios.json", "w", encoding="utf-8") as f:
            json.dump(declared_scenarios, f, indent=2)


def pytest_deselected(items):
    _deselected_items.extend(items)


def _item_is_skipped(item):
    return any(item.iter_markers("skip"))


def pytest_collection_finish(session: pytest.Session):

    if session.config.option.collectonly:
        return

    if session.config.option.sleep:  # on this mode, we simply sleep, not running any test or setup
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:  # catching ctrl+C
            context.scenario.close_targets()
            return
        except Exception as e:
            raise e

    if session.config.option.replay:
        setup_properties.load(context.scenario.host_log_folder)

    last_item_file = ""
    for item in session.items:

        if _item_is_skipped(item):
            continue

        if not item.instance:  # item is a method bounded to a class
            continue

        # the test method name is like test_xxxx
        # we replace the test_ by setup_, and call it if it exists

        setup_method_name = f"setup_{item.name[5:]}"

        if not hasattr(item.instance, setup_method_name):
            continue

        item_file = item.nodeid.split(":", 1)[0]
        if last_item_file != item_file:
            if len(last_item_file) == 0:
                logger.terminal.write_sep("-", "tests setup", bold=True)

            logger.terminal.write(f"\n{item_file} ")
            last_item_file = item_file

        setup_method = getattr(item.instance, setup_method_name)
        try:
            if session.config.option.replay:
                logger.debug(f"Restore properties of {setup_method} for {item}")
                setup_properties.restore_properties(item)
            else:
                logger.debug(f"Call {setup_method} for {item}")
                setup_method()
                setup_properties.store_properties(item)
        except Exception:
            logger.exception("Unexpected failure during setup method call")
            logger.terminal.write("x", bold=True, red=True)
            context.scenario.close_targets()
            raise
        else:
            logger.terminal.write(".", bold=True, green=True)

    logger.terminal.write("\n\n")

    if not session.config.option.replay:
        setup_properties.dump(context.scenario.host_log_folder)

    context.scenario.post_setup()


def pytest_runtest_call(item):
    # add a log line for each request made by the setup, to help debugging
    setup_properties.log_requests(item)


@pytest.hookimpl(optionalhook=True)
def pytest_json_runtest_metadata(item, call):

    if call.when != "setup":
        return {}

    return _collect_item_metadata(item)


def pytest_json_modifyreport(json_report):

    try:
        # add usefull data for reporting
        json_report["context"] = context.serialize()

        logger.debug("Modifying JSON report finished")

    except:
        logger.error("Fail to modify json report", exc_info=True)


def pytest_sessionfinish(session, exitstatus):

    logger.info("Executing pytest_sessionfinish")

    context.scenario.close_targets()

    if session.config.option.collectonly or session.config.option.replay:
        return

    # xdist: pytest_sessionfinish function runs at the end of all tests. If you check for the worker input attribute,
    # it will run in the master thread after all other processes have finished testing
    if context.scenario.is_main_worker:
        with open(f"{context.scenario.host_log_folder}/known_versions.json", "w", encoding="utf-8") as f:
            json.dump(
                {library: sorted(versions) for library, versions in LibraryVersion.known_versions.items()}, f, indent=2,
            )

        data = session.config._json_report.report  # pylint: disable=protected-access

        try:
            junit_modifyreport(
                data, session.config.option.xmlpath, junit_properties=context.scenario.get_junit_properties(),
            )

            export_feature_parity_dashboard(session, data)
        except Exception:
            logger.exception("Fail to export export reports", exc_info=True)


def export_feature_parity_dashboard(session, data):

    result = {
        "runUrl": session.config.option.report_run_url or "https://github.com/DataDog/system-tests",
        "runDate": data["created"],
        "environment": session.config.option.report_environment or "local",
        "testSource": "systemtests",
        "language": context.scenario.library.library,
        "variant": context.weblog_variant,
        "testedDependencies": [
            {"name": name, "version": str(version)} for name, version in context.scenario.components.items()
        ],
        "scenario": context.scenario.name,
        "tests": [convert_test_to_feature_parity_model(test) for test in data["tests"]],
    }
    context.scenario.customize_feature_parity_dashboard(result)
    with open(f"{context.scenario.host_log_folder}/feature_parity.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)


def convert_test_to_feature_parity_model(test):
    result = {
        "path": test["nodeid"],
        "lineNumber": test["lineno"],
        "outcome": test["outcome"],
        "testDeclaration": test["metadata"]["testDeclaration"],
        "details": test["metadata"]["details"],
        "features": test["metadata"]["features"],
    }

    return result


## Fixtures corners
@pytest.fixture(scope="session", name="session")
def fixture_session(request):
    return request.session


@pytest.fixture(scope="session", name="deselected_items")
def fixture_deselected_items():
    return _deselected_items
