from utils import weblog, interfaces, scenarios


@scenarios.external_processing
class Test_ExternalProcessing:
    def setup_main(self):
        self.r = weblog.get("/mock", params={"status_code": 200})

    def test_main(self):
        assert self.r.status_code == 200

        interfaces.library.assert_trace_exists(self.r)

        for _, span in interfaces.library.get_root_spans(request=self.r):
            assert span["meta"]["http.url"] == "http://localhost:7777/mock?status_code=200"
