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
        requests = []
        for i in range(1, 11):
            r = weblog.request(method="GET", path=f"/iast/sampling-by-route-method-count/{i}?param=value{i}")
            requests.append(r)
            r = weblog.request(method="GET", path=f"/iast/sampling-by-route-method-count-2/{i}?param=value{i}")
            requests.append(r)
            r = weblog.request(
                method="POST", path=f"/iast/sampling-by-route-method-count/{i}", data={"param": f"value{i}"}
            )
            requests.append(r)

        self.requests = requests

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

        assert len(vuln_hash_set) >= 45, (
            f"Invalid number of vulnerabilities: {vuln_debug_list}"
        )  # Bigger or equal, because unrelated extra vulns could be detected in the app
