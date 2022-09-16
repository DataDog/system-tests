import string
from utils import BaseTestCase, interfaces
from utils.tools import logger


class Test_SCA_libraries(BaseTestCase):
    def test_libraries_ok(self):
        """Test libraries are sent"""

        def validator(data):
            request = data["request"]
            type = request["content"]["request_type"]

            if type == "app-started":
                logger.debug("Test_SCA_libraries: app-started message found. Validating if libraries are sent")
                dependencies = request["content"]["payload"]["dependencies"]
                # Pending to clarify: In theory it uses both events, but in practice, tracer didn't have dependencies at the app-started moment yet.
                # So in real life it sends deps in dependencies-loaded event
                # assert dependencies != string.empty
            elif type == "app-dependencies-loaded":
                logger.debug(
                    "Test_SCA_libraries: app-dependencies-loaded message found. Validating if libraries are sent"
                )
                dependencies = request["content"]["payload"]["dependencies"]
                assert dependencies != string.empty

        interfaces.library.add_telemetry_validation(validator, is_success_on_expiry=True)
        interfaces.agent.add_telemetry_validation(validator, is_success_on_expiry=True)
