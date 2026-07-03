import json
import pytest

from .conftest import APMLibrary
from .test_library_tracestats import enable_tracestats
from utils.docker_fixtures import TestAgentAPI
from utils import scenarios, features

# TODO:
# - tag normalization


def enable_trace_filters(
    reject: list[str] | None = None,
    require: list[str] | None = None,
    reject_regex: list[str] | None = None,
    require_regex: list[str] | None = None,
    ignore_resources: list[str] | None = None,
) -> pytest.MarkDecorator:
    """Sets the agent trace filters in /info and its version to the minimum supported version for client-side stats."""
    agent_version = "7.65.0"
    reject = reject or []
    require = require or []
    reject_regex = reject_regex or []
    require_regex = require_regex or []
    ignore_resources = ignore_resources or []
    extra_info = {
        "filter_tags": {"reject": reject, "require": require},
        "filter_tags_regex": {"reject": reject_regex, "require": require_regex},
        "ignore_resources": ignore_resources,
    }
    agent_env_config = {
        "TEST_AGENT_VERSION": agent_version,
        "DD_AGENT_EXTRA_INFO": json.dumps(extra_info),
    }
    return pytest.mark.parametrize("agent_env", [agent_env_config])


@scenarios.parametric
@features.client_side_stats_supported
class Test_Trace_Filters:
    @enable_tracestats()
    @enable_trace_filters(reject=["reject_tag:true"])
    def test_trace_filters_reject(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        with test_library, test_library.dd_start_span(name="web.request", tags=[("reject_tag", "true")]):
            pass
        assert not test_agent.traces(), (
            "Trace should have been rejected because it has the reject_tag:true tag configured in trace filters"
        )
        assert not test_agent.get_v06_stats_requests(), (
            "Trace filters are applied before stats, therefore a filtered trace should not produce stats"
        )

    @enable_tracestats()
    @enable_trace_filters(require=["require_tag:true"])
    def test_trace_filters_require(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        with test_library, test_library.dd_start_span(name="web.request", tags=[("require_tag", "true")]):
            pass
        assert len(test_agent.traces()) == 1
        # Not testing that CSS here so we don't check that we received stats

    @enable_tracestats()
    @enable_trace_filters(reject=["reject_tag"])
    def test_trace_filters_reject_no_value(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        with test_library, test_library.dd_start_span(name="web.request", tags=[("reject_tag", "anything")]):
            pass
        assert not test_agent.traces()
        assert not test_agent.get_v06_stats_requests()

    @enable_tracestats()
    @enable_trace_filters(reject_regex=["reject_tag:.*true.*"])
    def test_trace_filters_reject_regex(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        with (
            test_library,
            test_library.dd_start_span(name="web.request", tags=[("reject_tag", "something true something")]),
        ):
            pass
        assert not test_agent.traces()
        assert not test_agent.get_v06_stats_requests()

    @enable_tracestats()
    @enable_trace_filters(require_regex=["require_tag:.*true.*"])
    def test_trace_filters_require_regex(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        with (
            test_library,
            test_library.dd_start_span(name="web.request", tags=[("require_tag", "something true something")]),
        ):
            pass
        assert len(test_agent.traces()) == 1

    @enable_tracestats()
    @enable_trace_filters(ignore_resources=[".*ignored.*"])
    def test_trace_filters_ignore_resources(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        with (
            test_library,
            test_library.dd_start_span(name="web.request", resource="this is an ignored span because of its resource"),
        ):
            pass
        assert not test_agent.traces()
        assert not test_agent.get_v06_stats_requests()

    @enable_tracestats()
    @enable_trace_filters(reject_regex=["reject_tag:[invalid"])
    def test_trace_filters_invalid_reject_regex(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Invalid tags are dropped so the trace is kept"""
        with (
            test_library,
            test_library.dd_start_span(name="web.request", tags=[("reject_tag", "[invalid")]),
        ):
            pass
        assert len(test_agent.traces()) == 1

    @enable_tracestats()
    @enable_trace_filters(reject=[" \treject_tag \t:\t true\t "])
    def test_trace_filters_trim(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        with (
            test_library,
            test_library.dd_start_span(name="web.request", tags=[("reject_tag", "true")]),
        ):
            pass
        assert not test_agent.traces()
        assert not test_agent.get_v06_stats_requests()

    @enable_tracestats()
    @enable_trace_filters(ignore_resources=["web.request"])
    def test_trace_filters_resource_normalization(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Test that resource normalization happens before tag filters: empty resources are replaced with span's name"""
        with (
            test_library,
            test_library.dd_start_span(name="web.request", resource=""),
        ):
            pass
        assert not test_agent.traces()
        assert not test_agent.get_v06_stats_requests()

    @enable_tracestats()
    @enable_trace_filters(reject=["http.status_code:999"])
    def test_trace_filters_tag_normalization_http_status_code(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Test that resource normalization happens before tag filters: invalid http.status_code tags are ignored"""
        with (
            test_library,
            test_library.dd_start_span(name="web.request", tags=[("http.status_code", "999")]),
        ):
            pass
        assert len(test_agent.traces()) == 1

    @enable_tracestats()
    @enable_trace_filters(reject=["env:prod_env"])
    def test_trace_filters_tag_normalization_env(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Test that resource normalization happens before tag filters: env tag is fully normalized"""
        with (
            test_library,
            test_library.dd_start_span(name="web.request", tags=[("env", "Prod Env")]),
        ):
            pass
        assert not test_agent.traces()
        assert not test_agent.get_v06_stats_requests()
