import json
from typing import Any
from collections import defaultdict
from datetime import timedelta
import time
from dateutil.parser import isoparse
from utils import context, interfaces, missing_feature, bug, flaky, irrelevant, weblog, scenarios, features, rfc, logger
from utils.interfaces._misc_validators import HeadersPresenceValidator, HeadersMatchValidator
from utils.telemetry import get_lang_configs, load_telemetry_json

INTAKE_TELEMETRY_PATH = "/api/v2/apmtelemetry"
AGENT_TELEMETRY_PATH = "/telemetry/proxy/api/v2/apmtelemetry"


def get_header(data, origin, name):
    for h in data[origin]["headers"]:
        if h[0].lower() == name:
            return h[1]
    return None


def get_request_content(data):
    return data["request"]["content"]


def get_request_type(data):
    return get_request_content(data).get("request_type")


def get_configurations(data):
    return get_request_content(data)["payload"].get("configuration")


def get_service_name(data):
    return get_request_content(data)["application"].get("service_name")


def not_onboarding_event(data):
    return get_request_type(data) != "apm-onboarding-event"


def is_v2_payload(data):
    return get_request_content(data).get("api_version") == "v2"


def is_v1_payload(data):
    return get_request_content(data).get("api_version") == "v1"


@rfc("https://docs.google.com/document/d/1Fai2gZlkvfa_WQs_yJsmi3nUwiOsMtNu2LFBnbTHJRA/edit#heading=h.llmi584vls7r")
@features.telemetry_instrumentation
class Test_Telemetry:
    """Test that instrumentation telemetry is sent"""

    # containers for telemetry request to check consistency between library payloads and agent payloads
    library_requests: dict[tuple[str, str], dict] = {}
    agent_requests: dict[tuple[str, str], dict] = {}

    def validate_library_telemetry_data(self, validator, *, success_by_default=False):
        telemetry_data = list(interfaces.library.get_telemetry_data(flatten_message_batches=False))

        if len(telemetry_data) == 0 and not success_by_default:
            raise ValueError("No telemetry data to validate on")

        for data in telemetry_data:
            validator(data)

    def validate_agent_telemetry_data(self, validator, *, flatten_message_batches=True, success_by_default=False):
        telemetry_data = list(interfaces.agent.get_telemetry_data(flatten_message_batches=flatten_message_batches))

        if len(telemetry_data) == 0 and not success_by_default:
            raise ValueError("No telemetry data to validate on")

        for data in telemetry_data:
            validator(data)

    def test_telemetry_message_data_size(self):
        """Test telemetry message data size"""

        def validator(data):
            if data["request"]["length"] >= 5_000_000:
                raise ValueError("Received message size is more than 5MB")

        self.validate_library_telemetry_data(validator)
        self.validate_agent_telemetry_data(validator)

    def test_status_ok(self):
        """Test that telemetry requests sent to agent are successful"""

        def validator(data):
            response_code = data["response"]["status_code"]
            assert 200 <= response_code < 300, f"Got response code {response_code} in {data['log_filename']}"

        self.validate_library_telemetry_data(validator)

    @bug(context.agent_version >= "7.36.0" and context.agent_version < "7.37.0", reason="APMRP-360")
    @bug(context.agent_version > "7.53.0", reason="APMAPI-926")
    def test_telemetry_proxy_enrichment(self):
        """Test telemetry proxy adds necessary information"""

        header_presence_validator = HeadersPresenceValidator(
            request_headers=["dd-agent-hostname", "dd-agent-env"],
            response_headers=(),
            check_condition=not_onboarding_event,
        )
        header_match_validator = HeadersMatchValidator(
            request_headers={"via": r"trace-agent 7\..+"}, check_condition=not_onboarding_event
        )

        self.validate_agent_telemetry_data(header_presence_validator)
        self.validate_agent_telemetry_data(header_match_validator)

    @irrelevant(condition=True, reason="cgroup in weblog is 0::/, so this test can't work")
    def test_telemetry_message_has_datadog_container_id(self):
        """Test telemetry messages contain datadog-container-id"""
        interfaces.agent.assert_headers_presence(
            path_filter=INTAKE_TELEMETRY_PATH, request_headers=["datadog-container-id"]
        )

    @missing_feature(library="cpp")
    def test_telemetry_message_required_headers(self):
        """Test telemetry messages contain required headers"""

        interfaces.agent.assert_headers_presence(path_filter=INTAKE_TELEMETRY_PATH, request_headers=["dd-api-key"])
        interfaces.library.assert_headers_presence(
            path_filter=AGENT_TELEMETRY_PATH,
            request_headers=["dd-telemetry-api-version", "dd-telemetry-request-type"],
            check_condition=not_onboarding_event,
        )

    @irrelevant(library="php", reason="PHP registers 2 telemetry services")
    def test_seq_id(self):
        """Test that messages are sent sequentially"""

        max_out_of_order_lag = timedelta(seconds=0.3)  # s

        telemetry_data = list(interfaces.library.get_telemetry_data(flatten_message_batches=False))
        if len(telemetry_data) == 0:
            raise ValueError("No telemetry data to validate on")

        data_list_per_runtime = defaultdict(list)
        for data in telemetry_data:
            data_list_per_runtime[data["request"]["content"]["runtime_id"]].append(data)

        for runtime_id, data_list in data_list_per_runtime.items():
            logger.debug(f"Validating telemetry messages for runtime_id {runtime_id}")

            last_known_data = None

            for data in data_list:
                seq_id = data["request"]["content"]["seq_id"]
                curr_message_time = isoparse(data["request"]["timestamp_start"])
                logger.debug(f"Message at {curr_message_time.ctime()} in {data['log_filename']}, seq_id: {seq_id}")

                if not (200 <= data["response"]["status_code"] < 300):
                    logger.info(f"Response is {data['response']['status_code']}")

                if last_known_data is None:
                    # first payload sent, nothing to check
                    continue

                last_seq_id = last_known_data["request"]["content"]["seq_id"]
                last_message_time = isoparse(last_known_data["request"]["timestamp_start"])

                # in theory, this assertion can't fail, as timestamp_start is set by the proxy
                assert curr_message_time > last_message_time

                # check that the current seq_id is greater or equal than the previous one
                assert (
                    seq_id >= last_seq_id
                ), f"Detected non consecutive seq_ids between {data['log_filename']} and {last_known_data['log_filename']}"

                if seq_id == last_seq_id:
                    # if consecutive requests sue the same number, it may be caused by a retry
                    # in that situation, the time between the two requests should be very small
                    # in theory less than 100ms, we allow a bit more time in the test
                    if curr_message_time - last_message_time > max_out_of_order_lag:
                        raise ValueError(
                            f"Received message with seq_id {seq_id} to far more than"
                            f"100ms after message with seq_id {last_seq_id}"
                        )

                last_known_data = data

    @missing_feature(context.library < "ruby@1.22.0", reason="app-started not sent")
    @flaky(context.library <= "python@1.20.2", reason="APMRP-360")
    @irrelevant(library="php", reason="PHP registers 2 telemetry services")
    @features.telemetry_app_started_event
    def test_app_started_sent_exactly_once(self):
        """Request type app-started is sent exactly once"""

        count_by_runtime_id: dict[str, int] = defaultdict(lambda: 0)

        for data in interfaces.library.get_telemetry_data():
            if get_request_type(data) == "app-started":
                logger.debug(
                    f"Found app-started in {data['log_filename']}. Response from agent: {data['response']['status_code']}"
                )
                runtime_id = data["request"]["content"]["runtime_id"]
                if data["response"]["status_code"] == 202:
                    count_by_runtime_id[runtime_id] += 1

        assert all(count == 1 for count in count_by_runtime_id.values())

    @missing_feature(context.library < "ruby@1.22.0", reason="app-started not sent")
    @bug(context.library >= "dotnet@3.4.0", reason="APMAPI-728")
    @features.telemetry_app_started_event
    def test_app_started_is_first_message(self):
        """Request type app-started is the first telemetry message or the first message in the first batch"""
        telemetry_data = list(interfaces.library.get_telemetry_data(flatten_message_batches=False))
        assert len(telemetry_data) > 0, "No telemetry messages"
        if telemetry_data[0]["request"]["content"].get("request_type") == "message-batch":
            first_message = telemetry_data[0]["request"]["content"]["payload"][0]
            assert (
                first_message.get("request_type") == "app-started"
            ), "app-started was not the first message in the first batch"
        else:
            # In theory, app-started must have seq_id 1, but tracers may skip seq_ids if sending messages fail.
            # So we will check that app-started is the first message by seq_id, rather than strictly seq_id 1.
            telemetry_data = sorted(telemetry_data, key=lambda x: x["request"]["content"]["seq_id"])
            app_started = [d for d in telemetry_data if d["request"]["content"].get("request_type") == "app-started"]
            assert app_started, "app-started message not found"
            min_seq_id = min(d["request"]["content"]["seq_id"] for d in telemetry_data)
            assert (
                app_started[0]["request"]["content"]["seq_id"] == min_seq_id
            ), "app-started is not the first message by seq_id"

    @bug(weblog_variant="spring-boot-openliberty", reason="APPSEC-6583")
    @bug(weblog_variant="spring-boot-wildfly", reason="APPSEC-6583")
    @bug(context.agent_version > "7.53.0", reason="APMAPI-926")
    def test_proxy_forwarding(self):
        """Test that all telemetry requests sent by library are forwarded correctly by the agent"""

        def save_data(data, container):
            # payloads are identifed by their seq_id/runtime_id
            if not_onboarding_event(data):
                assert "seq_id" in data["request"]["content"], f"`seq_id` is missing in {data['log_filename']}"
                key = data["request"]["content"]["seq_id"], data["request"]["content"]["runtime_id"]
                container[key] = data

        self.validate_library_telemetry_data(
            lambda data: save_data(data, self.library_requests), success_by_default=False
        )
        self.validate_agent_telemetry_data(
            lambda data: save_data(data, self.agent_requests), flatten_message_batches=True, success_by_default=False
        )

        # At the end, check that all data are consistent
        for key, agent_data in self.agent_requests.items():
            agent_message, agent_log_file = agent_data["request"]["content"], agent_data["log_filename"]

            if key not in self.library_requests:
                # once the library interface is validated, weblog is not stopped. But it can send other data, and
                # they won't be seen. The agent interface wait 5 second after, and can collect data. So if the
                # library sent some data during this 5s, the agent interface will see it, but not the library
                # interface. For now, simply do not consider this use case, waiting for a better solution.

                pass

                # logger.error(str({
                #     "library_requests": [{"seq_id": s, "runtime_id": r} for s, r in self.library_requests],
                #     "agent_requests": [{"seq_id": s, "runtime_id": r} for s, r in self.agent_requests],
                # }))

                # raise Exception(
                #     f"Agent proxy forwarded a message that was not sent by the library: {agent_log_file}",
                # )
            else:
                lib_data = self.library_requests.pop(key)
                lib_message, lib_log_file = lib_data["request"]["content"], lib_data["log_filename"]

                if agent_message != lib_message:
                    raise ValueError(
                        f"Telemetry proxy message different in messages {lib_log_file} and {agent_log_file}:\n"
                        f"library sent {lib_message}\n"
                        f"agent sent {agent_message}"
                    )

        if len(self.library_requests) != 0:
            for s, r in self.library_requests:
                logger.error(f"seq_id: {s}, runtime_id: {r}")

            raise Exception("The following telemetry messages were not forwarded by the agent")

    @staticmethod
    def _get_heartbeat_delays_by_runtime() -> dict:
        """Returns a dict where :
        The key is the runtime id
        The value is a list of delay observed on this runtime id
        """

        telemetry_data = list(interfaces.library.get_telemetry_data())
        heartbeats_by_runtime = defaultdict(list)

        for data in telemetry_data:
            if data["request"]["content"].get("request_type") == "app-heartbeat":
                heartbeats_by_runtime[data["request"]["content"]["runtime_id"]].append(data)

        delays_by_runtime = {}

        for runtime_id, heartbeats in heartbeats_by_runtime.items():
            assert len(heartbeats) > 2, f"No enough telemetry messages to check delays for runtime id {runtime_id}"

            logger.debug(f"Heartbeats for runtime {runtime_id}:")

            # In theory, it's sorted. Let be safe
            heartbeats.sort(key=lambda data: isoparse(data["request"]["timestamp_start"]))

            prev_message_time = None
            delays: list[float] = []
            for data in heartbeats:
                curr_message_time = isoparse(data["request"]["timestamp_start"])
                if prev_message_time is None:
                    logger.debug(f"  * {data['log_filename']}: {curr_message_time}")
                else:
                    delay = (curr_message_time - prev_message_time).total_seconds()
                    logger.debug(f"  * {data['log_filename']}: {curr_message_time} => {delay}s ellapsed")
                    delays.append(delay)

                prev_message_time = curr_message_time

            delays_by_runtime[runtime_id] = delays

        return delays_by_runtime

    @missing_feature(library="cpp_nginx", reason="DD_TELEMETRY_HEARTBEAT_INTERVAL not supported")
    @missing_feature(library="cpp_httpd", reason="DD_TELEMETRY_HEARTBEAT_INTERVAL not supported")
    @flaky(context.library <= "java@1.38.1", reason="APMRP-360")
    @flaky(context.library <= "php@0.90", reason="APMRP-360")
    @flaky(library="ruby", reason="APMAPI-226")
    @flaky(context.library >= "java@1.39.0", reason="APMAPI-723")
    @bug(context.library > "php@1.5.1", reason="APMAPI-971")
    @features.telemetry_heart_beat_collected
    def test_app_heartbeats_delays(self):
        """Check for telemetry heartbeat are not sent too fast/slow, regarding DD_TELEMETRY_HEARTBEAT_INTERVAL
        There are a lot of reason for individual heartbeats to be sent too slow/fast, and the subsequent ones
        to be sent too fast/slow so the RFC says that it must not drift. So we will check the average delay
        """

        delays_by_runtime = self._get_heartbeat_delays_by_runtime()

        # This interval can't be perfeclty exact, give some room for tests
        lower_limit = timedelta(seconds=context.telemetry_heartbeat_interval * 0.75).total_seconds()
        upper_limit = timedelta(seconds=context.telemetry_heartbeat_interval * 1.5).total_seconds()
        expectation = f"It should be sent every {context.telemetry_heartbeat_interval}s"

        for delays in delays_by_runtime.values():
            average_delay = sum(delays) / len(delays)
            assert average_delay > lower_limit, f"Heartbeat sent too fast: {average_delay}s. {expectation}"
            assert average_delay < upper_limit, f"Heartbeat sent too slow: {average_delay}s. {expectation}"

    def setup_app_dependencies_loaded(self):
        weblog.get("/load_dependency")

    @irrelevant(library="php")
    @irrelevant(library="cpp_nginx")
    @irrelevant(library="cpp_httpd")
    @irrelevant(library="golang")
    @irrelevant(library="python")
    @missing_feature(context.library < "ruby@1.22.0", reason="Telemetry V2 is not implemented yet")
    @irrelevant(
        library="java",
        reason="""
        A Java application can be redeployed to the same server for many times (for the same JVM process).
        That means, every new deployment/reload of application will cause reloading classes/dependencies and as the result we will see duplications.
        """,
    )
    def test_app_dependencies_loaded(self):
        """Test app-dependencies-loaded requests"""

        test_loaded_dependencies = {
            "dotnet": {"NodaTime": False},
            "nodejs": {"glob": False},
            "java": {"httpclient": False},
            "ruby": {"bundler": False},
        }

        test_defined_dependencies = {
            "dotnet": {},
            "nodejs": {
                "body-parser": False,
                "cookie-parser": False,
                "express": False,
                "express-xml-bodyparser": False,
                "pg": False,
                "glob": False,
            },
            "java": {
                "spring-boot-starter-json": False,
                "spring-boot-starter-jdbc": False,
                "jackson-dataformat-xml": False,
                "dd-trace-api": False,
                "opentracing-api": False,
                "opentracing-util": False,
                "postgresql": False,
                "java-driver-core": False,
                "metrics-core": False,
                "mongo-java-driver": False,
                "ognl": False,
                "protobuf-java": False,
                "grpc-netty-shaded": False,
                "grpc-protobuf": False,
                "grpc-stub": False,
                "jaxb-api": False,
                "bcprov-jdk15on": False,
                "hsqldb": False,
                "spring-boot-starter-security": False,
                "spring-ldap-core": False,
                "spring-security-ldap": False,
                "unboundid-ldapsdk": False,
                "httpclient": False,
            },
            "ruby": {},
        }

        seen_loaded_dependencies = test_loaded_dependencies[context.library.name]
        seen_defined_dependencies = test_defined_dependencies[context.library.name]

        for data in interfaces.library.get_telemetry_data():
            content = data["request"]["content"]
            if content.get("request_type") == "app-started":
                if "dependencies" in content["payload"]:
                    for dependency in content["payload"]["dependencies"]:
                        dependency_id = dependency["name"]  # +dep["version"]
                        if dependency_id in seen_loaded_dependencies:
                            raise Exception("Loaded dependency should not be in app-started")
                        if dependency_id not in seen_defined_dependencies:
                            continue
                        seen_defined_dependencies[dependency_id] = True
            elif content.get("request_type") == "app-dependencies-loaded":
                for dependency in content["payload"]["dependencies"]:
                    dependency_id = dependency["name"]  # +dependency["version"]
                    if seen_loaded_dependencies.get(dependency_id) is True:
                        raise Exception(
                            "Loaded dependency event sent multiple times for same dependency " + dependency_id
                        )
                    if dependency_id in seen_defined_dependencies:
                        seen_defined_dependencies[dependency_id] = True
                    if dependency_id in seen_loaded_dependencies:
                        seen_loaded_dependencies[dependency_id] = True

        for dependency, seen in seen_loaded_dependencies.items():
            if not seen:
                raise Exception(dependency + " not received in app-dependencies-loaded message")

    @irrelevant(library="ruby")
    @irrelevant(library="golang")
    @irrelevant(library="dotnet")
    @irrelevant(library="python")
    @irrelevant(library="php")
    @irrelevant(library="java")
    @irrelevant(library="nodejs")
    @irrelevant(library="cpp_nginx")
    @irrelevant(library="cpp_httpd")
    def test_api_still_v1(self):
        """Test that the telemetry api is still at version v1
        If this test fails, please mark Test_TelemetryV2 as released for the current version of the tracer,
        and this test as no longer relevant
        """

        def validator(data):
            assert is_v1_payload(data)

        self.validate_library_telemetry_data(validator=validator, success_by_default=True)

    @missing_feature(context.library in ("php",), reason="Telemetry is not implemented yet.")
    @missing_feature(context.library < "ruby@1.22.0", reason="Telemetry V2 is not implemented yet")
    def test_app_started_client_configuration(self):
        """Assert that default and other configurations that are applied upon start time are sent with the app-started event"""

        trace_agent_port = scenarios.default.weblog_container.trace_agent_port

        test_configuration: dict[str, dict] = {
            "dotnet": {},
            "nodejs": {"hostname": "proxy", "port": trace_agent_port, "appsec.enabled": True},
            # to-do :need to add configuration keys once python bug is fixed
            "python": {},
            "cpp_nginx": {"trace_agent_port": trace_agent_port},
            "cpp_httpd": {"trace_agent_port": trace_agent_port},
            "java": {"trace_agent_port": trace_agent_port, "telemetry_heartbeat_interval": 2},
            "ruby": {"DD_AGENT_TRANSPORT": "TCP"},
            "golang": {"lambda_mode": False},
        }
        configuration_map = test_configuration[context.library.name]

        def validator(data):
            if get_request_type(data) == "app-started":
                content = data["request"]["content"]
                configurations = content["payload"]["configuration"]
                configurations_present = []

                # validator is updated to handle tracers sending configuration chaining data
                for expected_config_name, expected_value in configuration_map.items():
                    config_name_to_check = expected_config_name
                    if context.library.name == "java":
                        # support for older versions of Java Tracer
                        config_name_to_check = expected_config_name.replace(".", "_")

                    expected_value_str = str(expected_value).lower()

                    # Check if any configuration entry matches the expected name and value
                    config_found = False
                    for cnf in configurations:
                        # Handle different configuration structures - some might not have 'value' key
                        if cnf.get("name") == config_name_to_check:
                            config_value = cnf.get("value")
                            # Accept both the expected value and its float version for telemetry_heartbeat_interval
                            if expected_config_name == "telemetry_heartbeat_interval":
                                try:
                                    expected_float = float(expected_value)
                                    config_float = float(config_value)
                                    if config_float == expected_float:
                                        config_found = True
                                        configurations_present.append(expected_config_name)
                                        break
                                except Exception as e:
                                    logger.debug(
                                        f"Could not compare as float for config '{expected_config_name}': {e}"
                                    )  # fallback to string comparison below
                            if config_value is not None and str(config_value).lower() == expected_value_str:
                                config_found = True
                                configurations_present.append(expected_config_name)
                                break

                    if not config_found:
                        # For debugging, show all entries with this config name
                        matching_entries = [cnf for cnf in configurations if cnf.get("name") == config_name_to_check]
                        if matching_entries:
                            values_found = [
                                f"{cnf.get('value', 'NO_VALUE')} (origin: {cnf.get('origin', 'unknown')}, keys: {list(cnf.keys())})"
                                for cnf in matching_entries
                            ]
                            raise Exception(
                                f"Client Configuration {expected_config_name} expected value is {expected_value_str} "
                                f"but found values: {values_found}"
                            )
                        else:
                            raise Exception(
                                f"Client Configuration information is not accurately reported, "
                                f"{expected_config_name} is not present in configuration on app-started event"
                            )

        self.validate_library_telemetry_data(validator)

    def setup_app_product_change(self):
        weblog.get("/enable_product")

    @missing_feature(
        context.library in ("dotnet", "nodejs", "java", "python", "golang", "cpp_nginx", "cpp_httpd", "php", "ruby"),
        reason="Weblog GET/enable_product and app-product-change event is not implemented yet.",
    )
    def test_app_product_change(self):
        """Test product change data when product is enabled"""

        telemetry_data = list(interfaces.library.get_telemetry_data())
        if len(telemetry_data) == 0:
            raise Exception("No telemetry data to validate on")

        app_product_change_event_found = False
        for data in telemetry_data:
            if get_request_type(data) == "app-product-change":
                content = data["request"]["content"]
                app_product_change_event_found = True
                products = content["payload"]["products"]
                for product in products:
                    appsec_enabled = product["appsec"]["enabled"]
                    profiler_enabled = product["profiler"]["enabled"]
                    dynamic_instrumentation_enabled = product["dynamic_instrumentation"]["enabled"]
                    assert (
                        appsec_enabled is True
                    ), "Product appsec Product profiler enabled was expected to be True, found False"
                    assert profiler_enabled is True, "Product profiler enabled was expected to be True, found False"
                    assert (
                        dynamic_instrumentation_enabled is False
                    ), "Product dynamic_instrumentation enabled was expected to be False, found True"

        if app_product_change_event_found is False:
            raise Exception("app-product-change is not emitted when product change is enabled")


