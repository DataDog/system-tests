import re
from utils import scenarios
from utils._context._scenarios import get_all_scenarios


@scenarios.test_the_test
def test_scenario_names():
    for scenario in get_all_scenarios():
        name = scenario.name
        assert re.fullmatch(
            r"^[A-Z][A-Z\d_]+$", name
        ), f"'{name}' is not a valid name for a scenario, it should be only capital letters"

        expected_property = name.lower()

        assert hasattr(scenarios, expected_property), f"Scenarios object sould have the {expected_property} property"
        assert (
            getattr(scenarios, expected_property) is scenario
        ), f"scenarios.{expected_property} should be the {scenario} object"
