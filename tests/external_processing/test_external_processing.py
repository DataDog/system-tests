from utils import weblog, interfaces

@scenarios.external_processing
class Test_ExternalProcessing:
    def setup_main(self):
        self.r = weblog.get("/mock", params={"status_code": 200}, proxy="http:envoy:10000")

    def test_main(self):
        assert self.r.status_code == 200

        traces = interfaces.library.get_traces()

        assert len(traces) == 1
        # test whatever you like
        assert traces[0]["request"]["url"] == "http://envoy:10000/mock?status_code=200"