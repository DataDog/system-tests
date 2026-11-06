"""It's easy to forget to attach a test inside this folder to the right scenario"""

from utils import scenarios
from .utils import get_scenario_map


@scenarios.test_the_test
def test_the_test_coherence():
    valid_scenarios = ("TEST_THE_TEST", "MOCK_THE_TEST", "MOCK_THE_TEST_2")
    scenario_map = get_scenario_map()

    for node_id, scenario_list in scenario_map.items():
        if node_id.startswith("tests/test_the_test/"):
            for scenario in scenario_list:
                assert scenario in valid_scenarios, f"{node_id} should belong to TEST_THE_TEST"
