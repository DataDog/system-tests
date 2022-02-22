from utils.interfaces._core import BaseValidation


class _TraceStatsValid(BaseValidation):

    is_success_on_expiry = True
    path_filters = ["/v0.6/stats", "/v0.4/traces"]

    def __init__(self):
        super().__init__()

    def check(self, data):
        print(data)
        self.set_failure("Testing")