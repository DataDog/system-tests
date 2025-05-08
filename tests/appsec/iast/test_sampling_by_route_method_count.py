from utils import features
from tests.appsec.iast.utils import get_iast_event
from utils import weblog
from utils._logger import logger


@features.iast_vuln_sampling_route_method_count_algorithm
class TestSamplingByRouteMethodCount:
    def setup_sampling_by_route_method_count(self):
        # Endpoint expect 15 vulnerabilities with different hashes
        # vulnerability types don't matter
        # Each request expect some vulnerabilities or no vulns, but at the end all the vulnerabilities must be there

        r1 = weblog.request(method="GET", path="/iast/sampling-by-route-method-count/1/?param=value01")
        r2 = weblog.request(method="GET", path="/iast/sampling-by-route-method-count/2/?param=value02")
        r3 = weblog.request(method="GET", path="/iast/sampling-by-route-method-count/3/?param=value03")
        r4 = weblog.request(method="GET", path="/iast/sampling-by-route-method-count/4/?param=value04")
        r5 = weblog.request(method="GET", path="/iast/sampling-by-route-method-count/5/?param=value05")
        r6 = weblog.request(method="GET", path="/iast/sampling-by-route-method-count/6/?param=value06")
        r7 = weblog.request(method="GET", path="/iast/sampling-by-route-method-count/7/?param=value07")
        r8 = weblog.request(method="GET", path="/iast/sampling-by-route-method-count/8/?param=value08")
        r9 = weblog.request(method="GET", path="/iast/sampling-by-route-method-count/9/?param=value09")
        r10 = weblog.request(method="GET", path="/iast/sampling-by-route-method-count/10/?param=value10")
        self.requests = [r1, r2, r3, r4, r5, r6, r7, r8, r9, r10]

    def test_sampling_by_route_method_count(self):
        vuln_hash_set = set()
        vuln_debug_list = []

        for r in self.requests:
            iast = None
            try:
                iast = get_iast_event(r)
                assert isinstance(iast, dict)
            except Exception:
                logger.debug("No iast event found in request")
                continue

            if iast["vulnerabilities"] is not None:
                vuln_debug_list.append(iast["vulnerabilities"])
                assert len(iast["vulnerabilities"]) < 15  # Vulns are sampled, so not all of them are present

                for vuln in iast["vulnerabilities"]:
                    vulnerability_hash = vuln["hash"]
                    vuln_hash_set.add(vulnerability_hash)

        assert len(vuln_hash_set) >= 15, f"Invalid number of vulnerabilities: {vuln_debug_list}"  # Bigger or equal, because unrelated extra vulns could be detected in the app
