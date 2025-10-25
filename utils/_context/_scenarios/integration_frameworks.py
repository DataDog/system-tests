from collections.abc import Generator
import contextlib

import pytest

from utils.docker_fixtures import (
    FrameworkTestClientFactory,
    TestAgentAPI,
    FrameworkTestClientApi,
)
from utils._logger import logger
from utils._context.component_version import ComponentVersion
from ._docker_fixtures import DockerFixturesScenario


class IntegrationFrameworksScenario(DockerFixturesScenario):
    _test_client_factory: FrameworkTestClientFactory

    def __init__(self, name: str, doc: str) -> None:
        super().__init__(
            name,
            doc=doc,
            github_workflow="endtoend",
            agent_image="ghcr.io/datadog/dd-apm-test-agent/ddapm-test-agent:v1.36.0",
        )

        self.environment = {
            "DD_TRACE_DEBUG": "true",
            "DD_TRACE_OTEL_ENABLED": "true",
        }

    def configure(self, config: pytest.Config):
        library: str = config.option.library
        weblog: str = config.option.weblog

        if not library:
            pytest.exit("No library specified, please set -L option", 1)

        if not weblog:
            pytest.exit("No framework specified, please set -W option", 1)

        if "@" not in weblog:
            pytest.exit("Weblog must be of the form : openai@2.0.0.", 1)

        framework, framework_version = weblog.split("@", 1)

        self._test_agent_factory.configure(self.host_log_folder)

        self._test_client_factory = FrameworkTestClientFactory(
            host_log_folder=self.host_log_folder,
            library=library,
            framework=framework,
            framework_version=framework_version,
            container_env=self.environment,
            container_volumes={f"./utils/build/docker/{library}/{framework}_app": "/app/integration_frameworks"},
        )

        # Set library version - for now use a placeholder, will be updated after building
        self._library = ComponentVersion(library, "0.0.0")
        logger.debug(f"Library: {library}, Framework: {framework}=={framework_version}")

        if self.is_main_worker:
            # Build the framework test server image
            self._test_client_factory.build(self.host_log_folder, github_token_file=config.option.github_token_file)
            self._test_agent_factory.pull()
            self._clean()

    @contextlib.contextmanager
    def get_client(
        self,
        request: pytest.FixtureRequest,
        worker_id: str,
        test_id: str,
        library_env: dict[str, str],
        test_agent: TestAgentAPI,
    ) -> Generator[FrameworkTestClientApi, None, None]:
        with self._test_client_factory.get_client(
            request=request,
            library_env=library_env,
            worker_id=worker_id,
            test_id=test_id,
            test_agent=test_agent,
        ) as client:
            yield client

    @property
    def library(self):
        return self._library
