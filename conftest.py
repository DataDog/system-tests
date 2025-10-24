# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

# keep this import at the top of the file
from utils.proxy import scrubber  # noqa: F401

from collections.abc import Sequence, Generator
import json
import os
from pathlib import Path
import time
import types
from typing import Any
import xml.etree.ElementTree as ET

import pytest
from _pytest.junitxml import xml_key
from pytest_jsonreport.plugin import JSONReport
from pluggy._result import _Result as Result

from manifests.parser.core import load as load_manifests
from utils import context
from utils.properties_serialization import SetupProperties
from utils._context._scenarios import scenarios, Scenario
from utils._context.component_version import ComponentVersion
from utils._decorators import released, configure as configure_decorators, parse_skip_declaration, add_pytest_marker
from utils._features import NOT_REPORTED_ID as NOT_REPORTED_FEATURE_ID
from utils._logger import logger
from utils.get_declaration import get_declarations

# Monkey patch JSON-report plugin to avoid noise in report
JSONReport.pytest_terminal_summary = lambda *args, **kwargs: None  # noqa: ARG005

# pytest does not keep a trace of deselected items, so we keep it in a global variable
_deselected_items: list[pytest.Item] = []
setup_properties = SetupProperties()


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--scenario", "-S", type=str, action="store", default="DEFAULT", help="Unique identifier of scenario"
    )
    parser.addoption("--replay", "-R", action="store_true", help="Replay tests based on logs")
    parser.addoption("--sleep", action="store_true", help="Startup scenario without launching the tests (keep running)")
    parser.addoption(
        "--force-execute", "-F", action="append", default=[], help="Item to execute, even if they are skipped"
    )
    parser.addoption("--scenario-report", action="store_true", help="Produce a report on nodeids and their scenario")
    parser.addoption(
        "--skip-empty-scenario",
        action="store_true",
        help="Skip scenario if it contains only tests marked as xfail or irrelevant",
    )

    parser.addoption("--force-dd-trace-debug", action="store_true", help="Set DD_TRACE_DEBUG to true")
    parser.addoption("--force-dd-iast-debug", action="store_true", help="Set DD_IAST_DEBUG_ENABLED to true")
    # k8s scenarios mandatory parameters
    parser.addoption("--k8s-provider", type=str, action="store", help="Set the k8s provider, like kind or minikube")
    parser.addoption("--k8s-weblog", type=str, action="store", help="Set weblog to deploy on k8s")
    parser.addoption("--k8s-library", type=str, action="store", help="Set language to test")
    parser.addoption(
        "--k8s-lib-init-img", type=str, action="store", help="Set tracers init image on the docker registry"
    )
    parser.addoption("--k8s-injector-img", type=str, action="store", help="Set injector image on the docker registry")
    parser.addoption("--k8s-weblog-img", type=str, action="store", help="Set test app image on the docker registry")
    parser.addoption(
        "--k8s-cluster-img", type=str, action="store", help="Set the datadog cluster image on the docker registry"
    )
    parser.addoption(
        "--k8s-ssi-registry-base",
        type=str,
        action="store",
        help="Set the default ssi registry base for the injection images (cluster agent, injector and library init)",
    )

    # Onboarding scenarios mandatory parameters
    parser.addoption("--vm-weblog", type=str, action="store", help="Set virtual machine weblog")
    parser.addoption("--vm-library", type=str, action="store", help="Set virtual machine library to test")
    parser.addoption("--vm-env", type=str, action="store", help="Set virtual machine environment")
    parser.addoption("--vm-provider", type=str, action="store", help="Set provider for VMs")
    parser.addoption("--vm-only", type=str, action="store", help="Filter to execute only one vm name")
    parser.addoption(
        "--vm-default-vms",
        type=str,
        action="store",
        help="True launch vms marked as default, False launch only no default vm. All launch all vms",
        default="True",
    )

    # Docker ssi scenarios
    parser.addoption("--ssi-weblog", type=str, action="store", help="Set docker ssi weblog")
    parser.addoption("--ssi-library", type=str, action="store", help="Set docker ssi library to test")
    parser.addoption("--ssi-base-image", type=str, action="store", help="Set docker ssi base image to build")
    parser.addoption("--ssi-arch", type=str, action="store", help="Set docker ssi archictecture of the base image")
    parser.addoption("--ssi-env", type=str, action="store", help="Prod or Dev (use ssi releases or snapshots)")
    parser.addoption("--ssi-library-version", type=str, action="store", help="Optional, use custom version of library")
    parser.addoption(
        "--ssi-injector-version", type=str, action="store", help="Optional, use custom version of injector"
    )
    parser.addoption(
        "--ssi-installable-runtime",
        type=str,
        action="store",
        help=(
            """Set the language runtime to install on the docker base image. """
            """Empty if we don't want to install any runtime"""
        ),
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
        choices=["cpp", "golang", "dotnet", "java", "nodejs", "php", "python", "ruby", "rust"],
    )
    parser.addoption(
        "--github-token-file",
        type=str,
        action="store",
        default="",
        help="An file containing a valid Github token to perform API calls",
    )

    # report data to feature parity dashboard
    parser.addoption(
        "--report-run-url", type=str, action="store", default=None, help="URI of the run who produced the report"
    )
    parser.addoption(
        "--report-environment", type=str, action="store", default=None, help="The environment the test is run under"
    )