@features.telemetry_app_started_event
@scenarios.telemetry_enhanced_config_reporting
@rfc("https://docs.google.com/document/d/1vhIimn2vt4tDRSxsHn6vWSc8zYHl0Lv0Fk7CQps04C4/edit?usp=sharing")
class Test_TelemetryEnhancedConfigReporting:
    # Expected configuration precedence: default -> env_var -> code
    EXPECTED_CONFIGS: dict[str, dict[str, Any]] = {
        "nodejs": {
            "name": "DD_LOG_INJECTION",
            "precedence": [
                {"origin": "default", "value": True},
                {"origin": "env_var", "value": False},
                {"origin": "code", "value": True},
            ],
        },
        "python": {
            "name": "DD_LOGS_INJECTION",
            "precedence": [
                {"origin": "default", "value": True},
                {"origin": "env_var", "value": False},
                {"origin": "code", "value": True},
            ],
        },
        "dotnet": {
            "name": "DD_LOGS_INJECTION",
            "precedence": [
                {"origin": "default", "value": True},
                {"origin": "env_var", "value": False},
                {"origin": "code", "value": True},
            ],
        },
        "java": {
            "name": "logs_injection_enabled",
            "precedence": [
                {"origin": "default", "value": "true"},
                {
                    "origin": "jvm_prop",
                    "value": "true",
                },  # File-based properties differ from sysprops, but still report with origin:jvm_prop, even though they have a lower precedence than env_var: https://github.com/DataDog/dd-trace-java/blob/5c66a150ff3b16ebf9626c0f0170fc9715461a6b/utils/config-utils/src/main/java/datadog/trace/bootstrap/config/provider/ConfigProvider.java#L507-L514
                {"origin": "env_var", "value": "false"},
            ],
        },
    }

    def test_telemetry_events_seq_id(self):
        """Verify all configuration entries have valid seq_id."""
        configurations = interfaces.library.get_telemetry_configurations()
        assert configurations, "No configurations found"

        for config in configurations:
            assert "seq_id" in config, f"Configuration missing seq_id: {config}"
            assert config["seq_id"] is not None, f"Configuration has null seq_id: {config}"

    def test_telemetry_enhanced_config_reporting_precedence(self):
        """Verify configuration precedence order matches expected sequence."""
        expected_config = self.EXPECTED_CONFIGS[context.library.name]
        config_name = expected_config["name"]
        expected_precedence: list[dict[str, Any]] = expected_config["precedence"]

        # Get configurations from telemetry events
        all_configs = interfaces.library.get_telemetry_configurations()
        assert all_configs, "No configurations found"

        matching_configs = [cfg for cfg in all_configs if cfg["name"] == config_name]
        assert matching_configs, f"No configurations found for {config_name}"

        # Group configurations by origin and keep the latest (highest seq_id) for each origin
        latest_by_origin: dict[str, dict[str, Any]] = self._get_latest_configs_by_origin(matching_configs)

        # Sort latest configurations by origin by seq_id to get the effective precedence order
        sorted_configs: list[dict[str, Any]] = sorted(latest_by_origin.values(), key=lambda x: x["seq_id"])

        # Verify that configurations for the expected number of origins were received
        assert len(sorted_configs) == len(expected_precedence), f"Expected {expected_precedence}, Got: {sorted_configs}"

        # Verify each configuration matches expected precedence
        for i, expected in enumerate(expected_precedence):
            actual = sorted_configs[i]
            assert actual["name"] == config_name, f"Config: {actual}, Expected Name: {config_name}"
            assert actual["origin"] == expected["origin"], f"Config: {actual}, Expected Origin: {expected['origin']}"
            assert actual["value"] == expected["value"], f" Config: {actual}, Expected Value: {expected['value']}"

    def _get_latest_configs_by_origin(self, configs: list[dict]) -> dict[str, dict[str, Any]]:
        """Group configs by origin and return the latest (highest seq_id) for each origin."""
        latest_by_origin: dict[str, dict[str, Any]] = {}

        for config in configs:
            origin = config["origin"]
            if origin not in latest_by_origin or config["seq_id"] > latest_by_origin[origin]["seq_id"]:
                latest_by_origin[origin] = config
        return latest_by_origin


