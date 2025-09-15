from logging import FileHandler
import os
from pathlib import Path
import shutil

import pytest
from utils._logger import logger, get_log_formatter


class ScenarioGroup:
    scenarios: list["Scenario"]
    name: str = ""

    def __init__(self) -> None:
        self.scenarios = []

    def __call__(self, test_object):  # noqa: ANN001 (tes_object can be a class or a class method)
        """Handles @scenario_groups.scenario_group_name"""

        for scenario in self.scenarios:
            scenario(test_object)

        return test_object


class _ScenarioGroups:
    all = ScenarioGroup()
    appsec = ScenarioGroup()
    appsec_rasp = ScenarioGroup()
    appsec_lambda = ScenarioGroup()
    debugger = ScenarioGroup()
    end_to_end = ScenarioGroup()
    exotics = ScenarioGroup()
    graphql = ScenarioGroup()
    integrations = ScenarioGroup()
    ipv6 = ScenarioGroup()
    lambda_end_to_end = ScenarioGroup()
    lib_injection = ScenarioGroup()
    lib_injection_profiling = ScenarioGroup()
    k8s_injector_dev = ScenarioGroup()
    open_telemetry = ScenarioGroup()
    profiling = ScenarioGroup()
    sampling = ScenarioGroup()
    onboarding = ScenarioGroup()
    simple_onboarding = ScenarioGroup()
    simple_onboarding_profiling = ScenarioGroup()
    simple_onboarding_appsec = ScenarioGroup()
    docker_ssi = ScenarioGroup()
    essentials = ScenarioGroup()
    external_processing = ScenarioGroup()
    remote_config = ScenarioGroup()
    telemetry = ScenarioGroup()
    tracing_config = ScenarioGroup()
    tracer_release = ScenarioGroup()

    def __getitem__(self, key: str) -> ScenarioGroup:
        key = key.replace("-", "_").lower()

        if not hasattr(self, key):
            names: list[str] = [name for name in dir(self) if not name.startswith("_")]
            names.sort()
            raise ValueError(f"Scenario group `{key}` does not exist. Valid values are:\n* {'\n* '.join(names)}")

        return getattr(self, key)


# populate names
for name, group in _ScenarioGroups.__dict__.items():
    if isinstance(group, ScenarioGroup):
        group.name = name

scenario_groups = _ScenarioGroups()

# safeguard to ensure that names are set
assert scenario_groups.all.name == "all", "Scenario group 'all' should be named 'all'"

VALID_CI_WORKFLOWS = {
    None,
    "endtoend",
    "libinjection",
    "k8s_injector_dev",
    "aws_ssi",
    "parametric",
    "testthetest",
    "dockerssi",
    "externalprocessing",
}


class Scenario:
    def __init__(
        self, name: str, github_workflow: str | None, doc: str, scenario_groups: list[ScenarioGroup] | None = None
    ) -> None:
        self.name = name
        self.replay = False
        self.doc = doc
        self.rc_api_enabled = False
        self.github_workflow = github_workflow  # TODO: rename this to workflow, as it may not be a github workflow
        self.scenario_groups = scenario_groups or []

        self.scenario_groups = list(set(self.scenario_groups))  # removes duplicates

        # key value pair of what is actually tested
        self.components: dict[str, str] = {}

        # if xdist is used, this property will be set to false for sub workers
        self.is_main_worker: bool = True

        assert (
            self.github_workflow in VALID_CI_WORKFLOWS
        ), f"Invalid github_workflow {self.github_workflow} for {self.name}"

        for group in self.scenario_groups:
            assert isinstance(group, ScenarioGroup), f"Invalid scenario group {group} for {self.name}"
            group.scenarios.append(self)

    def _create_log_subfolder(self, subfolder: str, *, remove_if_exists: bool = False):
        if self.replay:
            return

        path = os.path.join(self.host_log_folder, subfolder)

        if remove_if_exists:
            shutil.rmtree(path, ignore_errors=True)

        Path(path).mkdir(parents=True, exist_ok=True)

    def __call__(self, test_object):  # noqa: ANN001 (tes_object can be a class or a class method)
        """Handles @scenarios.scenario_name"""

        pytest.mark.scenario(self.name)(test_object)

        return test_object

    def pytest_configure(self, config: pytest.Config):
        self.replay = config.option.replay

        # https://github.com/pytest-dev/pytest-xdist/issues/271#issuecomment-826396320
        # we are in the main worker, not in a xdist sub-worker
        self.is_main_worker = not hasattr(config, "workerinput")

        if self.is_main_worker:
            # xdist use case: with xdist subworkers, this function is called
            # * at very first command
            # * then once per worker

            # the issue is that _create_log_subfolder() remove the folder if it exists, then create it.
            # This scenario is then possible :
            # 1. some worker A creates logs/
            # 2. another worker B removes it
            # 3. worker A want to create logs/tests.log -> boom

            # to fix that, only the main worker can create the log folder

            self._create_log_subfolder("", remove_if_exists=True)

        handler = FileHandler(f"{self.host_log_folder}/tests.log", encoding="utf-8")
        handler.setFormatter(get_log_formatter())

        logger.addHandler(handler)

        self.configure(config)

    def configure(self, config: pytest.Config): ...

    def pytest_sessionstart(self, session: pytest.Session):  # noqa: ARG002
        """Called at the very begining of the process"""

        logger.terminal.write_sep("=", "test context", bold=True)

        try:
            for warmup in self.get_warmups():
                logger.info(f"Executing warmup {warmup}")
                warmup()
        except:
            self.close_targets()
            raise

    def get_warmups(self):
        return [
            lambda: logger.stdout(f"Scenario: {self.name}"),
            lambda: logger.stdout(f"Logs folder: ./{self.host_log_folder}"),
        ]

    def post_setup(self, session: pytest.Session):
        """Called after test setup"""

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int):
        """Called at the end of the process"""

    def close_targets(self):  # TODO remove this method
        """Called at the end of the process"""

    @property
    def host_log_folder(self):
        return "logs" if self.name == "DEFAULT" else f"logs_{self.name.lower()}"

    @property
    def parametrized_tests_metadata(self):
        return {}

    def get_junit_properties(self):
        return {"dd_tags[systest.suite.context.scenario]": self.name}

    def customize_feature_parity_dashboard(self, result: dict):
        pass

    def __str__(self) -> str:
        return f"Scenario '{self.name}'"
