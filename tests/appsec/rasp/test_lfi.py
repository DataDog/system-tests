from utils import features, weblog, interfaces, scenarios, rfc


@rfc("https://docs.google.com/document/d/1vmMqpl8STDk7rJnd3YBsa6O9hCls_XHHdsodD61zr_4/edit#heading=h.tonjsgarlieo")
@features.rasp_local_file_inclusion
@scenarios.appsec_rasp
class Test_LFI:
    def setup_lfi(self):
        # TODO : document this endpoint in docs/weblog
        self.r = weblog.get("/rasp/lfi", params={"file": "injection_pattern.txt"})

    def test_lfi(self):
        assert self.r.status_code == 403
        assert self.r.text == "Blocked by RASP"  # TODO

        for span in interfaces.library.get_spans(request=self.r):
            if "_dd.appsec.json" in span["meta"]:
                data = span["meta"]["_dd.appsec.json"]

                assert "RASP" in data  # TODO

        # for a later PR, do something like
        # interfaces.library.assert_rasp_attack(self.r, attack_code="LFI")
