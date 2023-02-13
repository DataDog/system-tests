from utils import weblog, interfaces, rfc, scenario


@rfc("https://datadoghq.atlassian.net/browse/ATI-2419?focusedCommentId=956826")
@scenario("APM_TRACING_E2E_SINGLE_SPAN")
class Test_SingleSpan:
    """This is a test that exercises the Single Span Ingestion Control feature.
    Read more about Single Span at https://datadoghq.atlassian.net/wiki/spaces/APM/pages/2564915820/Trace+Ingestion+Mechanisms#Single-Span-Ingestion-Control

    Past incident: https://app.datadoghq.com/incidents/18687
    """

    def setup_main(self):
        self.parentSubmitted = weblog.get("/e2e_single_span?parentName=parent.span.single_span_submitted&childName=child.span")
        self.childSubmitted = weblog.get("/e2e_single_span?parentName=parent.span&childName=child.span.single_span_submitted")

    def test_main(self):
        traceWithParent = interfaces.backend.assert_trace_exists(self.parentSubmitted)
        traceWithChild = interfaces.backend.assert_trace_exists(self.childSubmitted)
