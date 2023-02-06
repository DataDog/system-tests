from datetime import datetime, timedelta

from utils import context, interfaces, missing_feature, bug, released, flaky, irrelevant
from utils.tools import logger
from utils.interfaces._misc_validators import HeadersPresenceValidator, HeadersMatchValidator


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

    def validate_library_telemetry_data(self, validator, success_by_default=False):
        telemetry_data = list(interfaces.library.get_telemetry_data())

        if len(telemetry_data) == 0:
            if not success_by_default:
                raise Exception("No telemetry data to validate on")

        for data in telemetry_data:
            validator(data)

    def validate_agent_telemetry_data(self, validator, success_by_default=False):
        telemetry_data = list(interfaces.agent.get_telemetry_data())

        if len(telemetry_data) == 0:
            if not success_by_default:
                raise Exception("No telemetry data to validate on")

        for data in telemetry_data:
            validator(data)

    @flaky(library="java", reason="Agent sometimes respond 502")
    def test_status_ok(self):
        """Test that telemetry requests are successful"""

        def validator(data):
            response_code = data["response"]["status_code"]
            assert 200 <= response_code < 300, f"Got response code {response_code}"

        self.validate_library_telemetry_data(validator)

    @bug(
        context.agent_version >= "7.36.0" and context.agent_version < "7.37.0",
        reason="Version reporting of trace agent is broken in 7.36.x release",
    )
    def test_telemetry_proxy_enrichment(self):
        """Test telemetry proxy adds necessary information"""

        def not_onboarding_event(data):
            return data["request"]["content"].get("request_type") != "apm-onboarding-event"

        header_presence_validator = HeadersPresenceValidator(
            request_headers=["dd-agent-hostname", "dd-agent-env"],
            response_headers=(),
            check_condition=not_onboarding_event,
        )
        header_match_validator = HeadersMatchValidator(
            request_headers={"via": r"trace-agent 7\..+"}, response_headers=(), check_condition=not_onboarding_event
        )

        self.validate_agent_telemetry_data(header_presence_validator)
        self.validate_agent_telemetry_data(header_match_validator)

    @irrelevant(True, reason="cgroup in weblog is 0::/, so this test can't work")
    def test_telemetry_message_has_datadog_container_id(self):
        """Test telemetry messages contain datadog-container-id"""
        interfaces.agent.assert_headers_presence(
            path_filter="/api/v2/apmtelemetry", request_headers=["datadog-container-id"],
        )

    @missing_feature(library="python")
    def test_seq_id(self):
        """Test that messages are sent sequentially"""

        MAX_OUT_OF_ORDER_LAG = 0.1  # s

        max_seq_id = 0
        received_max_time = None
        seq_ids = []

        fmt = "%Y-%m-%dT%H:%M:%S.%f"

        telemetry_data = list(interfaces.library.get_telemetry_data())
        if len(telemetry_data) == 0:
            raise Exception("No telemetry data to validate on")

        for data in telemetry_data:
            if 200 <= data["response"]["status_code"] < 300:
                seq_id = data["request"]["content"]["seq_id"]
                seq_ids.append((seq_id, data["log_filename"]))
                curr_message_time = datetime.strptime(data["request"]["timestamp_start"], fmt)
            if seq_id > max_seq_id:
                max_seq_id = seq_id
                received_max_time = curr_message_time
            else:
                if received_max_time is not None and (curr_message_time - received_max_time) > MAX_OUT_OF_ORDER_LAG:
                    raise Exception(
                        f"Received message with seq_id {seq_id} to far more than"
                        f"100ms after message with seq_id {max_seq_id}"
                    )

        seq_ids.sort()
        for i in range(len(seq_ids) - 1):
            diff = seq_ids[i + 1][0] - seq_ids[i][0]
            if diff == 0:
                raise Exception(
                    f"Detected 2 telemetry messages with same seq_id {seq_ids[i + 1][1]} and {seq_ids[i][1]}"
                )

            if diff > 1:
                raise Exception(f"Detected non conscutive seq_ids between {seq_ids[i + 1][1]} and {seq_ids[i][1]}")

    @bug(library="python", reason="To be explained")
    @missing_feature(context.weblog_variant == "spring-boot-native", reason="GraalVM. Tracing support only")
    @missing_feature(context.weblog_variant == "spring-boot-3-native", reason="GraalVM. Tracing support only")
    def test_app_started(self):
        """Request type app-started is sent on startup at least once"""

        def validator(data):
            return data["request"]["content"].get("request_type") == "app-started"

        self.validate_library_telemetry_data(validator)

    @missing_feature(library="python")
    def test_app_started_sent_only_once(self):
        """Request type app-started is not sent twice"""

        def validator(data):
            if data["request"]["content"].get("request_type") == "app-started":
                self.app_started_count += 1
                assert self.app_started_count < 2, "request_type/app-started has been sent too many times"

        self.validate_library_telemetry_data(validator)

    def test_telemetry_messages_valid(self):
        """Telemetry messages additional validation"""

        def validate_integration_changes(data):
            content = data["request"]["content"]
            if content.get("request_type") == "app-integrations-change":
                assert content["payload"]["integrations"], "Integrations changes must not be empty"

        def validate_dependencies_changes(data):
            content = data["request"]["content"]
            if content["request_type"] == "app-dependencies-loaded":
                assert content["payload"]["dependencies"], "Dependencies changes must not be empty"

        self.validate_library_telemetry_data(validate_integration_changes)
        self.validate_library_telemetry_data(validate_dependencies_changes)

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
    @bug(
        library="java", weblog_variant="spring-boot-wildfly",
    )
    def test_proxy_forwarding(self):
        """Test that all telemetry requests sent by library are forwarded correctly by the agent"""

        def save_data(data, container):
            # payloads are identifed by their seq_id/runtime_id
            key = data["request"]["content"]["tracer_time"], data["request"]["content"]["runtime_id"]
            container[key] = data

        self.validate_library_telemetry_data(
            lambda data: save_data(data, self.library_requests), success_by_default=False
        )
        self.validate_agent_telemetry_data(lambda data: save_data(data, self.agent_requests), success_by_default=False)

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
                logger.error(f"tracer_time: {s}, runtime_id: {r}")

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

        self.validate_library_telemetry_data(validator)

    def test_app_heartbeat(self):
        """Check for heartbeat or messages within interval and valid started and closing messages"""

        prev_message_time = -1
        TELEMETRY_HEARTBEAT_INTERVAL = int(context.weblog_image.env.get("DD_TELEMETRY_HEARTBEAT_INTERVAL", 60))
        ALLOWED_INTERVALS = 2
        fmt = "%Y-%m-%dT%H:%M:%S.%f"

        telemetry_data = list(interfaces.library.get_telemetry_data())
        if len(telemetry_data) == 0:
            raise Exception("No telemetry data to validate on")

        for data in telemetry_data:
            curr_message_time = datetime.strptime(data["request"]["timestamp_start"], fmt)
            if prev_message_time != -1:
                delta = curr_message_time - prev_message_time
                if delta > timedelta(seconds=ALLOWED_INTERVALS * TELEMETRY_HEARTBEAT_INTERVAL):
                    raise Exception(
                        f"No heartbeat or message sent in {ALLOWED_INTERVALS} hearbeat intervals: "
                        "{TELEMETRY_HEARTBEAT_INTERVAL}\nLast message was sent {str(delta)} seconds ago."
                    )
            prev_message_time = curr_message_time
