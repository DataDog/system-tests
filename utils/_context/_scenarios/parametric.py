from collections.abc import Generator
import contextlib
import glob
import json
import os
from typing import Any

import pytest

from utils._context.component_version import ComponentVersion
from utils._context.docker import get_docker_client
from utils._logger import logger
from utils.docker_fixtures import (
    TestAgentAPI,
    compute_volumes,
    ParametricTestClientFactory,
    ParametricTestClientApi,
)

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
            agent_image="ghcr.io/datadog/dd-apm-test-agent/ddapm-test-agent:v1.39.0",
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
            "nodejs": self.get_node_volumes(),
            "php": {"./utils/build/docker/php/parametric/server.php": "/client/server.php"},
            "python": {"./utils/build/docker/python/parametric/apm_test_client": "/app/apm_test_client"},
        }

        # get tracer version info building and executing the ddtracer-version.docker file
        self._test_client_factory = ParametricTestClientFactory(
            library=library,
            dockerfile=f"utils/build/docker/{library}/parametric/Dockerfile",
            tag=f"{library}-test-client",
            container_name=f"{library}-test-client",
            container_volumes=volumes.get(library, {}),
            container_env={},
        )

        self._test_client_factory.configure(self.host_log_folder)
        self._test_agent_factory.configure(self.host_log_folder)

        if self.is_main_worker:
            # https://github.com/pytest-dev/pytest-xdist/issues/271#issuecomment-826396320
            # we are in the main worker, not in a xdist sub-worker
            # self._build_apm_test_server_image(config.option.github_token_file)
            self._test_agent_factory.pull()
            self._test_client_factory.build(github_token_file=config.option.github_token_file)
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

        if self.is_main_worker:
            self.warmups.append(lambda: logger.stdout(f"Library: {self.library}"))
        self.warmups.append(self._set_components)

    def _set_components(self):
        self.components["library"] = self.library.version
        self.components[self.library.name] = self.library.version

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
    ) -> Generator[ParametricTestClientApi, None, None]:
        with self._test_client_factory.get_apm_library(
            request=request,
            worker_id=worker_id,
            test_id=test_id,
            test_agent=test_agent,
            library_env=library_env,
            library_extra_command_arguments=library_extra_command_arguments,
        ) as result:
            yield result
