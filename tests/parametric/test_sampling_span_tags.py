from utils import scenarios
from utils.parametric.spec.trace import MANUAL_DROP_KEY  # noqa
from utils.parametric.spec.trace import SAMPLING_DECISION_MAKER_KEY  # noqa
from utils.parametric.spec.trace import SAMPLING_PRIORITY_KEY  # noqa
from utils.parametric.spec.trace import Span  # noqa
from utils.parametric.spec.trace import find_span_in_traces  # noqa


@scenarios.parametric
class Test_Sampling_Span_Tags:
    def test_decision_maker_tag_inheritance_child_dropped_sst001(self, test_agent, test_library):
        with test_library:
            with test_library.start_span(name="parent", service="webserver") as parent:
                with test_library.start_span(name="child", parent_id=parent.span_id, service="webserver") as child:
                    child.set_meta(MANUAL_DROP_KEY, None)
        traces = test_agent.wait_for_num_traces(1)
        parent_span = find_span_in_traces(traces, Span(name="parent", service="webserver"))
        child_span = find_span_in_traces(traces, Span(name="child", service="webserver"))

        assert child_span["meta"].get(SAMPLING_DECISION_MAKER_KEY) is None
        assert parent_span["meta"].get(SAMPLING_DECISION_MAKER_KEY) is None
        assert parent_span["metrics"].get(SAMPLING_PRIORITY_KEY) == -1
        assert parent_span["metrics"].get("_dd.agent_psr") == 1
