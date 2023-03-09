from utils import context, interfaces, missing_feature, bug, released, weblog, scenarios


@released(python="1.7.0", dotnet="2.12.0", java="0.108.1", nodejs="3.2.0")
@bug(context.uds_mode and context.library < "nodejs@3.7.0")
@missing_feature(library="cpp")
@missing_feature(library="ruby")
@missing_feature(library="php")
@missing_feature(library="golang", reason="Implemented but not merged in master")
class Test_ForceBatchingEnabled:
    def setup_message_batch_event_order(self):
        weblog.get("/load_dependency")
        weblog.get("/enable_integration")
        weblog.get("/enable_product")

    @missing_feature(
        context.library in ("dotnet", "nodejs", "java", "python"),
        reason="DD_FORCE_BATCHING_ENABLE is not implemented yet.",
    )
    @scenarios.telemetry_message_batch_event_order
    def test_message_batch_event_order(self):
        """Test that the events in message-batch are in chronological order"""
        eventslist = []
        for data in interfaces.library.get_telemetry_data():
            content = data["request"]["content"]
            eventslist.append(content.get("request_type"))

        assert (
            eventslist.index("app-dependencies-loaded")
            < eventslist.index("app-integrations-change")
            < eventslist.index("app-product-change")
        ), "Events in message-batch are not in chronological order of event triggered"
