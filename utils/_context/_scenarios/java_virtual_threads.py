from ._core import EndToEndScenario


class JavaVirtualThreads(EndToEndScenario):
    """JDK 21 virtual threads with one carrier.

    The weblog is Spring Boot 3 on Tomcat. A request that does not finish means the tracer
    pinned or exhausted that carrier: the startup hang fixed in dd-trace-java 1.67.1
    (APMS-20734) and the still-open PendingTrace.write monitor (APMS-20446).
    """

    def __init__(self) -> None:
        super().__init__(
            "JAVA_VIRTUAL_THREADS",
            doc=(
                "Spring Boot 3 on JDK 21 with Tomcat virtual threads and a single carrier. "
                "A request that does not finish means the tracer pinned or exhausted that carrier."
            ),
            # No dd_trace category: only the weblog that lists this scenario runs here.
            # Every other Java weblog is JDK 11 and does not implement these endpoints.
            weblog_categories=[],
            appsec_enabled=False,
            iast_enabled=False,
            tracer_sampling_rate=1.0,
            weblog_env={
                "DD_TRACE_PARTIAL_FLUSH_ENABLED": "true",
                # Below the fan-out size, so PendingTrace.write runs while virtual threads still hold the trace.
                "DD_TRACE_PARTIAL_FLUSH_MIN_SPANS": "50",
            },
        )
