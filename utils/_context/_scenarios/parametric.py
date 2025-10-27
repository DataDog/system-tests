from collections.abc import Generator
import contextlib
import glob
import json
import os
from pathlib import Path
from typing import Any

import pytest

from utils._context.component_version import ComponentVersion
from utils._context.docker import get_docker_client
from utils._logger import logger
from utils.docker_fixtures import (
    TestAgentFactory,
    TestAgentAPI,
    compute_volumes,
    ParametricTestClientFactory,
)
from utils.parametric._library_client import APMLibrary

from .core import scenario_groups
from ._docker_fixtures import DockerFixturesScenario


# Max timeout in seconds to keep a container running
default_subprocess_run_timeout = 300


class ParametricScenario(DockerFixturesScenario):
    _test_client_factory: ParametricTestClientFactory

    class PersistentParametricTestConf(dict):
        """Parametric tests are executed in multiple thread, we need a mechanism to persist
        each parametrized_tests_metadata on a file
        """

        def __init__(self, outer_inst: "ParametricScenario"):
            self.outer_inst = outer_inst
            # To handle correctly we need to add data by default
            self.update({"scenario": outer_inst.name})

        def __setitem__(self, item: Any, value: Any):  # noqa: ANN401
            super().__setitem__(item, value)
            # Append to the context file
            ctx_filename = f"{self.outer_inst.host_log_folder}/{os.environ.get('PYTEST_XDIST_WORKER')}_context.json"
            with open(ctx_filename, "a") as f:
                json.dump({item: value}, f)
                f.write(",")
                f.write(os.linesep)

        def deserialize(self):
            result = {}
            for ctx_filename in glob.glob(f"{self.outer_inst.host_log_folder}/*_context.json"):
                with open(ctx_filename) as f:
                    file_content = f.read()
                    # Remove last carriage return and the last comma. Wrap into json array.
                    all_params = json.loads(f"[{file_content[:-2]}]")
                    # Change from array to unique dict
                    for d in all_params:
                        result.update(d)
            return result

    def __init__(self, name: str, doc: str) -> None:
        super().__init__(
            name,
            doc=doc,
            github_workflow="parametric",
            scenario_groups=[scenario_groups.all, scenario_groups.tracer_release, scenario_groups.parametric],
        )
        self._parametric_tests_confs = ParametricScenario.PersistentParametricTestConf(self)

    @property
    def parametrized_tests_metadata(self):
        return self._parametric_tests_confs

    def configure(self, config: pytest.Config):
        if not config.option.library:
            pytest.exit("No library specified, please set -L option or use TEST_LIBRARY env var", 1)

        library: str = config.option.library

        volumes = {
            "golang": {"./utils/build/docker/golang/parametric": "/client"},
            "nodejs": get_node_volumes(),
            "php": {"./utils/build/docker/php/parametric/server.php": "/client/server.php"},
            "python": {"./utils/build/docker/python/parametric/apm_test_client": "/app/apm_test_client"},
        }

        self._test_agent_factory = TestAgentFactory(self.host_log_folder)

        # get tracer version info building and executing the ddtracer-version.docker file
        self._test_client_factory = ParametricTestClientFactory(
            library=library,
            dockerfile=f"utils/build/docker/{library}/parametric/Dockerfile",
            tag=f"{library}-test-client",
            container_name=f"{library}-test-client",
            container_volumes=volumes.get(library, {}),
            container_env={},
        )

        if self.is_main_worker:
            # https://github.com/pytest-dev/pytest-xdist/issues/271#issuecomment-826396320
            # we are in the main worker, not in a xdist sub-worker
            # self._build_apm_test_server_image(config.option.github_token_file)
            self._test_agent_factory.pull()
            self._test_client_factory.build(
                host_log_folder=self.host_log_folder, github_token_file=config.option.github_token_file
            )
            self._clean()

        # https://github.com/DataDog/system-tests/issues/2799
        if library in ("nodejs", "python", "golang", "ruby", "dotnet", "rust"):
            output = get_docker_client().containers.run(
                self._test_client_factory.tag,
                remove=True,
                command=["./system_tests_library_version.sh"],
                volumes=compute_volumes(self._test_client_factory.container_volumes),
            )
        else:
            output = get_docker_client().containers.run(
                self._test_client_factory.tag,
                remove=True,
                command=["cat", "SYSTEM_TESTS_LIBRARY_VERSION"],
            )

        self._library = ComponentVersion(library, output.decode("utf-8"))
        logger.debug(f"Library version is {self._library}")

    def _set_components(self):
        self.components["library"] = self.library.version

    def get_warmups(self):
        result = super().get_warmups()
        result.append(lambda: logger.stdout(f"Library: {self.library}"))
        result.append(self._set_components)

        return result

    @property
    def library(self):
        return self._library

    @property
    def weblog_variant(self):
        return f"parametric-{self.library.name}"

    def get_junit_properties(self) -> dict[str, str]:
        result = super().get_junit_properties()

        result["dd_tags[systest.suite.context.library.name]"] = self.library.name
        result["dd_tags[systest.suite.context.library.version]"] = self.library.version
        result["dd_tags[systest.suite.context.weblog_variant]"] = self.weblog_variant

        return result

    @contextlib.contextmanager
    def get_apm_library(
        self,
        request: pytest.FixtureRequest,
        worker_id: str,
        test_id: str,
        test_agent: TestAgentAPI,
        library_env: dict,
        library_extra_command_arguments: list[str],
    ) -> Generator[APMLibrary, None, None]:
        log_path = f"{self.host_log_folder}/outputs/{request.cls.__name__}/{request.node.name}/server_log.log"
        Path(log_path).parent.mkdir(parents=True, exist_ok=True)

        with (
            open(log_path, "w+", encoding="utf-8") as log_file,
            self._test_client_factory.get_apm_library(
                worker_id=worker_id,
                test_id=test_id,
                test_agent=test_agent,
                library_env=library_env,
                library_extra_command_arguments=library_extra_command_arguments,
                test_server_log_file=log_file,
            ) as result,
        ):
            yield result

        request.node.add_report_section(
            "teardown", f"{self.library.name.capitalize()} Library Output", f"Log file:\n./{log_path}"
        )


def _get_base_directory() -> str:
    return str(Path.cwd())


def get_node_volumes() -> dict[str, str]:
    volumes = {}

    try:
        with open("./binaries/nodejs-load-from-local", encoding="utf-8") as f:
            path = f.read().strip(" \r\n")
            source = os.path.join(_get_base_directory(), path)
            volumes[str(Path(source).resolve())] = "/volumes/dd-trace-js"
    except FileNotFoundError:
        logger.info("No local dd-trace-js found, do not mount any volume")

    return volumes
