from utils.interfaces._core import BaseValidation


class _HeartbeatValidation(BaseValidation):
    is_success_on_expiry = True
    TELEMETRY_INTAKE_ENDPOINT = "/api/v2/apmtelemetry"
    TELEMETRY_AGENT_ENDPOINT = "/telemetry/proxy/api/v2/apmtelemetry"

    def __init__(self, number, endpoint):
        super().__init__(path_filters=endpoint)
        self.number = number
        self.counter = 0

    def check(self, data):
        request = data["request"]
        type = request["content"]["request_type"]
        super().log_info(f"Heartbeat Validation: {request}")
        if type == "app-heartbeat":
            self.counter = self.counter+1
            super().log_info("Heartbeat Validation: Heartbeat comes at ")

    def final_check(self):
        assert self.number == self.counter