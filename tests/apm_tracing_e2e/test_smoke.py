from utils import weblog, interfaces, rfc, scenarios


@rfc(
    "https://docs.google.com/document/d/1MtSlvPCKWM4x4amOYAvlKVbJjd0b0oUXxxlX-lo8KN8/edit#"
)
@scenarios.apm_tracing_e2e
class Test_Backend:
    """This is a smoke test that exercises the full flow of APM Tracing.
    It includes trace submission, the trace flowing through the backend processing,
    and then finally successfully fetching the final trace from the API.
    """

    def setup_main(self):
        self.r = weblog.get("/")

    def test_main(self):
        trace = interfaces.backend.assert_library_traces_exist(self.r)
