from collections.abc import Generator
import contextlib
from typing import TextIO

from utils.parametric._library_client import APMLibrary, APMLibraryClient


from ._core import get_host_port, docker_run
from ._test_agent import TestAgentAPI
from ._test_client import TestClientFactory


class ParametricTestClientFactory(TestClientFactory):
    @contextlib.contextmanager
    def get_apm_library(
        self,
        worker_id: str,
        test_id: str,
        test_agent: TestAgentAPI,
        library_env: dict,
        library_extra_command_arguments: list[str],
        test_server_log_file: TextIO,
    ) -> Generator["APMLibrary", None, None]:
        host_port = get_host_port(worker_id, 4500)
        container_port = 8080

        env = {
            "DD_TRACE_DEBUG": "true",
            "DD_TRACE_AGENT_URL": f"http://{test_agent.container_name}:{test_agent.container_port}",
            "DD_AGENT_HOST": test_agent.container_name,
            "DD_TRACE_AGENT_PORT": str(test_agent.container_port),
            "APM_TEST_CLIENT_SERVER_PORT": str(container_port),
            "DD_TRACE_OTEL_ENABLED": "true",
        }

        for k, v in library_env.items():
            # Don't set env vars with a value of None
            if v is not None:
                env[k] = v
            elif k in env:
                del env[k]

        command = list(self.command)

        if len(library_extra_command_arguments) > 0:
            if self.library not in ("nodejs", "java", "php"):
                # TODO : all test server should call directly the target without using a sh script
                command += library_extra_command_arguments
            else:
                # temporary workaround for the test server to be able to run the command
                env["SYSTEM_TESTS_EXTRA_COMMAND_ARGUMENTS"] = " ".join(library_extra_command_arguments)

        with docker_run(
            image=self.tag,
            name=f"{self.container_name}-{test_id}",
            command=command,
            env=env,
            ports={f"{container_port}/tcp": host_port},
            volumes=self.container_volumes,
            log_file=test_server_log_file,
            network=test_agent.network,
        ) as container:
            test_server_timeout = 60

            client = APMLibraryClient(
                self.library,
                f"http://localhost:{host_port}",
                test_server_timeout,
                container,
            )

            tracer = APMLibrary(client, self.library)
            yield tracer
