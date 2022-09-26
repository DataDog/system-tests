from utils import context, BaseTestCase, interfaces, missing_feature, bug, released
from utils.tools import logger

@released(dotnet="2.12.0", java="0.108.1")
@missing_feature(library="cpp")
@missing_feature(library="ruby")
@missing_feature(library="php")
@missing_feature(library="golang", reason="Implemented but not merged in master")
@bug(library="nodejs", reason="Telemetry seems to be totally not working in UDS mode")
class Test_Telemetry(BaseTestCase):
    """Test that instrumentation telemetry is sent"""

    # containers for telemetry request to check consistency between library payloads and agent payloads
    library_requests = {}
    agent_requests = {}

    app_started_count = 0

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

    @missing_feature(library="java")
    @missing_feature(library="dotnet")
    @missing_feature(library="python")
    def test_telemetry_message_has_datadog_container_id(self):
        """Test telemetry messages contain datadog-container-id"""
        interfaces.agent.assert_headers_presence(
            path_filter="/api/v2/apmtelemetry", request_headers=["datadog-container-id"],
        )

    @missing_feature(library="python")
    def test_seq_id(self):
        """Test that messages are sent sequentially"""
        interfaces.library.assert_seq_ids_are_roughly_sequential()
        interfaces.library.assert_no_skipped_seq_ids()

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

        def validate_integration_changes(data):
            content = data["request"]["content"]
            if content.get("request_type") == "app-integrations-change":
                assert content["payload"]["integrations"], f"Integration changes must mot be empty"

        def validate_dependencies_changes(data):
            content = data["request"]["content"]
            if content["request_type"] == "app-dependencies-loaded":
                assert content["payload"]["dependencies"], f"dependencies changes must mot be empty"

        interfaces.library.add_telemetry_validation(validator=validate_integration_changes, is_success_on_expiry=True)
        interfaces.library.add_telemetry_validation(validator=validate_dependencies_changes, is_success_on_expiry=True)

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
            logger.debug(f"check_data_consistency library_requests::: {self.library_requests}")
            logger.debug(f"check_data_consistency agent_requests::: {self.agent_requests}")
            for key, agent_data in self.agent_requests.items():
                agent_message, agent_log_file = agent_data["request"]["content"], agent_data["log_filename"]
                logger.debug(f"MONTERO_TEST:: KEY ::: {key}")
                if key not in self.library_requests:
                    logger.debug(f"MONTERO :: KEY ::: {key}")
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

        logger.debug(f"MONTERO library_requests::: {self.library_requests}")
        logger.debug(f"MONTERO agent_requests::: {self.agent_requests}")
        # At the end, check that all data are consistent
        interfaces.agent.add_final_validation(check_data_consistency)
