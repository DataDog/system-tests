from .endtoend import EndToEndScenario

class ExternalProcessingScenario(EndToEndScenario):
    def __init__(self, name, description, ):
        super().__init__(name, description)

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
