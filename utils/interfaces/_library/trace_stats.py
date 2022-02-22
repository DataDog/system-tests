from utils.interfaces._core import BaseValidation


class _TraceStatsValid(BaseValidation):

    is_success_on_expiry = True
    path_filters = ["/v0.6/stats", "/v0.4/traces"]

    def __init__(self):
        super().__init__()
        self.traces = []
        self.stats = []
        self.expected_timeout = 160

    def check(self, data):
        if data["path"] == "/v0.4/traces":
            self.traces.append(data)

    def final_check(self):
        if len(self.traces) == 0:
            self.set_failure("Not expected")
            return

        self.set_status(True)
