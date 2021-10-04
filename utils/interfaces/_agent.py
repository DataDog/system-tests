"""
This files will validate data flow between agent and backend
"""

import threading

from utils.interfaces._core import BaseValidation, InterfaceValidator
from utils.interfaces._schemas_validators import SchemaValidator


class AgentInterfaceValidator(InterfaceValidator):
    """Validate agent/backend interface"""

    def __init__(self):
        super().__init__("agent")

        self.ready = threading.Event()

    def append_data(self, data):
        data = super().append_data(data)

        self.ready.set()

        return data

    def assert_use_domain(self, domain):
        self.append_validation(_UseDomain(domain))

    def assert_schemas(self):
        self.append_validation(SchemaValidator("agent"))

    def assert_metric_existence(self, metric_name):
        self.append_validation(_MetricExistence(metric_name))


class _UseDomain(BaseValidation):
    is_success_on_expiry = True

    def __init__(self, domain):
        super().__init__()
        self.domain = domain

    def check(self, data):
        domain = data["host"][-len(self.domain) :]

        if domain != self.domain:
            self.set_failure(f"Message #{data['message_number']} uses host {domain} instead of {self.domain}")


class _MetricExistence(BaseValidation):
    path_filters = "/api/v0.2/traces"

    def __init__(self, metric_name):
        super().__init__()
        self.metric_name = metric_name

    def check(self, data):
        for trace in data["request"]["content"]["traces"]:
            for span in trace["spans"]:
                if "metrics" in span and self.metric_name in span["metrics"]:
                    self.set_status(True)
                    break
