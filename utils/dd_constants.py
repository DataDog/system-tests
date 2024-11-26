from enum import IntEnum


# Key used in the metrics map to indicate tracer sampling priority
SAMPLING_PRIORITY_KEY = "_sampling_priority_v1"

"""
Key used in the metrics to map to single span sampling.
"""
SINGLE_SPAN_SAMPLING_MECHANISM = "_dd.span_sampling.mechanism"

"""
Value used in the metrics to map to single span sampling decision.
"""
SINGLE_SPAN_SAMPLING_MECHANISM_VALUE = 8

"""Key used in the metrics to map to single span sampling sample rate."""
SINGLE_SPAN_SAMPLING_RATE = "_dd.span_sampling.rule_rate"

"""Key used in the metrics to map to single span sampling max per second."""
SINGLE_SPAN_SAMPLING_MAX_PER_SEC = "_dd.span_sampling.max_per_second"


""" Some release identifiers """
PYTHON_RELEASE_PUBLIC_BETA = "1.4.0rc1.dev"
PYTHON_RELEASE_GA_1_1 = "1.5.0rc1.dev"


class RemoteConfigApplyState(IntEnum):
    """ https://docs.google.com/document/d/1bUVtEpXNTkIGvLxzkNYCxQzP2X9EK9HMBLHWXr_5KLM/edit#heading=h.vy1jegxy7cuc """

    UNKNOWN = 0
    UNACKNOWLEDGED = 1
    ACKNOWLEDGED = 2
    ERROR = 3


class Capabilities(IntEnum):
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
    APM_TRACING_ENABLED = 19
    ASM_RASP_SQLI = 21
    ASM_RASP_LFI = 22
    ASM_RASP_SSRF = 23
    ASM_RASP_SHI = 24
    APM_TRACING_SAMPLE_RULES = 29
    ASM_ENDPOINT_FINGERPRINT = 32
    ASM_SESSION_FINGERPRINT = 33
    ASM_NETWORK_FINGERPRINT = 34
    ASM_HEADER_FINGERPRINT = 35


class SpanKind(IntEnum):
    """Specifies additional details on how this span relates to its parent span.
    """

    #: Default value. Indicates that the span is used internally in the
    # application.
    INTERNAL = 1

    #: Indicates that the span describes an operation that handles a remote
    # request.
    SERVER = 2

    #: Indicates that the span describes a request to some remote service.
    CLIENT = 3

    #: Indicates that the span describes a producer sending a message to a
    #: broker. Unlike client and server, there is usually no direct critical
    #: path latency relationship between producer and consumer spans.
    PRODUCER = 4

    #: Indicates that the span describes a consumer receiving a message from a
    #: broker. Unlike client and server, there is usually no direct critical
    #: path latency relationship between producer and consumer spans.
    CONSUMER = 5


class StatusCode(IntEnum):
    """Represents the canonical set of status codes of a finished Span."""

    UNSET = 0
    """The default status."""

    OK = 1
    """The operation has been validated by an Application developer or Operator to have completed successfully."""

    ERROR = 2
    """The operation contains an error."""
