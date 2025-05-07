from utils import features
from tests.appsec.iast.utils import get_iast_event
from utils import weblog

@features.iast_vuln_sampling_route_method_count_algorithm
class TestSamplingByRouteMethodCount:
    def setup_sampling_by_route_method_count(self):
        # Endpoint expect 15 vulnerabilities with different hashes
        # vulnerability types don't matter
        # Each request expect some vulnerabilities or no vulns, but at the end all the vulnerabilities must be there
        
        r1 = weblog.request(method="GET", path="/iast/sampling-by-route-method-count")
        r2 = weblog.request(method="GET", path="/iast/sampling-by-route-method-count")
        r3 = weblog.request(method="GET", path="/iast/sampling-by-route-method-count")
        r4 = weblog.request(method="GET", path="/iast/sampling-by-route-method-count")
        r5 = weblog.request(method="GET", path="/iast/sampling-by-route-method-count")
        r6 = weblog.request(method="GET", path="/iast/sampling-by-route-method-count")
        r7 = weblog.request(method="GET", path="/iast/sampling-by-route-method-count")
        r8 = weblog.request(method="GET", path="/iast/sampling-by-route-method-count")
        r9 = weblog.request(method="GET", path="/iast/sampling-by-route-method-count")
        r10 = weblog.request(method="GET", path="/iast/sampling-by-route-method-count")
        self.requests = [r1, r2, r3, r4, r5, r6, r7, r8, r9, r10]

    def test_sampling_by_route_method_count(self):
        vuln_hash_set = set()
        vuln_type_count = dict()

        for r in self.requests:
            iast = None
            try:
                iast = get_iast_event(r)
            except Exception as e:
                continue

            if iast["vulnerabilities"]:
                assert len(iast["vulnerabilities"]) < 15 # Vulns are sampled, so not all of them are present

                for vuln in iast["vulnerabilities"]:
                    hash = vuln["hash"]
                    vuln_hash_set.add(hash)

        assert len(vuln_hash_set) >= 15 # Bigger or equal, because unrelated extra vulns could be detected in the app