@features.telemetry_instrumentation
class Test_APMOnboardingInstallID:
    """Tests that APM onboarding install information is correctly propagated"""

    def test_traces_contain_install_id(self):
        """Assert that at least one trace carries APM onboarding info"""

        def validate_at_least_one_span_with_tag(tag):
            for _, span in interfaces.agent.get_spans():
                meta = span.get("meta", {})
                if tag in meta:
                    break
            else:
                raise Exception(f"Did not find tag {tag} in any spans")

        validate_at_least_one_span_with_tag("_dd.install.id")
        validate_at_least_one_span_with_tag("_dd.install.time")
        validate_at_least_one_span_with_tag("_dd.install.type")


def get_all_keys_and_values(*objs: tuple[None | dict | list, ...]) -> list:
    result: list = []
    for obj in objs:
        if obj is not None:
            if isinstance(obj, dict):
                result.extend(list(obj.keys()))
                result.extend(list(obj.values()))
            elif isinstance(obj, list):
                result.extend(obj)
            else:
                logger.error(f"Unexpected type in concat: {type(obj).__name__}")
    return result


def is_key_accepted_by_telemetry(key, allowed_keys, allowed_prefixes):
    lower_key = key.lower()
    is_allowed_key = lower_key in allowed_keys
    is_allowed_prefix = any(lower_key.startswith(prefix) for prefix in allowed_prefixes)

    return is_allowed_key or is_allowed_prefix


