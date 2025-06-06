from http import HTTPStatus
from time import time


# TODO: movethis test logic in test class
class _SeqIdLatencyValidation:
    """Verify that the messages seq_id s are sent somewhat in-order."""

    MAX_OUT_OF_ORDER_LAG = 0.1  # s

    def __init__(self):
        super().__init__()
        self.max_seq_id = 0
        self.received_max_time = None

    def __call__(self, data: dict):
        seq_id = data["request"]["content"]["seq_id"]
        now = time()
        if seq_id > self.max_seq_id:
            self.max_seq_id = seq_id
            self.received_max_time = now
        elif self.received_max_time is not None and (now - self.received_max_time) > self.MAX_OUT_OF_ORDER_LAG:
            raise ValueError(
                f"Received message with seq_id {seq_id} to far more than"
                f"100ms after message with seq_id {self.max_seq_id}"
            )


class _NoSkippedSeqId:
    """Verify that the messages seq_id s are sent somewhat in-order."""

    def __init__(self):
        super().__init__()
        self.seq_ids = []

    def __call__(self, data: dict):
        if HTTPStatus(data["response"]["status_code"]).is_success:
            seq_id = data["request"]["content"]["seq_id"]
            self.seq_ids.append((seq_id, data["log_filename"]))

    def final_check(self):
        self.seq_ids.sort()
        for i in range(len(self.seq_ids) - 1):
            diff = self.seq_ids[i + 1][0] - self.seq_ids[i][0]
            if diff == 0:
                raise ValueError(
                    f"Detected 2 telemetry messages with same seq_id {self.seq_ids[i + 1][1]} and {self.seq_ids[i][1]}"
                )

            if diff > 1:
                raise ValueError(
                    f"Detected non conscutive seq_ids between {self.seq_ids[i + 1][1]} and {self.seq_ids[i][1]}"
                )
