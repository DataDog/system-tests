import pytest
from utils import scenarios


@scenarios.test_the_test
class Test_Decorator:
    def test_uniqueness(self):

        with pytest.raises(ValueError):

            @scenarios.integrations
            @scenarios.apm_tracing_e2e
            class Test_Dbm:
                pass
