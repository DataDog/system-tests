import pytest

from utils import missing_feature, context, scenarios
from utils.tools import logger


@scenarios.onboarding_host_container
@scenarios.onboarding_host
class Test_Onboarding:
    def test_one(self, onboardig_vm):
        logger.info(f"DONE:: {onboardig_vm.ip}-{onboardig_vm.name}")
