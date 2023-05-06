import pytest

from utils import missing_feature, context, scenarios
from utils.tools import logger


@scenarios.onboarding
class Test_Onboarding:
    def test_one(self, client):
        logger.info(f"DONE:: {client.ip}")
