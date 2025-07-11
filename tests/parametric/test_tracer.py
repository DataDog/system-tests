import pytest

from utils.parametric.spec.trace import find_trace
from utils.parametric.spec.trace import find_span
from utils.parametric.spec.trace import find_first_span_in_trace_payload
from utils.parametric.spec.trace import find_root_span
from utils import missing_feature, context, rfc, scenarios, features

from .conftest import _TestAgentAPI
from .conftest import APMLibrary


parametrize = pytest.mark.parametrize


@scenarios.parametric
@features.trace_annotation
class Test_Tracer:
    @missing_feature(context.library == "cpp", reason="metrics cannot be set manually")
    @missing_feature(context.library == "nodejs", reason="nodejs overrides the manually set service name")
    def test_tracer_span_top_level_attributes(self, test_agent: _TestAgentAPI, test_library: APMLibrary) -> None:
        """Do a simple trace to ensure that the test client is working properly."""
        with (
            test_library,
            test_library.dd_start_span(
                "operation", service="my-webserver", resource="/endpoint", typestr="web"
            ) as parent,
        ):
            parent.set_metric("number", 10)
            with test_library.dd_start_span("operation.child", parent_id=parent.span_id) as child:
                child.set_meta("key", "val")

        traces = test_agent.wait_for_num_traces(1, sort_by_start=False)
        trace = find_trace(traces, parent.trace_id)
        assert len(trace) == 2

        root_span = find_span(trace, parent.span_id)
        assert root_span["name"] == "operation"
        assert root_span["service"] == "my-webserver"
        assert root_span["resource"] == "/endpoint"
        assert root_span["type"] == "web"
        assert root_span["metrics"]["number"] == 10
        child_span = find_span(trace, child.span_id)
        assert child_span["name"] == "operation.child"
        assert child_span["meta"]["key"] == "val"