@features.telemetry_api_v2_implemented
class Test_TelemetryV2:
    """Test telemetry v2 specific constraints"""

    @missing_feature(library="dotnet", reason="Product started missing")
    @missing_feature(library="php", reason="Product started missing (both in libdatadog and php)")
    @missing_feature(library="python", reason="Product started missing in app-started payload")
    @missing_feature(library="cpp_nginx", reason="Product started missing in app-started payload")
    @missing_feature(library="cpp_httpd", reason="Product started missing in app-started payload")
    def test_app_started_product_info(self):
        """Assert that product information is accurately reported by telemetry"""

        for data in interfaces.library.get_telemetry_data(flatten_message_batches=True):
            if not is_v2_payload(data):
                continue
            if get_request_type(data) == "app-started":
                products = data["request"]["content"]["payload"]["products"]
                assert (
                    "appsec" in products
                ), "Product information is not accurately reported by telemetry on app-started event"

    @irrelevant(
        library="dotnet",
        reason="Re-enable when this automatically updates the dd-go files.",
    )
    @irrelevant(
        condition=context.library not in ("python", "java"),
        reason="This test causes to many friction. It has been replaced by alerts on slack channels",
    )
    def test_config_telemetry_completeness(self):
        """Assert that config telemetry is handled properly by telemetry intake

        Runbook: https://github.com/DataDog/system-tests/blob/main/docs/edit/runbook.md#test_config_telemetry_completeness
        """

        config_norm_rules = load_telemetry_json("config_norm_rules")
        config_prefix_block_list = load_telemetry_json("config_prefix_block_list")
        config_aggregation_list = load_telemetry_json("config_aggregation_list")

        lang_configs = get_lang_configs()

        for data in interfaces.library.get_telemetry_data(flatten_message_batches=True):
            if not is_v2_payload(data):
                continue
            if get_request_type(data) in ["app-started", "app-client-configuration-change"]:
                language_name = data["request"]["content"]["application"]["language_name"]

                lang_config = lang_configs.get(language_name, {})

                norm_rules = lang_config.get("normalization_rules", {})
                exact_keys = get_all_keys_and_values(config_norm_rules, norm_rules)

                prefix_keys = get_all_keys_and_values(
                    config_prefix_block_list,
                    lang_config.get("prefix_block_list", {}),
                    config_aggregation_list,
                    lang_config.get("reduce_rules", {}),
                )

                configuration = data["request"]["content"]["payload"]["configuration"]
                library_config_keys = sorted([config["name"] for config in configuration if "name" in config])

                missing_config_keys = [
                    key for key in library_config_keys if not is_key_accepted_by_telemetry(key, exact_keys, prefix_keys)
                ]

                # This may create a fairly large test output, but it makes the output more actionable
                if len(missing_config_keys) != 0:
                    logger.error(json.dumps(missing_config_keys, indent=2))
                    raise ValueError(
                        "(NOT A FLAKE) Read this quick runbook to update allowed configs: https://github.com/DataDog/system-tests/blob/main/docs/edit/runbook.md#test_config_telemetry_completeness"
                    )

    @missing_feature(library="cpp_nginx")
    @missing_feature(library="cpp_httpd")
    @missing_feature(context.library < "ruby@1.22.0", reason="dd-client-library-version missing")
    @bug(context.library == "python" and context.library.version.prerelease is not None, reason="APMAPI-927")
    def test_telemetry_v2_required_headers(self):
        """Assert library add the relevant headers to telemetry v2 payloads"""

        def validator(data):
            telemetry = data["request"]["content"]
            assert get_header(data, "request", "dd-telemetry-api-version") == telemetry.get("api_version")
            assert get_header(data, "request", "dd-telemetry-request-type") == telemetry.get("request_type")
            application = telemetry.get("application", {})
            assert get_header(data, "request", "dd-client-library-language") == application.get("language_name")
            assert get_header(data, "request", "dd-client-library-version") == application.get("tracer_version")

        interfaces.library.validate_telemetry(validator=validator, success_by_default=True)


