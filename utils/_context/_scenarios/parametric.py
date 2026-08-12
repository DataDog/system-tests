from collections.abc import Generator
import contextlib
import glob
import json
import os
from pathlib import Path
from typing import Any

import pytest

from utils._context.component_version import ComponentVersion
from utils._context.constants import WeblogCategory
from utils._context.docker import get_docker_client
from utils._logger import logger
from utils.docker_fixtures import (
    TestAgentAPI,
    compute_volumes,
    ParametricTestClientFactory,
    ParametricTestClientApi,
)
from utils.docker_fixtures._test_agent import DEFAULT_OTLP_GRPC_PORT, DEFAULT_OTLP_HTTP_PORT
from utils.docker_fixtures._test_agent_pool import WorkerAgentPool
from utils.parametric.process import ProcessParametricTestClientFactory, ProcessTestAgentFactory

from ._docker_fixtures import DockerFixturesScenario


# Max timeout in seconds to keep a container running
default_subprocess_run_timeout = 300


class ParametricScenario(DockerFixturesScenario):
    _test_client_factory: Any
    _test_agent_factory: Any

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
            agent_image="ghcr.io/datadog/dd-apm-test-agent/ddapm-test-agent:v1.64.1",
            weblog_categories=[WeblogCategory.parametric],
        )
        self._parametric_tests_confs = ParametricScenario.PersistentParametricTestConf(self)

    def pytest_configure(self, config: pytest.Config) -> None:
        self._runtime = config.option.parametric_runtime
        super().pytest_configure(config)

    @property
    def host_log_folder(self) -> str:
        if getattr(self, "_runtime", "docker") == "process" and os.environ.get("TEST_UNDECLARED_OUTPUTS_DIR"):
            return str(Path(os.environ["TEST_UNDECLARED_OUTPUTS_DIR"]) / "system-tests")
        return super().host_log_folder

    @property
    def parametrized_tests_metadata(self):
        return self._parametric_tests_confs

    def configure(self, config: pytest.Config):
        if not config.option.library:
            pytest.exit("No library specified, please set -L option or use TEST_LIBRARY env var", 1)

        library: str = config.option.library

        if self._runtime == "process":
            self._configure_process(library)
            return

        volumes = {
            "golang": {"./utils/build/docker/golang/parametric": "/client"},
            "nodejs": self.get_node_volumes(),
            "php": {"./utils/build/docker/php/parametric/server.php": "/client/server.php"},
            "python": {"./utils/build/docker/python/parametric/apm_test_client": "/app/apm_test_client"},
        }

        env = {}

        if library == "python":
            python_env, python_volumes = self.get_python_env_and_volumes()
            env.update(python_env)
            volumes["python"].update(python_volumes)

        # get tracer version info building and executing the ddtracer-version.docker file
        self._test_client_factory = ParametricTestClientFactory(
            library=library,
            dockerfile=f"utils/build/docker/{library}/parametric/Dockerfile",
            tag=f"{library}-test-client",
            container_name=f"{library}-test-client",
            container_volumes=volumes.get(library, {}),
            container_env=env,
        )

        self._test_client_factory.configure(self.host_log_folder)
        self._test_agent_factory.configure(self.host_log_folder)

        if self.is_main_worker:
            # https://github.com/pytest-dev/pytest-xdist/issues/271#issuecomment-826396320
            # we are in the main worker, not in a xdist sub-worker
            # self._build_apm_test_server_image(config.option.github_token_file)
            self._test_agent_factory.pull()
            skip_build = getattr(config.option, "skip_parametric_build", False)
            if skip_build and len(get_docker_client().images.list(name=self._test_client_factory.tag)) > 0:
                logger.stdout(
                    "Skipping parametric build (image already exists, --skip-parametric-build or SKIP_PARAMETRIC_BUILD)"
                )
            else:
                self._test_client_factory.build(github_token_file=config.option.github_token_file)
            self._clean()

        # https://github.com/DataDog/system-tests/issues/2799
        # The version check container runs npm link (nodejs) or similar operations that
        # are not safe for concurrent execution on the same volume. Only the main worker
        # runs the container; sub-workers read the cached result from a file.
        version_cache = os.path.join(self.host_log_folder, "_library_version.txt")

        if self.is_main_worker:
            if library in ("nodejs", "python", "golang", "ruby", "dotnet", "rust"):
                output = get_docker_client().containers.run(
                    self._test_client_factory.tag,
                    remove=True,
                    command=["./system_tests_library_version.sh"],
                    volumes=compute_volumes(self._test_client_factory.container_volumes),
                    environment=self._test_client_factory.container_env,
                )
            else:
                output = get_docker_client().containers.run(
                    self._test_client_factory.tag,
                    remove=True,
                    command=["cat", "SYSTEM_TESTS_LIBRARY_VERSION"],
                )

            version_string = output.decode("utf-8")
            with open(version_cache, "w", encoding="utf-8") as f:
                f.write(version_string)
        else:
            with open(version_cache, encoding="utf-8") as f:
                version_string = f.read()

        self._library = ComponentVersion(library, version_string)
        logger.debug(f"Library version is {self._library}")

        if self.is_main_worker:
            self.warmups.append(lambda: logger.stdout(f"Library: {self.library}"))
        self.warmups.append(self._set_components)

    def _configure_process(self, library: str) -> None:
        if library != "golang":
            pytest.exit("The process parametric runtime currently supports only golang", 1)

        server = os.environ.get("SYSTEM_TESTS_GO_PARAMETRIC_SERVER")
        proot = os.environ.get("SYSTEM_TESTS_PROOT")
        test_agent = os.environ.get("SYSTEM_TESTS_TEST_AGENT_BIN")
        if not server or not proot or not test_agent:
            pytest.exit(
                "The process runtime requires SYSTEM_TESTS_GO_PARAMETRIC_SERVER, SYSTEM_TESTS_PROOT, "
                "and SYSTEM_TESTS_TEST_AGENT_BIN",
                1,
            )
        assert server is not None
        assert proot is not None
        assert test_agent is not None

        try:
            default_ports = (
                int(os.environ["SYSTEM_TESTS_TEST_AGENT_APM_PORT"]),
                int(os.environ["SYSTEM_TESTS_TEST_AGENT_OTLP_HTTP_PORT"]),
                int(os.environ["SYSTEM_TESTS_TEST_AGENT_OTLP_GRPC_PORT"]),
            )
        except (KeyError, ValueError):
            pytest.exit("rules_itest did not provide the default test-agent port mapping", 1)

        self._test_client_factory = ProcessParametricTestClientFactory(
            executable=Path(server),
            proot=Path(proot),
            library=library,
        )
        self._test_agent_factory = ProcessTestAgentFactory(
            executable=Path(test_agent),
            default_ports=default_ports,
        )
        self._test_client_factory.configure(self.host_log_folder)
        self._test_agent_factory.configure(self.host_log_folder)
        self._library = ComponentVersion(library, os.environ.get("SYSTEM_TESTS_GO_LIBRARY_VERSION", "v2.4.0"))
        if self.is_main_worker:
            self.warmups.append(lambda: logger.stdout(f"Library: {self.library}"))
        self.warmups.append(self._set_components)

    def get_agent_pool(self, worker_id: str) -> WorkerAgentPool:
        if getattr(self, "_runtime", "docker") == "docker":
            return super().get_agent_pool(worker_id)
        if self._agent_pool is None:

            @contextlib.contextmanager
            def _creator(
                request: pytest.FixtureRequest, agent_env: dict[str, str]
            ) -> Generator[TestAgentAPI, None, None]:
                del agent_env
                with self._test_agent_factory.default_agent(request) as api:
                    yield api

            self._agent_pool = WorkerAgentPool(_creator)
        return self._agent_pool

    @contextlib.contextmanager
    def get_test_agent_api(
        self,
        worker_id: str,
        request: pytest.FixtureRequest,
        test_id: str,
        agent_env: dict[str, str],
        container_otlp_http_port: int = DEFAULT_OTLP_HTTP_PORT,
        container_otlp_grpc_port: int = DEFAULT_OTLP_GRPC_PORT,
    ) -> Generator[TestAgentAPI, None, None]:
        if getattr(self, "_runtime", "docker") == "docker":
            with super().get_test_agent_api(
                worker_id=worker_id,
                request=request,
                test_id=test_id,
                agent_env=agent_env,
                container_otlp_http_port=container_otlp_http_port,
                container_otlp_grpc_port=container_otlp_grpc_port,
            ) as api:
                yield api
            return
        del worker_id, test_id
        with self._test_agent_factory.get_test_agent_api(
            request=request,
            agent_env=agent_env,
            container_otlp_http_port=container_otlp_http_port,
            container_otlp_grpc_port=container_otlp_grpc_port,
        ) as api:
            yield api

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
