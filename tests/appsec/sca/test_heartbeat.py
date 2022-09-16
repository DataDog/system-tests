import string
from utils import BaseTestCase, interfaces
from utils.tools import logger


class Test_SCA_heartbeat(BaseTestCase):
    def test_status_ok(self):
        """Test a heartbeat is sent"""

        interfaces.library.expected_timeout = 90
        interfaces.library.add_heartbeat_validation(1)
        interfaces.agent.expected_timeout = 60
        interfaces.agent.add_heartbeat_validation(2)
