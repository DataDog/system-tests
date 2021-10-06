from utils import BaseTestCase, context, interfaces, skipif


@skipif(not context.appsec_is_released, reason=context.appsec_not_released_reason)
class Test_Metrics(BaseTestCase):
    @skipif(context.library == "dotnet", reason="missing feature")
    @skipif(context.library == "java", reason="missing feature")
    def test_waf_eval_ms(self):
        """ Appsec reports _dd.appsec.waf_eval_ms """
        interfaces.library.assert_metric_existence("_dd.appsec.waf_eval_ms")
        interfaces.agent.assert_metric_existence("_dd.appsec.waf_eval_ms")

    def test_no_overbudget(self):
        """ There is no Appsec process over time budget """
        interfaces.library.assert_metric_absence("_dd.appsec.waf_overtime_ms")


@skipif(not context.appsec_is_released, reason=context.appsec_not_released_reason)
@skipif(context.library == "java", reason="missing feature: response is not reported")
class Test_StatusCode(BaseTestCase):
    def test_basic(self):
        """ Appsec reports good status code """
        r = self.weblog_get("/path_that_doesn't_exists/", headers={"User-Agent": "Arachni/v1"})
        assert r.status_code == 404
        interfaces.library.assert_waf_attack(r)

        def check_http_code(event):
            status_code = event["context"]["http"]["response"]["status"]
            assert status_code == 404, f"404 should have been reported, not {status_code}"

            return True

        interfaces.library.add_appsec_validation(r, check_http_code)


@skipif(not context.appsec_is_released, reason=context.appsec_not_released_reason)
class Test_HTTPHeaders(BaseTestCase):
    @staticmethod
    def _check_header_is_present(header_name):
        def inner_check(event):
            assert header_name.lower() in [
                n.lower() for n in event["context"]["http"]["request"]["headers"].keys()
            ], f"header {header_name} not reported"

        return inner_check

    def test_x_forwarded_for(self):
        """ AppSec reports the X-Forwarded-For HTTP header """
        r = self.weblog_get(
            "/waf/", headers={"X-Forwarded-For": "42.42.42.42, 43.43.43.43", "User-Agent": "Arachni/v1"}
        )
        interfaces.library.add_appsec_validation(r, self._check_header_is_present("x-forwarded-for"))

    def test_x_client_ip(self):
        """ AppSec reports the X-Client-IP HTTP header """
        r = self.weblog_get("/waf/", headers={"X-Client-IP": "42.42.42.42, 43.43.43.43", "User-Agent": "Arachni/v1"})
        interfaces.library.add_appsec_validation(r, self._check_header_is_present("x-client-ip"))

    def test_x_real_ip(self):
        """ AppSec reports the X-Real-IP HTTP header """
        r = self.weblog_get("/waf/", headers={"X-Real-IP": "42.42.42.42, 43.43.43.43", "User-Agent": "Arachni/v1"})
        interfaces.library.add_appsec_validation(r, self._check_header_is_present("x-real-ip"))

    def test_x_forwarded(self):
        """ AppSec reports the X-Forwarded HTTP header """
        r = self.weblog_get("/waf/", headers={"X-Forwarded": "42.42.42.42, 43.43.43.43", "User-Agent": "Arachni/v1"})
        interfaces.library.add_appsec_validation(r, self._check_header_is_present("x-forwarded"))

    def test_x_cluster_client_ip(self):
        """ AppSec reports the X-Cluster-Client-IP HTTP header """
        r = self.weblog_get(
            "/waf/", headers={"X-Cluster-Client-IP": "42.42.42.42, 43.43.43.43", "User-Agent": "Arachni/v1"}
        )
        interfaces.library.add_appsec_validation(r, self._check_header_is_present("x-cluster-client-ip"))

    def test_forwarded_for(self):
        """ AppSec reports the Forwarded-For HTTP header """
        r = self.weblog_get("/waf/", headers={"Forwarded-For": "42.42.42.42, 43.43.43.43", "User-Agent": "Arachni/v1"})
        interfaces.library.add_appsec_validation(r, self._check_header_is_present("forwarded-for"))

    def test_forwarded(self):
        """ AppSec reports the Forwarded HTTP header """
        r = self.weblog_get("/waf/", headers={"Forwarded": "42.42.42.42, 43.43.43.43", "User-Agent": "Arachni/v1"})
        interfaces.library.add_appsec_validation(r, self._check_header_is_present("forwarded"))

    def test_via(self):
        """ AppSec reports the Via HTTP header """
        r = self.weblog_get("/waf/", headers={"Via": "42.42.42.42, 43.43.43.43", "User-Agent": "Arachni/v1"})
        interfaces.library.add_appsec_validation(r, self._check_header_is_present("via"))

    def test_true_client_ip(self):
        """ AppSec reports the True-Client-IP HTTP header """
        r = self.weblog_get("/waf/", headers={"True-Client-IP": "42.42.42.42, 43.43.43.43", "User-Agent": "Arachni/v1"})
        interfaces.library.add_appsec_validation(r, self._check_header_is_present("true-client-ip"))