def pytest_configure(config: pytest.Config) -> None:
    if not config.option.force_dd_trace_debug and os.environ.get("SYSTEM_TESTS_FORCE_DD_TRACE_DEBUG") == "true":
        config.option.force_dd_trace_debug = True

    if not config.option.force_dd_iast_debug and os.environ.get("SYSTEM_TESTS_FORCE_DD_IAST_DEBUG") == "true":
        config.option.force_dd_iast_debug = True

    # handle options that can be filled by environ
    if not config.option.report_environment and "SYSTEM_TESTS_REPORT_ENVIRONMENT" in os.environ:
        config.option.report_environment = os.environ["SYSTEM_TESTS_REPORT_ENVIRONMENT"]

    if not config.option.report_run_url and "SYSTEM_TESTS_REPORT_RUN_URL" in os.environ:
        config.option.report_run_url = os.environ["SYSTEM_TESTS_REPORT_RUN_URL"]

    if (
        not config.option.skip_empty_scenario
        and os.environ.get("SYSTEM_TESTS_SKIP_EMPTY_SCENARIO", "").lower() == "true"
    ):
        config.option.skip_empty_scenario = True

    if not config.option.force_execute and "SYSTEM_TESTS_FORCE_EXECUTE" in os.environ:
        config.option.force_execute = os.environ["SYSTEM_TESTS_FORCE_EXECUTE"].strip().split(",")

    # clean input
    config.option.force_execute = [item.strip() for item in config.option.force_execute if len(item.strip()) != 0]

    # First of all, we must get the current scenario

    current_scenario: Scenario | None = None

    for name in dir(scenarios):
        if name.upper() == config.option.scenario:
            current_scenario = getattr(scenarios, name)
            break

    if current_scenario is not None:
        current_scenario.pytest_configure(config)
        context.scenario = current_scenario
    else:
        pytest.exit(f"Scenario {config.option.scenario} does not exist", 1)

    if not config.option.replay and not config.option.collectonly:
        config.option.json_report_file = f"{context.scenario.host_log_folder}/report.json"
        config.option.xmlpath = f"{context.scenario.host_log_folder}/reportJunit.xml"

    configure_decorators(config)
    logger.info(f"Force execute: {config.option.force_execute}")


# Called at the very begening
def pytest_sessionstart(session: pytest.Session) -> None:
    # get the terminal to allow logging directly in stdout
    logger.terminal = session.config.pluginmanager.get_plugin("terminalreporter")

    # if only collect tests, do not start the scenario
    if not session.config.option.collectonly:
        context.scenario.pytest_sessionstart(session)

    # The canonical way o adding Junit properties to testsuite is not working with xdist
    # Workaround to tackle this issue
    # https://github.com/pytest-dev/pytest/issues/7767#issuecomment-698560400
    xml = session.config._store.get(xml_key, None)  # noqa: SLF001
    if xml:
        properties = context.scenario.get_junit_properties()
        for key, value in properties.items():
            xml.add_global_property(key, value or "")

    if session.config.option.sleep:
        logger.terminal.write("\n ********************************************************** \n")
        logger.terminal.write(" *** .:: Sleep mode activated. Press Ctrl+C to exit ::. *** ")
        logger.terminal.write("\n ********************************************************** \n\n")


# called when each test item is collected
def _collect_item_metadata(item: pytest.Item):
    declaration: str | None = None
    details: str | None = None

    for marker in reversed(list(item.iter_markers("declaration"))):
        declaration = marker.kwargs["declaration"]
        details = marker.kwargs["details"]

        if declaration == "irrelevant":
            # if any irrelevant declaration exists, it is the one we need to expose
            break

    if declaration is not None:
        logger.debug(f"{item.nodeid} => {declaration} => skipped")

    metadata = {
        "details": declaration if details is None else f"{declaration} ({details})",
        "testDeclaration": declaration,
        "features": [marker.kwargs["feature_id"] for marker in item.iter_markers("features")],
        "owners": list({marker.kwargs["owner"] for marker in item.iter_markers("owners")}),
    }

    # decorate test for junit
    item.user_properties.append(("test.codeowners", json.dumps(metadata["owners"])))

    # for feature_id in metadata["features"]:
    #     item.user_properties.append(("dd_tags[test.feature_id]", str(feature_id)))

    if declaration:
        item.user_properties.append(("dd_tags[systest.case.declaration]", declaration))

    if details:
        item.user_properties.append(("dd_tags[systest.case.declarationDetails]", details))

    return metadata

