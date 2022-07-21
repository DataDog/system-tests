import traceback
from time import time

from utils.interfaces._core import BaseValidation
from utils.tools import logger, m

TELEMETRY_AGENT_ENDPOINT = "/telemetry/proxy/api/v2/apmtelemetry"
TELEMETRY_INTAKE_ENDPOINT = "/api/v2/apmtelemetry"


class _TelemetryValidation(BaseValidation):
    """ will run an arbitrary check on telemetry data

        Validator function can :
        * returns true => validation will be validated at the end (but trace will continue to be checked)
        * returns False or None => nothing is done
        * raise an exception => validation will fail
    """

    def __init__(self, validator, is_success_on_expiry=False):
        super().__init__(path_filters=TELEMETRY_AGENT_ENDPOINT)
        self.validator = validator
        self.is_success_on_expiry = is_success_on_expiry

    def check(self, data):
        try:
            if self.validator(data):
                self.set_status(is_success=True)
        except Exception as e:
            logger.exception(f"{m(self.message)} not validated on {data['log_filename']}")
            msg = traceback.format_exception_only(type(e), e)[0]
            self.set_failure(f"{m(self.message)} not validated on {data['log_filename']}: {msg}")


class _SeqIdLatencyValidation(BaseValidation):
    """Verify that the messages seq_id s are sent somewhat in-order."""

    MAX_OUT_OF_ORDER_LAG = 0.1  # s
    path_filters = TELEMETRY_AGENT_ENDPOINT
    is_success_on_expiry = True

    def __init__(self, message=None, request=None):
        super().__init__(message=message, request=request)
        self.max_seq_id = 0
        self.received_max_time = None

    def check(self, data):
        seq_id = data["request"]["content"]["seq_id"]
        now = time()
        if seq_id > self.max_seq_id:
            self.max_seq_id = seq_id
            self.received_max_time = now
        else:
            if self.received_max_time is None:
                return
            elif (now - self.received_max_time) > self.MAX_OUT_OF_ORDER_LAG:
                self.set_failure(
                    f"Received message with seq_id {seq_id} to far more than"
                    f"100ms after message with seq_id {self.max_seq_id}"
                )


class _NoSkippedSeqId(BaseValidation):
    """Verify that the messages seq_id s are sent somewhat in-order."""

    path_filters = TELEMETRY_AGENT_ENDPOINT
    is_success_on_expiry = True

    def __init__(self, message=None, request=None):
        super().__init__(message=message, request=request)
        self.seq_ids = []

    def check(self, data):
        seq_id = data["request"]["content"]["seq_id"]
        self.seq_ids.append((seq_id, data["log_filename"]))

    def final_check(self):
        self.seq_ids.sort()
        for i in range(len(self.seq_ids) - 1):
            diff = self.seq_ids[i + 1][0] - self.seq_ids[i][0]
            if diff == 0:
                self.set_failure(
                    f"Detected 2 telemetry messages with same seq_id {self.seq_ids[i + 1][1]} and {self.seq_ids[i][1]}"
                )
            elif diff > 1:
                self.set_failure(
                    f"Detected non conscutive seq_ids between {self.seq_ids[i + 1][1]} and {self.seq_ids[i][1]}"
                )


class _TelemetryProxyValidation(BaseValidation):
    class LibToAgent(BaseValidation):
        is_success_on_expiry = True
        path_filters = TELEMETRY_AGENT_ENDPOINT

        def __init__(self):
            super().__init__()
            self.library_messages = {}

        def check(self, data):
            seq_id = data["request"]["content"]["seq_id"]
            runtime_id = data["request"]["content"]["runtime_id"]

            key = (seq_id, runtime_id)

            self.library_messages[key] = data

        def final_check(self):
            return super().final_check()

    path_filters = TELEMETRY_INTAKE_ENDPOINT
    is_success_on_expiry = True

    def __init__(self, lib_to_agent):
        super().__init__()
        self.lib_to_agent = lib_to_agent
        self.agent_messages = {}

    def check(self, data):
        seq_id = data["request"]["content"]["seq_id"]
        runtime_id = data["request"]["content"]["runtime_id"]

        key = (seq_id, runtime_id)

        self.agent_messages[key] = data

    def final_check(self):
        for key, agent_data in self.agent_messages.items():
            agent_message, agent_log_file = agent_data["request"]["content"], agent_data["log_filename"]

            if key not in self.lib_to_agent.library_messages:
                self.set_failure(f"Agent proxy forwarded a message that was not sent by the library:\n{agent_message}")
                return

            lib_data = self.lib_to_agent.library_messages.pop(key)
            lib_message, lib_log_file = lib_data["request"]["content"], lib_data["log_filename"]

            if agent_message != lib_message:
                self.set_failure(
                    f"Telemetry proxy message different\nlibrary -> agent got {lib_message}\nagent -> dd got {message}"
                    f"in messages {lib_log_file} and {agent_log_file}"
                )
                return

        if self.lib_to_agent.library_messages:
            self.set_failure(
                f"The following telemetry messages were not forwarded by the proxy endpoint\n"
                f"{' '.join((lm for _, lm in self.lib_to_agent.library_messages.values()))}"
            )
