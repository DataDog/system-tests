from .core import ScenarioGroup
from .endtoend import EndToEndScenario


class ProfilingScenario(EndToEndScenario):
    def __init__(self, name) -> None:
        super().__init__(
            name,
            library_interface_timeout=160,
            weblog_env={
                "DD_PROFILING_ENABLED": "true",
                "DD_PROFILING_UPLOAD_PERIOD": "10",
                "DD_PROFILING_START_DELAY": "1",
                # Used within Spring Boot native tests to test profiling without affecting tracing scenarios
                "USE_NATIVE_PROFILING": "presence",
                # Reduce noise
                "DD_INSTRUMENTATION_TELEMETRY_ENABLED": "false",
            },
            doc="Test profiling feature. Not included in default scenario because is quite slow",
            scenario_groups=[ScenarioGroup.PROFILING],
            require_api_key=True,  # for an unknown reason, /flush on nodejs takes days with a fake key on this scenario
        )

    def configure(self, config):
        super().configure(config)

        library = self.weblog_container.image.env["SYSTEM_TESTS_LIBRARY"]
        if library == "dotnet":
            # https://docs.datadoghq.com/profiler/enabling/dotnet/?tab=linux#enabling-the-profiler
            self.weblog_container.environment["LD_PRELOAD"] = (
                "/opt/datadog/continuousprofiler/Datadog.Linux.ApiWrapper.x64.so"
            )
        elif library == "python":
            # https://ddtrace.readthedocs.io/en/stable/configuration.html#DD_PROFILING_STACK_V2_ENABLED
            # profiling is known to be unstable on python3.11, and this value is here to fix that
            # it's not yet the default behaviour, but it will be in the future
            self.weblog_container.environment["DD_PROFILING_STACK_V2_ENABLED"] = "true"
