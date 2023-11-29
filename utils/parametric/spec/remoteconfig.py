import enum
from typing import Literal


# Remote Configuration apply status is used by clients to report the application status of a Remote Configuration
# record.
# UNKNOWN = 0
# UNACKNOWLEDGED = 1
# ACKNOWLEDGED = 2
# ERROR = 3
# RFC: https://docs.google.com/document/d/1bUVtEpXNTkIGvLxzkNYCxQzP2X9EK9HMBLHWXr_5KLM/
APPLY_STATUS = Literal[0, 1, 2, 3]


class Capabilities(enum.IntFlag):
    ASM_ACTIVATION = 1 << 1
    ASM_IP_BLOCKING = 1 << 2
    ASM_DD_RULES = 1 << 3
    ASM_EXCLUSIONS = 1 << 4
    ASM_REQUEST_BLOCKING = 1 << 5
    ASM_ASM_RESPONSE_BLOCKING = 1 << 6
    ASM_USER_BLOCKING = 1 << 7
    ASM_CUSTOM_RULES = 1 << 8
    ASM_CUSTOM_BLOCKING_RESPONSE = 1 << 9
    ASM_TRUSTED_IPS = 1 << 10
    ASM_API_SECURITY_SAMPLE_RATE = 1 << 11
    APM_TRACING_SAMPLE_RATE = 1 << 12
    APM_TRACING_LOGS_INJECTION = 1 << 13
    APM_TRACING_HTTP_HEADER_TAGS = 1 << 14
    APM_TRACING_CUSTOM_TAGS = 1 << 15
