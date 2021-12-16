from utils import context, BaseTestCase, interfaces
from utils.interfaces._core import BaseValidation
from utils.warmups import default_warmup

context.add_warmup(default_warmup)

TELEMETRY_AGENT_ENDPOINT = "/telemetry/proxy/api/v2/apmtelemetry"
TELEMETRY_INTAKE_ENDPOINT = "/api/v2/apmtelemetry"


class TelemetryRequestSuccessValidation(BaseValidation):
    is_success_on_expiry = True

    def __init__(self, path_filter):
        self.path_filters = path_filter
        super().__init__()

    def check(self, data):
        repsonse_code = data["response"]["status_code"]
        if not 200 <= repsonse_code < 300:
            self.set_failure(f"Got response code {repsonse_code} telemetry message {data['log_filename']}")


class SeqIdValidation(BaseValidation):
    path_filters = TELEMETRY_AGENT_ENDPOINT
    is_success_on_expiry = True

    def __init__(self, message=None, request=None):
        super().__init__(message=message, request=request)
        self.seq_id = 1

    def check(self, data):
        actual_seq_id = data["request"]["content"]["seq_id"]
        if actual_seq_id != self.seq_id:
            self.set_failure(f"Expected seq_id {self.seq_id} got {actual_seq_id}")
        self.seq_id += 1


class TelemetryProxyValidation(BaseValidation):
    class LibToAgent(BaseValidation):
        is_success_on_expiry = True
        path_filters = TELEMETRY_AGENT_ENDPOINT

        def __init__(self):
            super().__init__()
            self.library_messages = {}

        def check(self, data):
            seq_id = data["request"]["content"]["seq_id"]
            self.library_messages[seq_id] = data["request"]["content"]

        def final_check(self):
            return super().final_check()

    path_filters = TELEMETRY_INTAKE_ENDPOINT
    is_success_on_expiry = True

    def __init__(self, lib_to_agent):
        super().__init__()
        self.lib_to_agent = lib_to_agent
        self.agent_messages = {}

    def check(self, data):
        if not self.lib_to_agent._closed.is_set():
            seq_id = data["request"]["content"]["seq_id"]
            self.agent_messages[seq_id] = data["request"]["content"]

    def final_check(self):
        for seq_id, message in self.agent_messages.items():
            lib_message = self.lib_to_agent.library_messages.pop(seq_id, None)
            if lib_message is None:
                self.set_failure(f"Agent proxy forwarded message a that was not sent by the library:\n{message}")
                return
            if message != lib_message:
                self.set_failure(
                    f"Telemetry proxy message different\nlibrary -> agent got {lib_message}\nagent -> dd got {message}"
                )
                return

        if self.lib_to_agent.library_messages:
            self.set_failure("Some telemetry messages were not forwarded by the proxy endpoint")


class AppStartedLibraryValidation(BaseValidation):
    path_filters = TELEMETRY_AGENT_ENDPOINT

    def __init__(self, message=None, request=None):
        super().__init__(message=message, request=request)
        self.app_started_received = False

    def check(self, data):
        if data["request"]["content"]["request_type"] != "app-started":
            return
        if self.app_started_received:
            self.set_failure("Received telemetry message with app-started request-type multiple times")
        self.app_started_received = True

    def final_check(self):
        if not self.app_started_received:
            self.set_failure("Didn't send telemetry app-started message")
        else:
            self.set_status(True)


class Test_Telemetry(BaseTestCase):
    """Test that instrumentation telemetry is sent"""

    def test_schemas(self):
        """Test that telemetry messages have the correct schema"""
        interfaces.library.assert_schemas()
        interfaces.agent.assert_schemas()

    def test_status_ok(self):
        """Test that telemetry requests are successful"""
        interfaces.library.append_validation(TelemetryRequestSuccessValidation(TELEMETRY_AGENT_ENDPOINT))
        interfaces.library.append_validation(TelemetryRequestSuccessValidation(TELEMETRY_INTAKE_ENDPOINT))

    def test_seq_id(self):
        """Test that messages are sent sequentially"""
        interfaces.library.append_validation(SeqIdValidation())

    def test_app_started(self):
        """Request type app-started is sent on startup"""
        interfaces.library.append_validation(AppStartedLibraryValidation())

    def test_proxy_forwarding(self):
        """Test that the telemetry proxy forwards messages correctly"""
        lib_to_agent_messages = TelemetryProxyValidation.LibToAgent()
        interfaces.library.append_validation(lib_to_agent_messages)
        interfaces.agent.append_validation(TelemetryProxyValidation(lib_to_agent_messages))