@features.telemetry_api_v2_implemented
class Test_ProductsDisabled:
    """Assert that product information are not reported when products are disabled in telemetry"""

    @scenarios.telemetry_app_started_products_disabled
    @missing_feature(context.library == "python", reason="feature not implemented")
    @missing_feature(context.library == "java", reason="feature not implemented")
    def test_app_started_product_disabled(self):
        data_found = False
        app_started_found = False

        telemetry_data = interfaces.library.get_telemetry_data()

        for data in telemetry_data:
            logger.debug(f"Checking {data['log_filename']}")
            data_found = True

            if get_request_type(data) != "app-started":
                continue

            app_started_found = True

            payload = data["request"]["content"]["payload"]

            assert "products" in payload, "Product information was expected in app-started event, but was missing"

            logger.debug(json.dumps(payload["products"], indent=2))
            for product, details in payload["products"].items():
                if product == "tracers":
                    # tracers is enabled, otherwise, nothing is reported to the agent
                    # to be confirmed it's the good behaviour
                    continue

                assert (
                    "enabled" in details
                ), f"Product information expected to indicate {product} is disabled, but missing"
                assert (
                    details["enabled"] is False
                ), f"Product information expected to indicate {product} is disabled, but found enabled"

        if not data_found:
            raise ValueError("No telemetry data to validate on")

        if not app_started_found:
            raise ValueError("app-started event not found in telemetry data")

    @scenarios.telemetry_app_started_products_disabled
    @missing_feature(context.library == "ruby", reason="feature not implemented")
    @missing_feature(context.library == "nodejs", reason="feature not implemented")
    @irrelevant(library="golang")
    def test_debugger_products_disabled(self):
        """Assert that the debugger products are disabled by default including DI, and ER"""
        data_found = False
        config_norm_rules = load_telemetry_json("config_norm_rules")
        lang_configs = get_lang_configs()
        lang_configs["java"] = lang_configs["jvm"]

        di_config, er_config, co_config = None, None, None
        for data in interfaces.library.get_telemetry_data():
            if get_request_type(data) not in ["app-started", "app-client-configuration-change"]:
                continue

            data_found = True

            configuration = data["request"]["content"]["payload"]["configuration"]
            language = data["request"]["content"]["application"]["language_name"]
            lang_config = lang_configs.get(language, {})

            normalized_config = {}
            for item in configuration:
                name = item["name"].lower()
                if name in lang_config:
                    name = lang_config[name]
                elif name in config_norm_rules:
                    name = config_norm_rules[name]

                normalized_config[name] = item.get("value", None)

            if normalized_config.get("dynamic_instrumentation_enabled") is not None:
                di_config = str(normalized_config["dynamic_instrumentation_enabled"]).lower()

            if normalized_config.get("exception_replay_enabled") is not None:
                er_config = str(normalized_config["exception_replay_enabled"]).lower()

            if normalized_config.get("code_origin_for_spans_enabled") is not None:
                co_config = str(normalized_config["code_origin_for_spans_enabled"]).lower()

        assert data_found, "No app-started event found in telemetry data"
        assert di_config == "false", "DI should be disabled by default"
        assert er_config == "false", "Exception Replay should be disabled by default"
        assert co_config == "false", "Code Origin for Spans should be disabled by default"


