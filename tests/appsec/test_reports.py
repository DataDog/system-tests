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
