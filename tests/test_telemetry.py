from datetime import datetime, timedelta

from utils import context, interfaces, missing_feature, bug, released, flaky, irrelevant
from utils.tools import logger


@released(dotnet="2.12.0", java="0.108.1", nodejs="3.2.0")
@bug(context.uds_mode and context.library < "nodejs@3.7.0")
@missing_feature(library="cpp")
@missing_feature(library="ruby")
@missing_feature(library="php")
@missing_feature(library="golang", reason="Implemented but not merged in master")
class Test_Telemetry:
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

        interfaces.library.validate_telemetry(validator, success_by_default=True)
        interfaces.agent.validate_telemetry(validator, success_by_default=True)

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

        interfaces.library.validate_telemetry(validator=validator)

    @missing_feature(library="python")
    def test_app_started_sent_only_once(self):
        """Request type app-started is not sent twice"""

        def validator(data):
            if data["request"]["content"].get("request_type") == "app-started":
                self.app_started_count += 1
                assert self.app_started_count < 2, "request_type/app-started has been sent too many times"

        interfaces.library.validate_telemetry(validator=validator, success_by_default=True)

    def test_telemetry_messages_valid(self):
        """Telemetry messages additional validation"""

        def validate_integration_changes(data):
            content = data["request"]["content"]
            if content.get("request_type") == "app-integrations-change":
                assert content["payload"]["integrations"], "Integration changes must mot be empty"

        def validate_dependencies_changes(data):
            content = data["request"]["content"]
            if content["request_type"] == "app-dependencies-loaded":
                assert content["payload"]["dependencies"], "dependencies changes must mot be empty"

        interfaces.library.validate_telemetry(validator=validate_integration_changes, success_by_default=True)
        interfaces.library.validate_telemetry(validator=validate_dependencies_changes, success_by_default=True)

    @bug(
        library="dotnet",
        reason="""
            Bug in the telemetry agent proxy, that can't reopen connections if they're closed by timeout
            https://github.com/DataDog/datadog-agent/pull/11880
        """,
    )
    @bug(
        library="java",
        weblog_variant="spring-boot-openliberty",
        reason="https://datadoghq.atlassian.net/browse/APPSEC-6583",
    )
    def test_proxy_forwarding(self):
        """Test that all telemetry requests sent by library are forwarded correctly by the agent"""

        def save_data(data, container):
            # payloads are identifed by their seq_id/runtime_id
            key = data["request"]["content"]["seq_id"], data["request"]["content"]["runtime_id"]
            container[key] = data

        # save all data from lib to agent
        interfaces.library.validate_telemetry(lambda data: save_data(data, self.library_requests), True)

        # save all data from agent to backend
        interfaces.agent.validate_telemetry(lambda data: save_data(data, self.agent_requests), True)

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
                    raise Exception(
                        f"Telemetry proxy message different in messages {lib_log_file} and {agent_log_file}:\n"
                        f"library sent {lib_message}\n"
                        f"agent sent {agent_message}"
                    )

        if len(self.library_requests) != 0:
            for s, r in self.library_requests:
                logger.error(f"seq_id: {s}, runtime_id: {r}")

            raise Exception("The following telemetry messages were not forwarded by the agent")

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

        interfaces.library.validate_telemetry(validator=validator, success_by_default=True)

    def test_app_heartbeat(self):
        """Check for heartbeat or messages within interval and valid started and closing messages"""

        prev_message_time = -1
        TELEMETRY_HEARTBEAT_INTERVAL = int(context.weblog_image.env.get("DD_TELEMETRY_HEARTBEAT_INTERVAL", 60))
        ALLOWED_INTERVALS = 2
        fmt = "%Y-%m-%dT%H:%M:%S.%f"

        for data in interfaces.library.get_telemetry_data():
            curr_message_time = datetime.strptime(data["request"]["timestamp_start"], fmt)
            if prev_message_time != -1:
                delta = curr_message_time - prev_message_time
                if delta > timedelta(seconds=ALLOWED_INTERVALS * TELEMETRY_HEARTBEAT_INTERVAL):
                    raise Exception(
                        f"No heartbeat or message sent in {ALLOWED_INTERVALS} hearbeat intervals: "
                        "{TELEMETRY_HEARTBEAT_INTERVAL}\nLast message was sent {str(delta)} seconds ago."
                    )
            prev_message_time = curr_message_time
