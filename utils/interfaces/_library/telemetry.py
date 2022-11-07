from time import time
from datetime import datetime, timedelta

from utils.interfaces._core import BaseValidation

TELEMETRY_AGENT_ENDPOINT = "/telemetry/proxy/api/v2/apmtelemetry"
TELEMETRY_INTAKE_ENDPOINT = "/api/v2/apmtelemetry"


# TODO: movethis test logic in test class
class _SeqIdLatencyValidation(BaseValidation):
    """Verify that the messages seq_id s are sent somewhat in-order."""

    MAX_OUT_OF_ORDER_LAG = 0.1  # s
    path_filters = TELEMETRY_AGENT_ENDPOINT
    is_success_on_expiry = True

    def __init__(self):
        super().__init__()
        self.max_seq_id = 0
        self.received_max_time = None

    def check(self, data):
        seq_id = data["request"]["content"]["seq_id"]
        now = time()
        if seq_id > self.max_seq_id:
            self.max_seq_id = seq_id
            self.received_max_time = now
        else:
            if self.received_max_time is not None and (now - self.received_max_time) > self.MAX_OUT_OF_ORDER_LAG:
                self.set_failure(
                    f"Received message with seq_id {seq_id} to far more than"
                    f"100ms after message with seq_id {self.max_seq_id}"
                )


class _NoSkippedSeqId(BaseValidation):
    """Verify that the messages seq_id s are sent somewhat in-order."""

    path_filters = TELEMETRY_AGENT_ENDPOINT
    is_success_on_expiry = True

    def __init__(self):
        super().__init__()
        self.seq_ids = []

    def check(self, data):
        if 200 <= data["response"]["status_code"] < 300:
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


class _AppHeartbeatValidation(BaseValidation):
    """Verify telemetry messages are sent every heartbeat interval."""

    path_filters = TELEMETRY_AGENT_ENDPOINT
    is_success_on_expiry = True

    def __init__(self):
        super().__init__()
        self.prev_message_time = -1
        self.TELEMETRY_HEARTBEAT_INTERVAL = 5  # Sync with scenario in run.sh
        self.ALLOWED_INTERVALS = 2
        self.fmt = "%Y-%m-%dT%H:%M:%S.%f"

    def check(self, data):
        curr_message_time = datetime.strptime(data["request"]["timestamp_start"], self.fmt)
        if self.prev_message_time != -1:
            delta = curr_message_time - self.prev_message_time
            if delta > timedelta(seconds=self.ALLOWED_INTERVALS * self.TELEMETRY_HEARTBEAT_INTERVAL):
                self.set_failure(
                    f"No heartbeat or message sent in {self.ALLOWED_INTERVALS} hearbeat intervals: {self.TELEMETRY_HEARTBEAT_INTERVAL}\nLast message was sent {str(delta)} seconds ago."
                )
        self.prev_message_time = curr_message_time
