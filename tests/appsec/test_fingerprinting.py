from utils import features
from utils import interfaces
from utils import rfc
from utils import weblog

ARACHNI_HEADERS = {"User-Agent": "Arachni/v1.5.1"}
DD_BLOCK_HEADERS = {"User-Agent": "dd-test-scanner-log-block"}


def get_span_meta(r):
    res = [span.get("meta", {}) for _, _, span in interfaces.library.get_spans(request=r)]
    assert res, f"no spans found in {r}"
    return res


@rfc("https://docs.google.com/document/d/1DivOa9XsCggmZVzMI57vyxH2_EBJ0-qqIkRHm_sEvSs/edit#heading=h.88xvn2cvs9dt")
@features.fingerprinting
class Test_Fingerprinting_Header_And_Network:
    def setup_fingerprinting_network(self):
        self.r = weblog.get("/", headers=ARACHNI_HEADERS)
        self.n = weblog.get("/")

    def test_fingerprinting_network(self):
        assert self.r.status_code == 200
        assert self.n.status_code == 200
        assert all("_dd.appsec.fp.http.network" in m for m in get_span_meta(self.r))
        assert all("_dd.appsec.fp.http.network" not in m for m in get_span_meta(self.n))

    def setup_fingerprinting_header(self):
        self.r = weblog.get("/", headers=ARACHNI_HEADERS)
        self.n = weblog.get("/")

    def test_fingerprinting_header(self):
        assert self.r.status_code == 200
        assert self.n.status_code == 200
        assert all("_dd.appsec.fp.http.header" in m for m in get_span_meta(self.r))
        assert all("_dd.appsec.fp.http.header" not in m for m in get_span_meta(self.n))

    def setup_fingerprinting_network_block(self):
        self.r = weblog.get("/", headers=DD_BLOCK_HEADERS)

    def test_fingerprinting_network_block(self):
        assert self.r.status_code == 403
        assert all("_dd.appsec.fp.http.network" in m for m in get_span_meta(self.r))

    def setup_fingerprinting_header_block(self):
        self.r = weblog.get("/", headers=DD_BLOCK_HEADERS)

    def test_fingerprinting_header_block(self):
        assert self.r.status_code == 403
        assert all("_dd.appsec.fp.http.header" in m for m in get_span_meta(self.r))


@rfc("https://docs.google.com/document/d/1DivOa9XsCggmZVzMI57vyxH2_EBJ0-qqIkRHm_sEvSs/edit#heading=h.88xvn2cvs9dt")
@features.fingerprinting
class Test_Fingerprinting_Endpoint:
    def setup_fingerprinting_endpoint(self):
        self.r = weblog.post("tag_value/value/200?x=3", data={"x": "this_is_not_an_attack"}, headers=ARACHNI_HEADERS,)
        self.n = weblog.post("tag_value/value/200?x=3", data={"x": "this_is_not_an_attack"},)

    def test_fingerprinting_endpoint(self):
        assert self.r.status_code == 200
        assert self.n.status_code == 200
        assert all("_dd.appsec.fp.http.endpoint" in m for m in get_span_meta(self.r))
        assert all("_dd.appsec.fp.http.endpoint" not in m for m in get_span_meta(self.n))