@features.dd_telemetry_dependency_collection_enabled_supported
@scenarios.telemetry_dependency_loaded_test_for_dependency_collection_disabled
class Test_DependencyEnable:
    """Tests on DD_TELEMETRY_DEPENDENCY_COLLECTION_ENABLED flag"""

    def setup_app_dependency_loaded_not_sent_dependency_collection_disabled(self):
        weblog.get("/load_dependency")

    def test_app_dependency_loaded_not_sent_dependency_collection_disabled(self):
        """app-dependencies-loaded request should not be sent if DD_TELEMETRY_DEPENDENCY_COLLECTION_ENABLED is false"""

        for data in interfaces.library.get_telemetry_data():
            if get_request_type(data) == "app-dependencies-loaded":
                raise ValueError("request_type app-dependencies-loaded should not be sent by this tracer")


@features.telemetry_message_batch
class Test_MessageBatch:
    """Tests on Message batching"""

    def setup_message_batch_enabled(self):
        weblog.get("/load_dependency")
        weblog.get("/enable_integration")
        weblog.get("/enable_product")

    @bug(library="nodejs", reason="APMAPI-929")
    def test_message_batch_enabled(self):
        """Test that events are sent in message batches"""
        event_list = set()
        for data in interfaces.library.get_telemetry_data(flatten_message_batches=False):
            content = data["request"]["content"]
            event_list.add(content.get("request_type"))

        assert "message-batch" in event_list, f"Expected one or more message-batch events: {event_list}"


