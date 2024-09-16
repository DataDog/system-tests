from enum import Enum
from logging import FileHandler
import os
from pathlib import Path
import shutil

import pytest
from utils.tools import logger, get_log_formatter


class ScenarioGroup(Enum):
    ALL = "all"
    APPSEC = "appsec"
    DEBUGGER = "debugger"
    END_TO_END = "end-to-end"
    GRAPHQL = "graphql"
    INTEGRATIONS = "integrations"
    LIB_INJECTION = "lib-injection"
    OPEN_TELEMETRY = "open-telemetry"
    PARAMETRIC = "parametric"
    PROFILING = "profiling"
    SAMPLING = "sampling"
    ONBOARDING = "onboarding"
    DOCKER_SSI = "docker-ssi"


VALID_GITHUB_WORKFLOWS = {
    None,
    "endtoend",
    "graphql",
    "libinjection",
    "opentelemetry",
    "parametric",
    "testthetest",
    "dockerssi",
}


class Scenario:
    def __init__(self, name, github_workflow, doc, scenario_groups=None) -> None:
        self.name = name
        self.replay = False
        self.doc = doc
        self.rc_api_enabled = False
        self.github_workflow = github_workflow
        self.scenario_groups = scenario_groups or []

        self.scenario_groups = list(set(self.scenario_groups))  # removes duplicates

        # if xdist is used, this property will be set to false for sub workers
        self.is_main_worker: bool = True

        assert (
            self.github_workflow in VALID_GITHUB_WORKFLOWS
        ), f"Invalid github_workflow {self.github_workflow} for {self.name}"

        for group in self.scenario_groups:
            assert group in ScenarioGroup, f"Invalid scenario group {group} for {self.name}: {group}"

    def _create_log_subfolder(self, subfolder, remove_if_exists=False):
        if self.replay:
            return

        path = os.path.join(self.host_log_folder, subfolder)

        if remove_if_exists:
            shutil.rmtree(path, ignore_errors=True)

        Path(path).mkdir(parents=True, exist_ok=True)

    def __call__(self, test_object):
        """handles @scenarios.scenario_name"""

        # Check that no scenario has been already declared
        for marker in getattr(test_object, "pytestmark", []):
            if marker.name == "scenario":
                raise ValueError(f"Error on {test_object}: You can declare only one scenario")

        pytest.mark.scenario(self.name)(test_object)

        return test_object

    def pytest_configure(self, config):
        self.replay = config.option.replay

        # https://github.com/pytest-dev/pytest-xdist/issues/271#issuecomment-826396320
        # we are in the main worker, not in a xdist sub-worker
        self.is_main_worker = not hasattr(config, "workerinput")

        if self.is_main_worker:
            # xdist use case: with xdist subworkers, this function is called
            # * at very first command
            # * then once per worker

            # the issue is that _create_log_subfolder() remove the folder if it exists, then create it. This scenario is then possible :
            # 1. some worker A creates logs/
            # 2. another worker B removes it
            # 3. worker A want to create logs/tests.log -> boom

            # to fix that, only the main worker can create the log folder

            self._create_log_subfolder("", remove_if_exists=True)

        handler = FileHandler(f"{self.host_log_folder}/tests.log", encoding="utf-8")
        handler.setFormatter(get_log_formatter())

        logger.addHandler(handler)

        self.configure(config)

    def pytest_sessionstart(self, session):
        """called at the very begining of the process"""

        logger.terminal.write_sep("=", "test context", bold=True)

        try:
            for warmup in self.get_warmups():
                logger.info(f"Executing warmup {warmup}")
                warmup()
        except:
            self.close_targets()
            raise

    def configure(self, config):
        ...

    def get_warmups(self):
        return [
            lambda: logger.stdout(f"Scenario: {self.name}"),
            lambda: logger.stdout(f"Logs folder: ./{self.host_log_folder}"),
        ]

    def post_setup(self):
        """called after test setup"""

    def close_targets(self):
        """called at the end of the process"""

    @property
    def host_log_folder(self):
        return "logs" if self.name == "DEFAULT" else f"logs_{self.name.lower()}"

    @property
    def components(self):
        return {}

    @property
    def parametrized_tests_metadata(self):
        return {}

    def get_junit_properties(self):
        return {"dd_tags[systest.suite.context.scenario]": self.name}

    def customize_feature_parity_dashboard(self, result):
        pass

    def __str__(self) -> str:
        return f"Scenario '{self.name}'"

    def is_part_of(self, declared_scenario):
        return self.name == declared_scenario
