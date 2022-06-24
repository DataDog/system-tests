from utils import context, BaseTestCase, interfaces, missing_feature, bug


@missing_feature(library="cpp")
@missing_feature(library="java")
@missing_feature(library="ruby")
@missing_feature(library="php")
@missing_feature(library="golang", reason="Implemented but not merged in master")
class Test_Telemetry(BaseTestCase):
    """Test that instrumentation telemetry is sent"""

    app_started_count = 0

    def test_status_ok(self):
        """Test that telemetry requests are successful"""

        def validator(data):
            repsonse_code = data["response"]["status_code"]
            assert 200 <= repsonse_code < 300, f"Got response code {repsonse_code}"

        interfaces.library.add_telemetry_validation(validator, is_success_on_expiry=True)
        interfaces.agent.add_telemetry_validation(validator, is_success_on_expiry=True)

    @missing_feature(library="dotnet")
    @missing_feature(library="python")
    def test_telemetry_proxy_enrichment(self):
        """Test telemetry proxy adds necessary information"""
        interfaces.agent.assert_headers_presence(
            path_filter="/api/v2/apmtelemetry",
            request_headers=["dd-agent-hostname", "dd-agent-env", "datadog-container-id"],
        )

    @missing_feature(library="python")
    def test_seq_id(self):
        """Test that messages are sent sequentially"""
        interfaces.library.assert_seq_ids_are_roughly_sequential()
        interfaces.library.assert_no_skipped_seq_ids()

    @missing_feature(library="python")
    @missing_feature(library="nodejs")
    def test_app_started(self):
        """Request type app-started is sent on startup at least once"""

        def validator(data):
            return data["request"]["content"].get("request_type") == "app-started"

        interfaces.library.add_telemetry_validation(validator=validator)

    @missing_feature(library="python")
    @missing_feature(library="nodejs")
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
        """Test that the telemetry proxy forwards messages correctly"""
        interfaces.library.assert_all_telemetry_messages_proxied(interfaces.agent)
