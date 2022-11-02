from utils import context, BaseTestCase, interfaces, missing_feature, bug, released, flaky, irrelevant


@released(dotnet="2.12.0", java="0.108.1", nodejs="3.2.0")
@bug(context.scenario == "UDS" and context.library < "nodejs@3.7.0")
@missing_feature(library="cpp")
@missing_feature(library="ruby")
@missing_feature(library="php")
@missing_feature(library="golang", reason="Implemented but not merged in master")
class Test_Telemetry(BaseTestCase):
    """Test that instrumentation telemetry is sent"""

    # containers for telemetry request to check consistency between library payloads and agent payloads
    library_requests = {}
    agent_requests = {}

    app_started_count = 0

    @flaky(library="java", reason="Agent sometimes respond 502")
    def test_status_ok(self):
        """Test that telemetry requests are successful"""

        def validator(data):
            repsonse_code = data["response"]["status_code"]
            assert 200 <= repsonse_code < 300, f"Got response code {repsonse_code}"

        interfaces.library.add_telemetry_validation(validator, is_success_on_expiry=True)
        interfaces.agent.add_telemetry_validation(validator, is_success_on_expiry=True)

    @bug(
        context.agent_version >= "7.36.0" and context.agent_version < "7.37.0",
        reason="Version reporting of trace agent is broken in 7.36.x release",
    )
    def test_telemetry_proxy_enrichment(self):
        """Test telemetry proxy adds necessary information"""
        interfaces.agent.assert_headers_presence(
            path_filter="/api/v2/apmtelemetry", request_headers=["dd-agent-hostname", "dd-agent-env"],
        )
        interfaces.agent.assert_headers_match(
            path_filter="/api/v2/apmtelemetry", request_headers={"via": r"trace-agent 7\..+"},
        )

    @irrelevant(True, reason="cgroup in weblog is 0::/, so this test can't work")
    def test_telemetry_message_has_datadog_container_id(self):
        """Test telemetry messages contain datadog-container-id"""
        interfaces.agent.assert_headers_presence(
            path_filter="/api/v2/apmtelemetry", request_headers=["datadog-container-id"],
        )

    def test_telemetry_message_required_headers(self):
        """Test telemetry messages contain required headers"""
        interfaces.agent.assert_headers_presence(
            path_filter="/api/v2/apmtelemetry",
            request_headers=["dd-api-key", "dd-telemetry-api-version", "dd-telemetry-request-type"],
        )

    @missing_feature(library="python")
    def test_seq_id(self):
        """Test that messages are sent sequentially"""
        interfaces.library.assert_seq_ids_are_roughly_sequential()
        interfaces.library.assert_no_skipped_seq_ids()

    @bug(library="python", reason="To be explained")
    def test_app_started(self):
        """Request type app-started is sent on startup at least once"""

        def validator(data):
            return data["request"]["content"].get("request_type") == "app-started"

        interfaces.library.add_telemetry_validation(validator=validator)

    @missing_feature(library="python")
    def test_app_started_sent_only_once(self):
        """Request type app-started is not sent twice"""

        def validator(data):
            if data["request"]["content"].get("request_type") == "app-started":
                self.app_started_count += 1
                assert self.app_started_count < 2, "request_type/app-started has been sent too many times"

        interfaces.library.add_telemetry_validation(validator=validator, is_success_on_expiry=True)

    def test_telemetry_messages_valid(self):
        """Telemetry messages additional validation"""

        integrations_with_version = set()

        def validate_dependencies(dependencies, track_integration_w_version=False, check_integration_w_version=False):
            seen_dependencies = set()
            for dependency in dependencies:
                assert dependency.get("name"), "Dependency name must be specified"
                dependency_id = dependency["name"]
                if dependency.get("version"):
                    dependency_id += dependency["version"]
                    if track_integration_w_version:
                        # Track integrations with versions
                        integrations_with_version.add(dependency["name"])
                else:
                    if check_integration_w_version:
                        # Check for integration versions if sent in app_started
                        assert (
                            dependency_id not in integrations_with_version
                        ), "Integration must have version if specified in app-started"

                assert dependency_id not in seen_dependencies, "Dependency payload must not contain duplicates"
                seen_dependencies.add(dependency_id)

        def validate_top_level_keys(data):
            content = data["request"]["content"]
            if content.get("request_type") == "app-heartbeat" or content.get("request_type") == "app-closing":
                return
            required_top_level_keys = ["api_version", "request_type", "runtime_id", "payload", "host", "tracer_time"]
            for field in required_top_level_keys:
                assert content.get(field), f"{field} must not be empty"
            application = content.get("application")
            required_application_keys = ["language_name", "language_version", "service_name", "tracer_version"]
            assert application, "Application must not be empty"
            for field in required_application_keys:
                assert application.get(field), f"{field} must not be empty"

        def validate_app_started(content):
            host = content["host"]
            payload = content["payload"]
            required_app_started_payload_keys = [
                "hostname",
                "os",
                "os_version",
                "kernel_name",
                "kernel_release",
                "kernel_version",
            ]
            for field in required_app_started_payload_keys:
                assert host.get(field), f"{field} must not be empty"
            if payload.get("dependencies"):
                validate_dependencies(payload["dependencies"])
            if payload.get("integrations"):
                validate_dependencies(payload["integrations"], track_integration_w_version=True)

        def validate_integrations_change(content):
            assert content["payload"]["integrations"], "Integrations changes must not be empty"
            validate_dependencies(content["payload"]["integrations"], check_integration_w_version=True)

        def validate_dependencies_loaded(content):
            assert content["payload"]["dependencies"], "Dependencies loaded must not be empty"
            validate_dependencies(content["payload"]["dependencies"])

        def validate_event_payloads(data):
            content = data["request"]["content"]
            if content.get("request_type") == "app-started":
                validate_app_started(content)
            elif content.get("request_type") == "app-dependencies-loaded":
                validate_dependencies_loaded(content)
            elif content.get("request_type") == "app-integrations-change":
                validate_integrations_change(content)

        interfaces.library.add_telemetry_validation(validator=validate_top_level_keys, is_success_on_expiry=True)
        interfaces.library.add_telemetry_validation(validator=validate_event_payloads, is_success_on_expiry=True)

    @bug(
        library="dotnet",
        reason="""
            Bug in the telemetry agent proxy, that can't reopen connections if they're closed by timeout
            https://github.com/DataDog/datadog-agent/pull/11880
        """,
    )
    def test_proxy_forwarding(self):
        """Test that all telemetry requests sent by library are forwarded correctly by the agent"""

        def save_data(data, container):
            # payloads are identifed by their seq_id/runtime_id
            key = data["request"]["content"]["seq_id"], data["request"]["content"]["runtime_id"]
            container[key] = data

        def check_data_consistency():

            for key, agent_data in self.agent_requests.items():
                agent_message, agent_log_file = agent_data["request"]["content"], agent_data["log_filename"]

                if key not in self.library_requests:
                    raise Exception(
                        f"Agent proxy forwarded a message that was not sent by the library: {agent_log_file}"
                    )

                lib_data = self.library_requests.pop(key)
                lib_message, lib_log_file = lib_data["request"]["content"], lib_data["log_filename"]

                if agent_message != lib_message:
                    raise Exception(
                        f"Telemetry proxy message different in messages {lib_log_file} and {agent_log_file}:\n"
                        f"library sent {lib_message}\n"
                        f"agent sent {agent_message}"
                    )

            if len(self.library_requests) != 0:
                raise Exception(
                    f"The following telemetry messages were not forwarded by the agent: \n"
                    f"{' '.join((data for _, data in self.library_requests.values()))}"
                )

            return True  # all good!

        # save all data from lib to agent
        interfaces.library.add_telemetry_validation(lambda data: save_data(data, self.library_requests), True)

        # save all data from agent to backend
        interfaces.agent.add_telemetry_validation(lambda data: save_data(data, self.agent_requests), True)

        # At the end, check that all data are consistent
        interfaces.agent.add_final_validation(check_data_consistency)

    @irrelevant(library="java")
    @irrelevant(library="nodejs")
    @irrelevant(library="dotnet")
    def test_app_dependencies_loaded_not_sent(self):
        """app-dependencies-loaded request should not be sent"""
        # Request type app-dependencies-loaded is never sent from certain language tracers
        # In case this changes we need to adjust the backend, by adding the language to this list
        # https://github.com/DataDog/dd-go/blob/prod/domains/appsec/libs/vulnerability_management/model.go#L262
        # This change means we cannot deduplicate runtime with the same library dependencies in the backend since
        # we never have guarantees that we have all the dependencies at one point in time

        def validator(data):
            if data["request"]["content"].get("request_type") == "app-dependencies-loaded":
                raise Exception("request_type app-dependencies-loaded should not be used by this tracer")

        interfaces.library.add_telemetry_validation(validator=validator, is_success_on_expiry=True)
