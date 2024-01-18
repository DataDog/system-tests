import enum
from typing import Literal
from typing import Tuple


# Remote Configuration apply status is used by clients to report the application status of a Remote Configuration
# record.
# UNKNOWN = 0
# UNACKNOWLEDGED = 1
# ACKNOWLEDGED = 2
# ERROR = 3
# RFC: https://docs.google.com/document/d/1bUVtEpXNTkIGvLxzkNYCxQzP2X9EK9HMBLHWXr_5KLM/
APPLY_STATUS = Literal[0, 1, 2, 3]


class Capabilities(enum.IntEnum):
    ASM_ACTIVATION = 1
    ASM_IP_BLOCKING = 2
    ASM_DD_RULES = 3
    ASM_EXCLUSIONS = 4
    ASM_REQUEST_BLOCKING = 5
    ASM_ASM_RESPONSE_BLOCKING = 6
    ASM_USER_BLOCKING = 7
    ASM_CUSTOM_RULES = 8
    ASM_CUSTOM_BLOCKING_RESPONSE = 9
    ASM_TRUSTED_IPS = 10
    ASM_API_SECURITY_SAMPLE_RATE = 11
    APM_TRACING_SAMPLE_RATE = 12
    APM_TRACING_LOGS_INJECTION = 13
    APM_TRACING_HTTP_HEADER_TAGS = 14
    APM_TRACING_CUSTOM_TAGS = 15


def human_readable_capabilities(caps: int) -> Tuple[str]:
    return tuple(c.name for c in Capabilities if caps >> c & 1)
