"""Default Antithesis scenario - a minimal scenario that doesn't start any containers."""

from logging import FileHandler
import os
import pytest

from watchdog.observers.polling import PollingObserver
from watchdog.events import FileSystemEventHandler, FileSystemEvent

from utils import interfaces
from utils.interfaces._core import ProxyBasedInterfaceValidator
from utils._context.component_version import ComponentVersion
from utils._logger import logger, get_log_formatter
from .core import Scenario, scenario_groups


class DefaultAntithesisScenario(Scenario):
    """A minimal scenario that doesn't start containers.

    This scenario is designed for Antithesis testing where containers
    are managed externally and we only want to run the test logic.

    This scenario will run all tests that are decorated with @scenarios.default
    by checking for the "DEFAULT" scenario marker during test collection.
    """

    def __init__(self, name: str) -> None:
        super().__init__(
            name,
            github_workflow=None,
            doc="Antithesis scenario that doesn't start containers - for external container management",
            # Include DEFAULT scenario groups for tests using @scenario_groups decorators
            scenario_groups=[
                scenario_groups.essentials,
                scenario_groups.telemetry,
                scenario_groups.default,
                scenario_groups.default_antithesis,
            ],
        )
        self._library: ComponentVersion | None = None
        # List of scenario names whose tests should also run in this scenario
        self.include_scenarios_from = ["DEFAULT"]

        # Interface timeout properties (will be set based on library in configure)
        self.library_interface_timeout = 25  # Default timeout
        self.agent_interface_timeout = 5
        self.backend_interface_timeout = 0

        # Tests that are incompatible with Antithesis environment
        # These tests will be skipped when running in DEFAULT_ANTITHESIS scenario
        self.incompatible_tests = [
            "tests/test_data_integrity.py::Test_Agent::test_agent_do_not_drop_traces",
            "tests/test_semantic_conventions.py::Test_Meta::test_meta_component_tag",
            "tests/test_telemetry.py::Test_Telemetry::test_telemetry_proxy_enrichment",
            "tests/test_telemetry.py::Test_Telemetry::test_app_started_is_first_message",
            "tests/test_telemetry.py::Test_Telemetry::test_proxy_forwarding",
            "tests/appsec/iast/source/test_uri.py::TestURI::test_source_reported",
            "tests/appsec/iast/source/test_uri.py::TestURI::test_telemetry_metric_instrumented_source",
            "tests/appsec/iast/source/test_uri.py::TestURI::test_telemetry_metric_executed_source",
            "tests/appsec/rasp/test_cmdi.py::Test_Cmdi_Rules_Version::test_min_version",
            "tests/appsec/rasp/test_cmdi.py::Test_Cmdi_Waf_Version::test_min_version",
            "tests/appsec/rasp/test_lfi.py::Test_Lfi_Rules_Version::test_min_version",
            "tests/appsec/rasp/test_lfi.py::Test_Lfi_Waf_Version::test_min_version",
            "tests/appsec/rasp/test_shi.py::Test_Shi_Rules_Version::test_min_version",
            "tests/appsec/rasp/test_shi.py::Test_Shi_Waf_Version::test_min_version",
            "tests/appsec/rasp/test_sqli.py::Test_Sqli_Rules_Version::test_min_version",
            "tests/appsec/rasp/test_sqli.py::Test_Sqli_Waf_Version::test_min_version",
            "tests/appsec/rasp/test_ssrf.py::Test_Ssrf_Rules_Version::test_min_version",
            "tests/appsec/rasp/test_ssrf.py::Test_Ssrf_Waf_Version::test_min_version",
            "tests/appsec/waf/test_addresses.py::Test_UrlQuery::test_query_with_strict_regex",
            "tests/appsec/waf/test_reports.py::Test_Monitoring::test_waf_monitoring_once",
            "tests/appsec/waf/test_reports.py::Test_Monitoring::test_waf_monitoring_once_rfc1025",
        ]

    def pytest_configure(self, config: pytest.Config) -> None:
        """Configure the scenario but don't delete the logs folder if it exists."""
        # Store replay and worker status
        self.replay = config.option.replay
        self.is_main_worker = not hasattr(config, "workerinput")

        # Create log folder WITHOUT removing it if it exists
        if self.is_main_worker:
            self._create_log_subfolder("", remove_if_exists=False)

        # Set up logging handler
        handler = FileHandler(f"{self.host_log_folder}/tests.log", encoding="utf-8")
        handler.setFormatter(get_log_formatter())
        logger.addHandler(handler)

        # Call configure
        self.configure(config)

    def configure(self, config: pytest.Config) -> None:
        """Configure the scenario but don't start any containers."""
        # Get library information from command line or environment
        library_name = config.option.library or os.environ.get("DD_LANG", "")
        library_version = os.environ.get("DD_LIBRARY_VERSION", "unknown")

        if library_name:
            self._library = ComponentVersion(library_name, library_version)

        # Configure interfaces like in endtoend.py
        interfaces.agent.configure(self.host_log_folder, replay=self.replay)
        interfaces.library.configure(self.host_log_folder, replay=self.replay)
        interfaces.backend.configure(self.host_log_folder, replay=self.replay)
        interfaces.library_dotnet_managed.configure(self.host_log_folder, replay=self.replay)
        interfaces.library_stdout.configure(self.host_log_folder, replay=self.replay)
        interfaces.agent_stdout.configure(self.host_log_folder, replay=self.replay)

        # Set library-specific interface timeouts
        if library_name == "java":
            self.library_interface_timeout = 25
        elif library_name in ("golang",):
            self.library_interface_timeout = 10
        elif library_name in ("nodejs", "ruby"):
            self.library_interface_timeout = 0
        elif library_name in ("php",):
            # possibly something weird on obfuscator, let increase the delay for now
            self.library_interface_timeout = 10
        elif library_name in ("python",):
            self.library_interface_timeout = 5
        else:
            self.library_interface_timeout = 40

    @property
    def library(self) -> ComponentVersion:
        """Return the library component version."""
        if not self._library:
            library_name = os.environ.get("DD_LANG", "")
            library_version = os.environ.get("DD_LIBRARY_VERSION", "unknown")
            self._library = ComponentVersion(library_name, library_version)
        return self._library

    @property
    def host_log_folder(self) -> str:
        """Override to use 'logs' folder instead of 'logs_default_antithesis'."""
        return "logs"

    def start_interfaces_watchdog(self, interfaces_list: list[ProxyBasedInterfaceValidator]) -> None:
        """Start file system watchdog to automatically ingest interface files."""

        class Event(FileSystemEventHandler):
            def __init__(self, interface: ProxyBasedInterfaceValidator) -> None:
                super().__init__()
                self.interface = interface

            def _ingest(self, event: FileSystemEvent) -> None:
                if event.is_directory:
                    return

                self.interface.ingest_file(event.src_path)

            on_modified = _ingest
            on_created = _ingest

        # Using polling observer to avoid issues with OS-dependent notifiers
        observer = PollingObserver()

        for interface in interfaces_list:
            observer.schedule(Event(interface), path=interface.log_folder)

        observer.start()

    def _start_interfaces_watchdog(self) -> None:
        """Start the interfaces watchdog for library and agent interfaces."""
        self.start_interfaces_watchdog([interfaces.library, interfaces.agent])

    def get_warmups(self) -> list:
        """Return warmup list with interface watchdog."""
        warmups = super().get_warmups()

        if not self.replay:
            # Start the interfaces watchdog to automatically ingest files
            warmups.append(self._start_interfaces_watchdog)

        return warmups

    def post_setup(self, session: pytest.Session) -> None:  # noqa: ARG002
        """Wait for all interfaces to finish collecting messages after test setup."""
        if self.replay:
            logger.terminal.write_sep("-", "Load all data from logs")
            logger.terminal.flush()

            interfaces.library.load_data_from_logs()
            interfaces.library.check_deserialization_errors()

            interfaces.agent.load_data_from_logs()
            interfaces.agent.check_deserialization_errors()

            interfaces.backend.load_data_from_logs()
        else:
            # Wait for library interface to finish collecting traces
            self._wait_interface(interfaces.library, self.library_interface_timeout)
            interfaces.library.check_deserialization_errors()

            # Wait for agent interface to finish collecting traces
            self._wait_interface(interfaces.agent, self.agent_interface_timeout)
            interfaces.agent.check_deserialization_errors()

            # Wait for backend interface
            self._wait_interface(interfaces.backend, self.backend_interface_timeout)

        # Load .NET managed library data if applicable
        interfaces.library_dotnet_managed.load_data()

    def _wait_interface(self, interface: ProxyBasedInterfaceValidator, timeout: int) -> None:
        """Wait for an interface to finish collecting messages.

        Args:
            interface: The interface validator to wait for
            timeout: Timeout in seconds to wait for the interface

        """
        logger.terminal.write_sep("-", f"Wait for {interface} ({timeout}s)")
        logger.terminal.flush()
        interface.wait(timeout)

    def pytest_sessionfinish(self, session: pytest.Session, exitstatus: int) -> None:
        """Clean up after the test session."""
        # No containers to clean up
