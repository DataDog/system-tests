from utils._context.containers import DummyServerContainer, ExternalProcessingContainer, EnvoyContainer
from .endtoend import DockerScenario, ScenarioGroup


class ExternalProcessingScenario(DockerScenario):
    def __init__(self, name):
        super().__init__(
            name,
            doc="Envoy + external processing",
            github_workflow="externalprocessing",
            scenario_groups=[ScenarioGroup.END_TO_END, ScenarioGroup.EXTERNAL_PROCESSING],
            use_proxy=True,
        )

        self._external_processing_container = ExternalProcessingContainer(self.host_log_folder)

        self._required_containers.append(self._external_processing_container)
        self._required_containers.append(EnvoyContainer(self.host_log_folder))
        self._required_containers.append(DummyServerContainer(self.host_log_folder))

        # start envoyproxy/envoy:v1.31-latest⁠
        # -> envoy.yaml configuration in tests/external_processing/envoy.yaml

        # start dummy http app on weblog port
        # -> server.py in tests/external_processing/server.py

        # start system-tests proxy
        # start agent
        # start service extension
        #    with agent url threw system-tests proxy

        # service extension image:
        # https://github.com/DataDog/dd-trace-go/pkgs/container/dd-trace-go%2Fservice-extensions-callout
        # Version:
        # tag: dev
        # base: latest/v*.*.*

    @property
    def weblog_variant(self):
        return "golang-dummy"

    @property
    def library(self):
        return self._external_processing_container.library
