from .endtoend import EndToEndScenario

class ExternalProcessingScenario(EndToEndScenario):
    def __init__(self, name, description, ):
        super().__init__(name, description)

        # start envoyproxy/emvoy
        # start dummy http app on weblog port
        # start system-tests proxy
        # start agent
        # start service extension
        #    with agent url threw system-tests proxy

        # need 
        #   ./build.sh golang -i weblog -w service-extension
