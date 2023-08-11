from utils import flaky, scenarios
from utils.parametric.spec.trace import MANUAL_DROP_KEY  # noqa
from utils.parametric.spec.trace import SAMPLING_AGENT_PRIORITY_RATE  # noqa
from utils.parametric.spec.trace import SAMPLING_DECISION_MAKER_KEY  # noqa
from utils.parametric.spec.trace import SAMPLING_PRIORITY_KEY  # noqa
from utils.parametric.spec.trace import Span  # noqa
from utils.parametric.spec.trace import find_span_in_traces  # noqa


@flaky(True, library="php", reason="I don't know")
@flaky(True, library="cpp")
@flaky(True, library="ruby")
@scenarios.parametric
class Test_Sampling_Span_Tags:
    def test_decision_maker_tag_inheritance_child_dropped_sst001(self, test_agent, test_library):
        with test_library:
            with test_library.start_span(name="parent", service="webserver") as parent_span:
                with test_library.start_span(
                    name="child", service="webserver", parent_id=parent_span.span_id
                ) as child_span:
                    child_span.set_meta(MANUAL_DROP_KEY, None)

        traces = test_agent.wait_for_num_spans(2, clear=True)

        parent_span = find_span_in_traces(traces, Span(name="parent", service="webserver"))
        child_span = find_span_in_traces(traces, Span(name="child", service="webserver"))

        assert child_span["meta"].get(SAMPLING_DECISION_MAKER_KEY) is None

        assert parent_span["meta"].get(SAMPLING_DECISION_MAKER_KEY) == -1
        # dotnet sets this to -0
        # java sets this to -1
        # golang sets this to -1

        assert parent_span["metrics"].get(SAMPLING_PRIORITY_KEY) == 1
        # dotnet sets this to 1.0
        # golang sets this to 1.0
        # java sets this to 1

        assert parent_span["metrics"].get(SAMPLING_AGENT_PRIORITY_RATE) == 1
        # nodejs sets this to None
