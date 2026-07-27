import json
import pytest

from .conftest import APMLibrary
from .utils import MIN_AGENT_VERSION_FOR_CSS, enable_tracestats
from utils.docker_fixtures import TestAgentAPI
from utils import scenarios, features


def enable_trace_filters(
    reject: list[str] | None = None,
    require: list[str] | None = None,
    reject_regex: list[str] | None = None,
    require_regex: list[str] | None = None,
    ignore_resources: list[str] | None = None,
) -> pytest.MarkDecorator:
    """Configure agent-side trace filters and pin the test agent version.

    Filters are advertised in the test agent's /info response (via DD_AGENT_EXTRA_INFO) so the
    tracer applies them client-side. The agent version is pinned to the minimum that supports
    client-side stats according to the spec.
    """
    agent_version = MIN_AGENT_VERSION_FOR_CSS
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
    """Trace filters advertised by the agent's /info are applied client-side by the tracer.

    Each test configures filter_tags / filter_tags_regex / ignore_resources via enable_trace_filters
    and asserts the tracer drops or keeps the trace accordingly, before it is sent to the agent and
    before client-side stats are computed.
    """

    @enable_tracestats()
    @enable_trace_filters(reject=["reject_tag:true"])
    def test_trace_filters_reject(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """A reject filter drops traces whose root span has the matching tag."""
        with test_library, test_library.dd_start_span(name="web.request", tags=[("reject_tag", "true")]):
            pass
        assert not test_agent.traces(), (
            "Trace should have been rejected because it has the reject_tag:true tag configured in trace filters"
        )
        assert not test_agent.get_v06_stats_requests(), (
            "Trace filters are applied before stats, therefore a filtered trace should not produce stats"
        )

    @enable_tracestats()
    @enable_trace_filters(reject=["reject_tag:true"])
    def test_trace_filters_reject_non_matching_kept(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """A reject filter keeps traces that do not match it (guards against dropping everything)."""
        with test_library, test_library.dd_start_span(name="web.request", tags=[("reject_tag", "false")]):
            pass
        assert len(test_agent.traces()) == 1, "trace not matching the reject filter should be kept"

    @enable_tracestats()
    @enable_trace_filters(require=["require_tag:true"])
    def test_trace_filters_require(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """A require filter keeps traces whose root span has the required tag."""
        with test_library, test_library.dd_start_span(name="web.request", tags=[("require_tag", "true")]):
            pass
        assert len(test_agent.traces()) == 1, "trace with the required tag should be kept"
        # Not testing that CSS here so we don't check that we received stats

    @enable_tracestats()
    @enable_trace_filters(require=["require_tag:true"])
    def test_trace_filters_require_missing(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """A require filter drops traces whose root span lacks the required tag."""
        with test_library, test_library.dd_start_span(name="web.request"):
            pass
        assert not test_agent.traces(), "trace lacking the required tag should be dropped"

    @enable_tracestats()
    @enable_trace_filters(require_regex=["require_tag:.*true.*"])
    def test_trace_filters_require_regex_missing(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """A require_regex filter drops traces whose root span lacks a tag matching the regex."""
        with test_library, test_library.dd_start_span(name="web.request"):
            pass
        assert not test_agent.traces(), "trace lacking the required regex tag should be dropped"

    @enable_tracestats()
    @enable_trace_filters(reject=["reject_tag:true"])
    def test_trace_filters_reject_missing(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """A reject filter does not drop traces whose root span lacks the reject tag."""
        with test_library, test_library.dd_start_span(name="web.request"):
            pass
        assert len(test_agent.traces()) == 1, "trace lacking the reject tag should not be dropped"

    @enable_tracestats()
    @enable_trace_filters(reject_regex=["reject_tag:.*true.*"])
    def test_trace_filters_reject_regex_missing(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """A reject_regex filter does not drop traces whose root span lacks a tag matching the regex."""
        with test_library, test_library.dd_start_span(name="web.request"):
            pass
        assert len(test_agent.traces()) == 1, "trace lacking the reject regex tag should not be dropped"

    @enable_tracestats()
    @enable_trace_filters(reject=["reject_tag"])
    def test_trace_filters_reject_no_value(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """A key-only reject filter matches the tag regardless of its value."""
        with test_library, test_library.dd_start_span(name="web.request", tags=[("reject_tag", "anything")]):
            pass
        assert not test_agent.traces(), "trace should be rejected (key-only filter)"
        assert not test_agent.get_v06_stats_requests(), "rejected trace should not produce stats"

    @enable_tracestats()
    @enable_trace_filters(reject_regex=["reject_tag:.*true.*"])
    def test_trace_filters_reject_regex(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """A reject_regex filter drops traces whose tag value matches the regex."""
        with (
            test_library,
            test_library.dd_start_span(name="web.request", tags=[("reject_tag", "something true something")]),
        ):
            pass
        assert not test_agent.traces(), "trace should be rejected (regex match)"
        assert not test_agent.get_v06_stats_requests(), "rejected trace should not produce stats"

    @enable_tracestats()
    @enable_trace_filters(require_regex=["require_tag:.*true.*"])
    def test_trace_filters_require_regex(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """A require_regex filter keeps traces whose tag value matches the regex."""
        with (
            test_library,
            test_library.dd_start_span(name="web.request", tags=[("require_tag", "something true something")]),
        ):
            pass
        assert len(test_agent.traces()) == 1, "trace should be kept (regex match)"

    @enable_tracestats()
    @enable_trace_filters(ignore_resources=[".*ignored.*"])
    def test_trace_filters_ignore_resources(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """An ignore_resources filter drops traces whose resource matches the regex."""
        with (
            test_library,
            test_library.dd_start_span(name="web.request", resource="this is an ignored span because of its resource"),
        ):
            pass
        assert not test_agent.traces(), "trace should be rejected (resource ignored)"
        assert not test_agent.get_v06_stats_requests(), "rejected trace should not produce stats"

    @enable_tracestats()
    @enable_trace_filters(ignore_resources=[".*ignored.*"])
    def test_trace_filters_ignore_resources_non_matching_kept(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """An ignore_resources filter keeps traces whose resource does not match.

        Guards against a tracer that drops everything whenever any ignore filter is configured.
        """
        with (
            test_library,
            test_library.dd_start_span(name="web.request", resource="this resource is kept"),
        ):
            pass
        assert len(test_agent.traces()) == 1, "trace with a non-ignored resource should be kept"

    @enable_tracestats()
    @enable_trace_filters(reject_regex=["reject_tag:[invalid"])
    def test_trace_filters_invalid_reject_regex(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """An invalid regex filter spec is silently dropped, so the trace is kept."""
        with (
            test_library,
            test_library.dd_start_span(name="web.request", tags=[("reject_tag", "[invalid")]),
        ):
            pass
        assert len(test_agent.traces()) == 1, "trace kept: invalid regex filter is dropped"

    @enable_tracestats()
    @enable_trace_filters(reject=[" \treject_tag \t:\t true\t "])
    def test_trace_filters_trim(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Whitespace around the filter key/value is trimmed before matching."""
        with (
            test_library,
            test_library.dd_start_span(name="web.request", tags=[("reject_tag", "true")]),
        ):
            pass
        assert not test_agent.traces(), "trace should be rejected after trimming filter whitespace"
        assert not test_agent.get_v06_stats_requests(), "rejected trace should not produce stats"

    @enable_tracestats()
    @enable_trace_filters(ignore_resources=["web.request"])
    def test_trace_filters_resource_normalization(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Test that resource normalization happens before tag filters: empty resources are replaced with span's name"""
        with (
            test_library,
            test_library.dd_start_span(name="web.request", resource=""),
        ):
            pass
        assert not test_agent.traces(), "empty resource normalized to span name, then ignored"
        assert not test_agent.get_v06_stats_requests(), "rejected trace should not produce stats"

    @enable_tracestats()
    @enable_trace_filters(reject=["http.status_code:999"])
    def test_trace_filters_tag_normalization_http_status_code(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Tag normalization happens before tag filters: an out-of-range http.status_code (999) is
        dropped, so the reject filter finds no matching tag and the trace is kept.
        """
        with (
            test_library,
            test_library.dd_start_span(name="web.request", tags=[("http.status_code", "999")]),
        ):
            pass
        assert len(test_agent.traces()) == 1, "trace kept: invalid http.status_code tag is dropped"

    @enable_tracestats(extra_env={"DD_ENV": "Prod Env"})
    @enable_trace_filters(reject=["env:prod_env"])
    def test_trace_filters_tag_normalization_env(self, test_agent: TestAgentAPI, test_library: APMLibrary):
        """Test that the env tag is fully normalized before tag filters are applied"""
        with (
            test_library,
            test_library.dd_start_span(name="web.request"),
        ):
            pass
        assert not test_agent.traces(), "trace rejected: env tag normalized to match filter"
        assert not test_agent.get_v06_stats_requests(), "rejected trace should not produce stats"
