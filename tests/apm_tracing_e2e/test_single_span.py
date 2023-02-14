from utils import weblog, interfaces, rfc, scenario
from utils.tools import logger
from tests.apm_tracing_e2e.constants import SAMPLING_PRIORITY_KEY, SINGLE_SPAN_SAMPLING_MECHANISM, SINGLE_SPAN_SAMPLING_MECHANISM_VALUE, SINGLE_SPAN_SAMPLING_RATE, SINGLE_SPAN_SAMPLING_MAX_PER_SEC


@rfc("https://datadoghq.atlassian.net/browse/ATI-2419?focusedCommentId=956826")
@scenario("APM_TRACING_E2E_SINGLE_SPAN")
class Test_SingleSpan:
    """This is a test that exercises the Single Span Ingestion Control feature.
    Read more about Single Span at https://datadoghq.atlassian.net/wiki/spaces/APM/pages/2564915820/Trace+Ingestion+Mechanisms#Single-Span-Ingestion-Control

    Past incident: https://app.datadoghq.com/incidents/18687
    """

    def setup_main(self):
        self.reqForParent = weblog.get("/e2e_single_span?parentName=parent.span.single_span_submitted&childName=child.span")
        self.reqForChild = weblog.get("/e2e_single_span?parentName=parent.span&childName=child.span.single_span_submitted")

    def test_main(self):
        spansForParent = _get_spans_submitted(self.reqForParent)
        logger.debug(f"PARENT: {spansForParent}")
        # Only the parent span should be submitted to the backend!
        assert 1 == len(spansForParent), _assert_msg(1, len(spansForParent))

        # TODO - Call the backend!
        # traceWithParent = interfaces.backend.assert_traces_exist(self.reqForParent)

        # span = spansForParent[0]
        # assert span["name"] == "parent.span.single_span_submitted"
        # assert span.get("parentID") is None
        # assert span["metrics"][SAMPLING_PRIORITY_KEY] == -1  # due to the global sampling rate = 0
        # assert span["metrics"][SINGLE_SPAN_SAMPLING_RATE] == 1.0
        # assert span["metrics"][SINGLE_SPAN_SAMPLING_MECHANISM] == SINGLE_SPAN_SAMPLING_MECHANISM_VALUE
        # assert span["metrics"][SINGLE_SPAN_SAMPLING_MAX_PER_SEC] == 50.0
        

        spansForChild = _get_spans_submitted(self.reqForChild)
        logger.debug(f"CHILD: {spansForChild}")
        assert 1 == len(spansForChild), _assert_msg(1, len(spansForChild))

        # traceWithChild = interfaces.backend.assert_traces_exist(self.reqForChild)

        # span = spansForChild[0]
        # assert span["name"] == "child.span.single_span_submitted"
        # assert span["parentID"] is not None
        # assert span["metrics"][SAMPLING_PRIORITY_KEY] == -1  # due to the global sampling rate = 0
        # assert span["metrics"][SINGLE_SPAN_SAMPLING_RATE] == 1.0
        # assert span["metrics"][SINGLE_SPAN_SAMPLING_MECHANISM] == SINGLE_SPAN_SAMPLING_MECHANISM_VALUE
        # assert span["metrics"][SINGLE_SPAN_SAMPLING_MAX_PER_SEC] == 50.0

def _get_spans_submitted(request):
    return [span for _, _, _, span in interfaces.agent.get_spans(request)]

def _assert_msg(expected, actual):
    return f"\n\tExpected:\t{expected}\n\tActual:\t\t{actual}\n\n"