def pytest_collection_modifyitems(session: pytest.Session, config: pytest.Config, items: list[pytest.Item]) -> None:
    """Unselect items that are not included in the current scenario"""

    logger.debug("pytest_collection_modifyitems")

    selected = []
    deselected = []

    all_declared_scenarios = {}

    def iter_markers(self: pytest.Item, name: str | None = None):
        return (x[1] for x in self.iter_markers_with_node(name=name) if x[1].name not in ("skip", "skipif", "xfail"))

    must_pass_item_count = 0
    for item in items:
        # if the item has explicit scenario markers, we use them
        # otherwise we use markers declared on its parents
        own_markers = [marker for marker in item.own_markers if marker.name == "scenario"]
        scenario_markers = own_markers if len(own_markers) != 0 else list(item.iter_markers("scenario"))
        if len(scenario_markers) == 0:
            declared_scenarios = ["DEFAULT"]
        else:
            declared_scenarios = [marker.args[0] for marker in scenario_markers]

        all_declared_scenarios[item.nodeid] = declared_scenarios

        # If we are running scenario with the option sleep, we deselect all
        if session.config.option.sleep:
            deselected.append(item)
            continue

        if context.scenario.name in declared_scenarios:
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

            if _item_must_pass(item):
                must_pass_item_count += 1

        else:
            logger.debug(f"{item.nodeid} is not included in {context.scenario}")
            deselected.append(item)

    if must_pass_item_count == 0 and session.config.option.skip_empty_scenario:
        items[:] = []
        config.hook.pytest_deselected(items=items)
    else:
        items[:] = selected
        config.hook.pytest_deselected(items=deselected)

    if config.option.scenario_report:
        with open(f"{context.scenario.host_log_folder}/scenarios.json", "w", encoding="utf-8") as f:
            json.dump(all_declared_scenarios, f, indent=2)

    rules = get_declarations(context.library.name,
                               context.library.version,
                               context.weblog_variant,
                               context.agent_version,
                               context.dd_apm_inject_version,
                               context.k8s_cluster_agent_version)
    for item in items:
        for nodeid, declarations in rules.items():
            if nodeid in item.nodeid:
                for declaration in declarations:
                    add_pytest_marker(item, declaration[0], declaration[1])



def pytest_deselected(items: Sequence[pytest.Item]) -> None:
    _deselected_items.extend(items)


def _item_must_pass(item: pytest.Item) -> bool:
    """Returns True if the item must pass to be considered as a success"""

    if any(item.iter_markers("skip")):
        return False

    if any(item.iter_markers("xfail")):
        return False

    for marker in item.iter_markers("skipif"):  # noqa: SIM110 (it's more clear like that)
        if all(marker.args[0]):
            return False

    return True


def _item_is_skipped(item: pytest.Item):
    return any(item.iter_markers("skip"))


def pytest_collection_finish(session: pytest.Session) -> None:
    if session.config.option.collectonly:
        return

    if session.config.option.sleep:  # on this mode, we simply sleep, not running any test or setup
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:  # catching ctrl+C
            context.scenario.close_targets()
            return

    if session.config.option.replay:
        setup_properties.load(context.scenario.host_log_folder)

    last_item_file = ""
    for item in session.items:
        if _item_is_skipped(item):
            item.user_properties.append(("dd_tags[systest.case.outcome]", "skipped"))
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

    context.scenario.post_setup(session)

    print("\n=== Collected test functions and their marks ===")
    with open("./dump", "w") as f:
        for item in session.items:
            # Get all marks, including inherited ones (parametrize, class, etc.)
            marks = [m.name for m in item.iter_markers()]
            f.write(f"{item.nodeid} :: {', '.join(sorted(set(marks))) or 'no marks'}\n")

    # Stop after collection, before running tests
    # pytest.exit("Listed all test marks.", returncode=0)


def pytest_runtest_call(item: pytest.Item) -> None:
    # add a log line for each request made by the setup, to help debugging
    setup_properties.log_requests(item)


