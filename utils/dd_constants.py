from enum import IntEnum
from opentelemetry.trace import SpanKind  # noqa: F401
from opentelemetry.trace import StatusCode  # noqa: F401


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
    """https://docs.google.com/document/d/1bUVtEpXNTkIGvLxzkNYCxQzP2X9EK9HMBLHWXr_5KLM/edit#heading=h.vy1jegxy7cuc"""

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
    ASM_PROCESSOR_OVERRIDES = 16
    ASM_CUSTOM_DATA_SCANNERS = 17
    ASM_EXCLUSION_DATA = 18
    APM_TRACING_ENABLED = 19
    APM_TRACING_DATA_STREAMS_ENABLED = 20
    ASM_RASP_SQLI = 21
    ASM_RASP_LFI = 22
    ASM_RASP_SSRF = 23
    ASM_RASP_SHI = 24
    ASM_RASP_XXE = 25
    ASM_RASP_RCE = 26
    ASM_RASP_NOSQLI = 27
    ASM_RASP_XSS = 28
    APM_TRACING_SAMPLE_RULES = 29
    CSM_ACTIVATION = 30
    ASM_AUTO_USER_INSTRUM_MODE = 31
    ASM_ENDPOINT_FINGERPRINT = 32
    ASM_SESSION_FINGERPRINT = 33
    ASM_NETWORK_FINGERPRINT = 34
    ASM_HEADER_FINGERPRINT = 35
    ASM_TRUNCATION_RULES = 36
    ASM_RASP_CMDI = 37
    APM_TRACING_ENABLE_DYNAMIC_INSTRUMENTATION = 38
    APM_TRACING_ENABLE_EXCEPTION_REPLAY = 39
    APM_TRACING_ENABLE_CODE_ORIGIN = 40
    APM_TRACING_ENABLE_LIVE_DEBUGGING = 41
    ASM_DD_MULTICONFIG = 42
    ASM_TRACE_TAGGING_RULES = 43
    ASM_EXTENDED_DATA_COLLECTION = 44
    APM_TRACING_MULTICONFIG = 45


class SamplingPriority(IntEnum):
    AUTO_KEEP = 1
    USER_KEEP = 2

class SamplingMechanism(IntEnum):
    UNKNOWN = -1
    DEFAULT = 0
    AGENT_RATE = 1
    REMOTE_RATE = 2
    RULE_RATE = 3
    MANUAL = 4
    APPSEC = 5
    REMOTE_USER_RATE = 6
    SINGLE_SPAN = 8
    RESERVED_9 = 9
    RESERVED_10 = 10
    REMOTE_USER_RULE = 11
    REMOTE_DYNAMIC_RULE = 12

class SpanKind(IntEnum):
    UNSPECIFIED = 0
    INTERNAL = 1
    SERVER = 2
    CLIENT = 3
    PRODUCER = 4
    CONSUMER = 5

    #     // Unspecified. Do NOT use as default.
    # // Implementations MAY assume SpanKind to be INTERNAL when receiving UNSPECIFIED.
    # SPAN_KIND_UNSPECIFIED = 0;

    # // Indicates that the span represents an internal operation within an application,
    # // as opposed to an operations happening at the boundaries. Default value.
    # SPAN_KIND_INTERNAL = 1;

    # // Indicates that the span covers server-side handling of an RPC or other
    # // remote network request.
    # SPAN_KIND_SERVER = 2;

    # // Indicates that the span describes a request to some remote service.
    # SPAN_KIND_CLIENT = 3;

    # // Indicates that the span describes a producer sending a message to a broker.
    # // Unlike CLIENT and SERVER, there is often no direct critical path latency relationship
    # // between producer and consumer spans. A PRODUCER span ends when the message was accepted
    # // by the broker while the logical processing of the message might span a much longer time.
    # SPAN_KIND_PRODUCER = 4;

    # // Indicates that the span describes consumer receiving a message from a broker.
    # // Like the PRODUCER kind, there is often no direct critical path latency relationship
    # // between producer and consumer spans.
    # SPAN_KIND_CONSUMER = 5;