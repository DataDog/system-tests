from utils import scenarios


@scenarios.test_the_test
class Test_Decorator:
    def test_allow_several(self):
        @scenarios.integrations
        @scenarios.apm_tracing_e2e
        class Test_Dbm:
            pass
