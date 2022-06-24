from utils import context, BaseTestCase, interfaces, missing_feature, bug


@missing_feature(library="cpp")
@missing_feature(library="java")
@missing_feature(library="ruby")
@missing_feature(library="php")
@missing_feature(library="golang", reason="Implemented but not merged in master")
class Test_Telemetry(BaseTestCase):
    """Test that instrumentation telemetry is sent"""

    def test_status_ok(self):
        """Test that telemetry requests are successful"""
        interfaces.library.assert_telemetry_requests_are_successful()
        interfaces.agent.assert_telemetry_requests_are_successful()

    def test_telemetry_proxy_enrichment(self):
        """Test telemetry proxy adds necessary information"""
        interfaces.agent.assert_headers_presence(
            path_filter="/api/v2/apmtelemetry",
            request_headers=["dd-agent-hostname", "dd-agent-env", "datadog-container-id"],
        )

    def test_seq_id(self):
        """Test that messages are sent sequentially"""
        interfaces.library.assert_seq_ids_are_roughly_sequential()
        interfaces.library.assert_no_skipped_seq_ids()

    def test_app_started(self):
        """Request type app-started is sent on startup"""
        interfaces.library.assert_send_app_started()

    def test_telemetry_messages_valid(self):
        """Telemetry messages additional validation"""
        interfaces.library.assert_telemetry_messages_valid()

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
