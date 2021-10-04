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