@features.telemetry_api_v2_implemented
class Test_Log_Generation:
    """Assert that logs reported by default, and not reported when logs generation is disabled in telemetry"""

    def _get_filename_with_logs(self):
        all_data = interfaces.library.get_telemetry_data()
        return [data["log_filename"] for data in all_data if get_request_type(data) == "logs"]

    @scenarios.telemetry_log_generation_disabled
    def test_log_generation_disabled(self):
        """When DD_TELEMETRY_LOGS_COLLECTION_ENABLED=false, no log should be sent"""
        assert len(self._get_filename_with_logs()) == 0, "Library shouldn't have sent any log"

    def test_log_generation_enabled(self):
        """By default, some logs should be sent"""
        assert len(self._get_filename_with_logs()) != 0


@features.telemetry_metrics_collected
@scenarios.telemetry_metric_generation_disabled
class Test_Metric_Generation_Disabled:
    """Assert that metrics are not reported when metric generation is disabled in telemetry"""

    def test_metric_generation_disabled(self):
        all_data = list(interfaces.library.get_telemetry_data(flatten_message_batches=True))
        assert len(all_data) != 0, "No telemetry data to validate on"
        generate_metrics_messages = [d for d in all_data if get_request_type(d) == "generate-metrics"]
        assert len(generate_metrics_messages) == 0, "Metric generation event is sent when metric generation is disabled"


