from collections.abc import Generator
import contextlib

import pytest
import requests


from utils.docker_fixtures._core import docker_run, get_host_port
from utils.docker_fixtures._test_agent import TestAgentAPI
from ._core import TestClientFactory, TestClientApi


class FrameworkTestClientFactory(TestClientFactory):
    """Abstracts the docker image/container that ship the tested tracer+framework.
    This class is responsible to:
    * build the image
    * expose a ready to call function that runs the container and returns the client that will be used in tests
    """

    def __init__(
        self,
        library: str,
        framework: str,
        framework_version: str,
        container_env: dict[str, str],
        container_volumes: dict[str, str],
    ):
        self.library = library
        self.framework = framework
        self.framework_version = framework_version
        super().__init__(
            library=library,
            dockerfile=f"utils/build/docker/{library}/{framework}.Dockerfile",
            build_args={"FRAMEWORK_VERSION": framework_version},
            tag=f"{library}-test-library-{framework}-{framework_version}",
            container_name=f"{library}-test-library-{framework}-{framework_version}",
            container_volumes=container_volumes,
            container_env=container_env,
        )

    @contextlib.contextmanager
    def get_client(
        self,
        request: pytest.FixtureRequest,
        worker_id: str,
        test_id: str,
        library_env: dict[str, str],
        test_agent: TestAgentAPI,
    ) -> Generator["FrameworkTestClientApi", None, None]:
        environment = dict(self.container_env)

        container_port: int = 8080
        host_port = get_host_port(worker_id, 4500)

        # TODO : we should not have to set those three values
        environment["DD_TRACE_AGENT_URL"] = f"http://{test_agent.container_name}:{test_agent.container_port}"
        environment["DD_AGENT_HOST"] = test_agent.container_name
        environment["DD_TRACE_AGENT_PORT"] = str(test_agent.container_port)
        environment["FRAMEWORK_TEST_CLIENT_SERVER_PORT"] = str(container_port)

        # overwrite env with the one provided by the test
        environment |= library_env

        with (
            self.get_client_log_file(request) as log_file,
            docker_run(
                image=self.tag,
                name=f"{self.container_name}-{test_id}",
                env=environment,
                volumes=self.container_volumes,
                network=test_agent.network,
                ports={f"{container_port}/tcp": host_port},
                log_file=log_file,
            ) as container,
        ):
            test_server_timeout = 60
            client = FrameworkTestClientApi(f"http://localhost:{host_port}", test_server_timeout, container)

            yield client

        request.node.add_report_section(
            "teardown", f"{self.library.capitalize()} Library Output", f"Log file:\n./{log_file.name}"
        )


class FrameworkTestClientApi(TestClientApi):
    """API to interact with the tracer+framework server running in a docker container for
    INTEGRATIONS_FRAMEWORK scenarios.
    """

    def request(
        self, method: str, url: str, body: dict | None = None, *, raise_for_status: bool = True
    ) -> requests.Response:
        resp = self._session.request(method, self._url(url), json=body)
        if raise_for_status:
            resp.raise_for_status()
        return resp
