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
