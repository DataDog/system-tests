from typing import Any, Literal
from utils.dd_constants import Capabilities


# Remote Configuration apply status is used by clients to report the application status of a Remote Configuration
# record.
# UNKNOWN = 0
# UNACKNOWLEDGED = 1
# ACKNOWLEDGED = 2
# ERROR = 3
# RFC: https://docs.google.com/document/d/1bUVtEpXNTkIGvLxzkNYCxQzP2X9EK9HMBLHWXr_5KLM/
APPLY_STATUS = Literal[0, 1, 2, 3]


def human_readable_capabilities(caps: int) -> tuple[Any, ...]:
    return tuple(c.name for c in Capabilities if caps >> c & 1)