@rfc("https://docs.google.com/document/d/1vxuRUNzHqd6sp1lnF3T383acbLrG0R-xDGi8cdZ4cs8/edit")
@scenarios.parametric
@features.embeded_git_reference
class Test_TracerSCITagging:
    @parametrize("library_env", [{"DD_GIT_REPOSITORY_URL": "https://github.com/DataDog/dd-trace-go"}])
    def test_tracer_repository_url_environment_variable(
        self, library_env: dict[str, str], test_agent: _TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """When DD_GIT_REPOSITORY_URL is specified
        When a trace chunk is emitted
            The first span of the trace chunk should have the value of DD_GIT_REPOSITORY_URL
            in meta._dd.git.repository_url
        """
        with (
            test_library,
            test_library.dd_start_span("operation") as parent,
            test_library.dd_start_span("operation.child", parent_id=parent.span_id),
        ):
            pass

        traces = test_agent.wait_for_num_traces(1, sort_by_start=False)
        trace = find_trace(traces, parent.trace_id)
        assert len(trace) == 2

        first_span = find_first_span_in_trace_payload(trace)
        # the repository url should be injected ONLY in the first span of the trace
        spans_with_git = [span for span in trace if span.get("meta", {}).get("_dd.git.repository_url")]
        assert len(spans_with_git) == 1
        assert first_span == spans_with_git[0]
        assert first_span["meta"]["_dd.git.repository_url"] == library_env["DD_GIT_REPOSITORY_URL"]

    @parametrize("library_env", [{"DD_GIT_COMMIT_SHA": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}])
    def test_tracer_commit_sha_environment_variable(
        self, library_env: dict[str, str], test_agent: _TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """When DD_GIT_COMMIT_SHA is specified
        When a trace chunk is emitted
            The first span of the trace chunk should have the value of DD_GIT_COMMIT_SHA
            in meta._dd.git.commit.sha
        """
        with (
            test_library,
            test_library.dd_start_span("operation") as parent,
            test_library.dd_start_span("operation.child", parent_id=parent.span_id),
        ):
            pass

        traces = test_agent.wait_for_num_traces(1, sort_by_start=False)
        trace = find_trace(traces, parent.trace_id)
        assert len(trace) == 2

        first_span = find_first_span_in_trace_payload(trace)
        # the repository url should be injected ONLY in the first span of the trace
        spans_with_git = [span for span in trace if span.get("meta", {}).get("_dd.git.commit.sha")]
        assert len(spans_with_git) == 1
        assert first_span == spans_with_git[0]

        assert first_span["meta"]["_dd.git.commit.sha"] == library_env["DD_GIT_COMMIT_SHA"]

    @parametrize(
        "library_env",
        [
            {
                "DD_GIT_REPOSITORY_URL": "https://gitlab-ci-token:AAA_bbb@gitlab.com/DataDog/systems-test.git",
                "expected_repo_url": "https://gitlab.com/DataDog/systems-test.git",
            },
            {
                "DD_GIT_REPOSITORY_URL": "ssh://gitlab-ci-token:AAA_bbb@gitlab.com/DataDog/systems-test.git",
                "expected_repo_url": "ssh://gitlab.com/DataDog/systems-test.git",
            },
            {
                "DD_GIT_REPOSITORY_URL": "https://token@gitlab.com/user/project.git",
                "expected_repo_url": "https://gitlab.com/user/project.git",
            },
            {
                "DD_GIT_REPOSITORY_URL": "ssh://token@gitlab.com/user/project.git",
                "expected_repo_url": "ssh://gitlab.com/user/project.git",
            },
            {
                "DD_GIT_REPOSITORY_URL": "https://gitlab.com/DataDog/systems-test.git",
                "expected_repo_url": "https://gitlab.com/DataDog/systems-test.git",
            },
            {
                "DD_GIT_REPOSITORY_URL": "gitlab.com/DataDog/systems-test.git",
                "expected_repo_url": "gitlab.com/DataDog/systems-test.git",
            },
            {
                "DD_GIT_REPOSITORY_URL": "git@github.com:user/project.git",
                "expected_repo_url": "git@github.com:user/project.git",
            },
        ],
    )
    @missing_feature(context.library == "nodejs", reason="nodejs does not strip credentials yet")
    def test_tracer_repository_url_strip_credentials(
        self, library_env: dict[str, str], test_agent: _TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """When DD_GIT_REPOSITORY_URL is specified
        When a trace chunk is emitted
            The first span of the trace chunk should have the value of DD_GIT_REPOSITORY_URL
            in meta._dd.git.repository_url, with credentials removed if any
        """
        with (
            test_library,
            test_library.dd_start_span("operation") as parent,
            test_library.dd_start_span("operation.child", parent_id=parent.span_id),
        ):
            pass

        traces = test_agent.wait_for_num_traces(1, sort_by_start=False)
        trace = find_trace(traces, parent.trace_id)
        first_span = find_first_span_in_trace_payload(trace)

        assert first_span["meta"]["_dd.git.repository_url"] == library_env["expected_repo_url"]


@scenarios.parametric
@features.dd_service_mapping
class Test_TracerUniversalServiceTagging:
    @missing_feature(reason="FIXME: library test client sets empty string as the service name")
    @parametrize("library_env", [{"DD_SERVICE": "service1"}])
    def test_tracer_service_name_environment_variable(
        self, library_env: dict[str, str], test_agent: _TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """When DD_SERVICE is specified
        When a span is created
            The span should use the value of DD_SERVICE for span.service
        """
        with test_library, test_library.dd_start_span("operation") as root:
            pass

        traces = test_agent.wait_for_num_traces(1, sort_by_start=False)
        trace = find_trace(traces, root.trace_id)
        span = find_root_span(trace)
        assert span is not None, "Root span not found"
        assert span["name"] == "operation"
        assert span["service"] == library_env["DD_SERVICE"]

    @parametrize("library_env", [{"DD_ENV": "prod"}])
    def test_tracer_env_environment_variable(
        self, library_env: dict[str, str], test_agent: _TestAgentAPI, test_library: APMLibrary
    ) -> None:
        """When DD_ENV is specified
        When a span is created
            The span should have the value of DD_ENV in meta.env
        """
        with test_library, test_library.dd_start_span("operation") as root:
            pass

        traces = test_agent.wait_for_num_traces(1, sort_by_start=False)
        trace = find_trace(traces, root.trace_id)

        span = find_root_span(trace)
        assert span is not None, "Root span not found"
        assert span["name"] == "operation"
        assert span["meta"]["env"] == library_env["DD_ENV"]