@features.telemetry_metrics_collected
@scenarios.agent_supporting_span_events
class Test_Metric_Generation_Enabled:
    """Assert that metrics are reported when metric generation is enabled in telemetry"""

    METRIC_FLUSH_INTERVAL = 10  # This is constant by design

    def setup_metric_generation_enabled(self):
        weblog.get("/")
        # Wait for at least 2 metric flushes, i.e. 20s
        logger.debug("Waiting 20s for metric flushes...")
        time.sleep(self.METRIC_FLUSH_INTERVAL * 2)
        logger.debug("Wait complete")

    def test_metric_generation_enabled(self):
        found = False
        for data in interfaces.library.get_telemetry_data():
            content = data["request"]["content"]
            if content.get("request_type") != "generate-metrics":
                continue
            if content["payload"]["series"]:
                found = True
                break
        assert found, "No metrics found in telemetry data"

    @missing_feature(library="java", reason="Not implemented")
    @missing_feature(library="nodejs")
    def test_metric_general_logs_created(self):
        self.assert_count_metric("general", "logs_created", expect_at_least=1)

    def test_metric_tracers_spans_created(self):
        self.assert_count_metric("tracers", "spans_created", expect_at_least=1)

    def test_metric_tracers_spans_finished(self):
        self.assert_count_metric("tracers", "spans_finished", expect_at_least=1)

    @missing_feature(library="java", reason="Not implemented")
    @missing_feature(library="nodejs")
    def test_metric_tracers_spans_enqueued_for_serialization(self):
        self.assert_count_metric("tracers", "spans_enqueued_for_serialization", expect_at_least=1)

    @missing_feature(library="java", reason="Not implemented")
    @missing_feature(library="nodejs")
    def test_metric_tracers_trace_segments_created(self):
        self.assert_count_metric("tracers", "trace_segments_created", expect_at_least=1)

    @missing_feature(library="java", reason="Not implemented")
    @missing_feature(library="nodejs")
    def test_metric_tracers_trace_chunks_enqueued_for_serialization(self):
        self.assert_count_metric("tracers", "trace_chunks_enqueued_for_serialization", expect_at_least=1)

    @missing_feature(library="java", reason="Not implemented")
    @missing_feature(library="nodejs")
    def test_metric_tracers_trace_chunks_sent(self):
        self.assert_count_metric("tracers", "trace_chunks_sent", expect_at_least=1)

    @missing_feature(library="java", reason="Not implemented")
    @missing_feature(library="nodejs")
    def test_metric_tracers_trace_segments_closed(self):
        self.assert_count_metric("tracers", "trace_segments_closed", expect_at_least=1)

    @missing_feature(library="java", reason="Not implemented")
    @missing_feature(library="nodejs")
    def test_metric_tracers_trace_api_requests(self):
        self.assert_count_metric("tracers", "trace_api.requests", expect_at_least=1)

    @missing_feature(library="java", reason="Not implemented")
    @missing_feature(library="nodejs")
    def test_metric_tracers_trace_api_responses(self):
        self.assert_count_metric("tracers", "trace_api.responses", expect_at_least=1)

    @missing_feature(library="java", reason="Not implemented")
    @missing_feature(library="nodejs")
    def test_metric_telemetry_api_requests(self):
        self.assert_count_metric("telemetry", "telemetry_api.requests", expect_at_least=1)

    @missing_feature(library="java", reason="Not implemented")
    @missing_feature(library="nodejs")
    def test_metric_telemetry_api_responses(self):
        self.assert_count_metric("telemetry", "telemetry_api.responses", expect_at_least=1)

    def assert_count_metric(self, namespace, metric, expect_at_least):
        series = list(interfaces.library.get_telemetry_metric_series(namespace, metric))
        assert len(series) != 0 or expect_at_least == 0, f"No telemetry data received for metric {namespace}.{metric}"

        count = 0
        for s in series:
            # assert correct type (count)
            # assert points total
            assert s["common"] is True
            assert s["type"] == "count"
            assert len(s["points"]) >= 1
            for p in s["points"]:
                count = count + p[1]

        assert count >= expect_at_least


@rfc("https://docs.google.com/document/d/1xTLC3UEGNooZS0YOYp3swMlAhtvVn1aa639TGxHHYvg/edit")
@features.telemetry_app_started_event
class Test_TelemetrySCAEnvVar:
    def test_telemetry_sca_propagated(self):
        target_service_name = "weblog"
        target_request_type = ["app-started", "app-client-configuration-change"]
        telemetry_data = list(interfaces.library.get_telemetry_data(flatten_message_batches=True))
        events = []

        for t in telemetry_data:
            if get_request_type(t) in target_request_type and get_service_name(t) == target_service_name:
                events.append(t)

        assert len(events) > 0, f"No telemetry found for {target_service_name} on {target_request_type}"

        found = False
        for e in events:
            configurations = get_configurations(e)
            for c in configurations:
                if c["name"] in ("appsec.sca_enabled", "DD_APPSEC_SCA_ENABLED"):
                    found = True
                    break
            if found:
                break

        assert found, f"No telemetry found for {target_service_name} on {target_request_type} with configuration appsec.sca_enabled"