@pytest.hookimpl(hookwrapper=True)
def pytest_fixture_setup(
    fixturedef,  # noqa: ARG001, ANN001
    request: pytest.FixtureRequest,
) -> Generator[None, Any, None]:
    try:
        (yield).get_result()
    except BaseException:
        xfails = [*request.node.iter_markers("xfail")]
        outcome = "xfailed" if len(xfails) != 0 else "error"

        request.node.user_properties.append(("dd_tags[systest.case.outcome]", outcome))


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo) -> Generator[None, Result, None]:  # noqa: ARG001
    # Run all other hooks to get the report object
    outcome = yield
    rep: pytest.TestReport = outcome.get_result()

    if rep.when == "call":  # only attach outcome after test call
        # rep.outcome is one of: passed, failed, skipped
        # but json_report also distinguishes xfailed/xpassed
        # via rep.wasxfail and outcome
        value = rep.outcome
        if getattr(rep, "wasxfail", None):
            if rep.outcome == "skipped":
                value = "xfailed"
            elif rep.outcome == "passed":
                value = "xpassed"

        item.user_properties.append(("dd_tags[systest.case.outcome]", value))


@pytest.hookimpl(optionalhook=True)
def pytest_json_runtest_metadata(item: pytest.Item, call: pytest.CallInfo) -> None | dict:
    if call.when != "setup":
        return {}

    return _collect_item_metadata(item)


def pytest_json_modifyreport(json_report: dict) -> None:
    try:
        # add usefull data for reporting
        json_report["context"] = context.serialize()

        logger.debug("Modifying JSON report finished")

    except:
        logger.error("Fail to modify json report", exc_info=True)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    logger.info("Executing pytest_sessionfinish")

    if session.config.option.skip_empty_scenario and exitstatus == pytest.ExitCode.NO_TESTS_COLLECTED:
        exitstatus = pytest.ExitCode.OK
        session.exitstatus = pytest.ExitCode.OK

    if session.config.option.collectonly or session.config.option.replay:
        return

    context.scenario.pytest_sessionfinish(session, exitstatus)

    # xdist: pytest_sessionfinish function runs at the end of all tests. If you check for the worker input attribute,
    # it will run in the master thread after all other processes have finished testing
    if context.scenario.is_main_worker:
        with open(f"{context.scenario.host_log_folder}/known_versions.json", "w", encoding="utf-8") as f:
            json.dump(
                {library: sorted(versions) for library, versions in ComponentVersion.known_versions.items()},
                f,
                indent=2,
            )

        if session.config.option.xmlpath:
            # Test optimization needs to have the full name in name attribute
            junit_report = ET.parse(session.config.option.xmlpath)  # noqa: S314

            for testcase in junit_report.iter("testcase"):
                if "classname" in testcase.attrib:
                    testcase.attrib["name"] = testcase.attrib["classname"] + "." + testcase.attrib["name"]
                    del testcase.attrib["classname"]

                if context.weblog_variant:
                    name = testcase.attrib["name"]
                    if name.endswith("]"):
                        testcase.attrib["name"] = f"{name[:-1]}, {context.weblog_variant}]"
                    else:
                        testcase.attrib["name"] = f"{name}[{context.weblog_variant}]"

            junit_report.write(session.config.option.xmlpath)

        try:
            data = session.config._json_report.report  # noqa: SLF001
            export_feature_parity_dashboard(session, data)
        except Exception:
            logger.exception("Fail to export reports", exc_info=True)


def export_feature_parity_dashboard(session: pytest.Session, data: dict) -> None:
    tests = [convert_test_to_feature_parity_model(test) for test in data["tests"]]

    result = {
        "runUrl": session.config.option.report_run_url or "https://github.com/DataDog/system-tests",
        "runDate": data["created"],
        "environment": session.config.option.report_environment or "local",
        "testSource": "systemtests",
        "language": context.library.name,
        "variant": context.weblog_variant,
        "testedDependencies": [
            {"name": name, "version": str(version)} for name, version in context.scenario.components.items()
        ],
        "configuration": context.configuration,
        "scenario": context.scenario.name,
        "tests": [test for test in tests if test is not None],
    }
    context.scenario.customize_feature_parity_dashboard(result)
    with open(f"{context.scenario.host_log_folder}/feature_parity.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2)


def convert_test_to_feature_parity_model(test: dict) -> dict | None:
    result = {
        "path": test["nodeid"],
        "lineNumber": test["lineno"],
        "outcome": test["outcome"],
        "testDeclaration": test["metadata"]["testDeclaration"],
        "details": test["metadata"]["details"],
        "features": [feature for feature in test["metadata"]["features"] if feature != NOT_REPORTED_FEATURE_ID],
    }

    # exclude test without a feature (they may have been flagged as not reported)
    return result if len(result["features"]) != 0 else None


## Fixtures corners
@pytest.fixture(scope="session", name="session")
def fixture_session(request: pytest.FixtureRequest) -> pytest.Session:
    return request.session


@pytest.fixture(scope="session", name="deselected_items")
def fixture_deselected_items() -> list[pytest.Item]:
    return _deselected_items
