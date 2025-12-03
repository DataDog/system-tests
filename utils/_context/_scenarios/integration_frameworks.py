from collections.abc import Generator
import contextlib
import os

import pytest

from utils.docker_fixtures import (
    FrameworkTestClientFactory,
    TestAgentAPI,
    FrameworkTestClientApi,
    compute_volumes,
)
from utils._logger import logger
from utils._context.component_version import ComponentVersion
from utils._context.docker import get_docker_client
from ._docker_fixtures import DockerFixturesScenario


class IntegrationFrameworksScenario(DockerFixturesScenario):
    _test_client_factory: FrameworkTestClientFactory
    _required_cassette_generation_api_keys: list[str] = ["OPENAI_API_KEY", "ANTHROPIC_API_KEY"]

    def __init__(
        self,
        name: str,
        doc: str,
    ) -> None:
        super().__init__(
            name,
            doc=doc,
            github_workflow="endtoend",
            agent_image="ghcr.io/datadog/dd-apm-test-agent/ddapm-test-agent:v1.38.0",
        )

        self.environment: dict[str, str] = {}

    def configure(self, config: pytest.Config):
        library: str = config.option.library
        weblog: str = config.option.weblog
        generate_cassettes: bool = config.option.generate_cassettes

        if not library:
            pytest.exit("No library specified, please set -L option", 1)

        if not weblog:
            pytest.exit("No framework specified, please set -W option", 1)

        # TODO: can we turn the dockerfiles into base dockerfiles and just set a couple variables per framework?
        if "@" not in weblog:
            pytest.exit(
                f"No version specified for {weblog}, please use the format {weblog}@<version>.\n"
                f"To use the latest version, use the format {weblog}@latest.\n"
                "Example: openai-py@2.0.0 or openai-js@latest",
                1,
            )

        self.weblog_variant = weblog

        framework, framework_version = weblog.split("@", 1)

        if config.option.force_dd_trace_debug:
            self.environment["DD_TRACE_DEBUG"] = "true"

        self._check_and_set_api_keys(generate_cassettes=generate_cassettes)

        # Handle weblog language name suffix needed for weblog definitions
        # e.g., "openai-py" -> "openai", "openai-js" -> "openai"
        framework_dir = framework.rsplit("-", 1)[0] if "-" in framework else framework

        self._set_dd_trace_integrations_enabled(library)

        # Setup container volumes with app code
        container_volumes = {f"./utils/build/docker/{library}/{framework_dir}_app": "/app/integration_frameworks"}

        # Add nodejs-load-from-local volume support if needed
        if library == "nodejs":
            container_volumes.update(self.get_node_volumes())

        self._test_client_factory = FrameworkTestClientFactory(
            library=library,
            framework=framework,
            framework_version=framework_version,
            container_env=self.environment,
            container_volumes=container_volumes,
        )

        self._test_agent_factory.configure(self.host_log_folder)
        self._test_client_factory.configure(self.host_log_folder)

        if self.is_main_worker:
            # Build the framework test server image
            self._test_client_factory.build(github_token_file=config.option.github_token_file)
            self._test_agent_factory.pull()
            self._clean()

        # Extract library version from built container
        output = get_docker_client().containers.run(
            self._test_client_factory.tag,
            remove=True,
            command=["./system_tests_library_version.sh"],
            volumes=compute_volumes(self._test_client_factory.container_volumes),
        )

        self._library = ComponentVersion(library, output.decode("utf-8"))
        logger.debug(f"Library: {library}, Framework: {framework}=={framework_version}, Version: {self._library}")

        self.warmups.append(lambda: logger.stdout(f"Library: {self.library}"))

    def _check_and_set_api_keys(self, *, generate_cassettes: bool = False) -> None:
        if generate_cassettes:
            for key in self._required_cassette_generation_api_keys:
                api_key = os.getenv(key)
                if not api_key:
                    pytest.exit(f"{key} is required to generate cassettes", 1)
                self.environment[key] = api_key  # type: ignore[assignment]
        else:
            for key in self._required_cassette_generation_api_keys:
                self.environment[key] = "<not-a-real-key>"

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

    def _set_dd_trace_integrations_enabled(self, library: str) -> None:
        """Set environment variables to disable certain integrations based on the library."""
        if library == "python":
            self.environment["DD_PATCH_MODULES"] = "fastapi:false,starlette:false"
        elif library == "nodejs":
            self.environment["DD_TRACE_EXPRESS_ENABLED"] = "false"
            self.environment["DD_TRACE_HTTP_ENABLED"] = "false"
            self.environment["DD_TRACE_DNS_ENABLED"] = "false"
            self.environment["DD_TRACE_NET_ENABLED"] = "false"
            self.environment["DD_TRACE_FETCH_ENABLED"] = "false"
