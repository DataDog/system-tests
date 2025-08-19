import re
from utils import scenarios
from utils._context._scenarios import get_all_scenarios


@scenarios.test_the_test
def test_minimal_number_of_scenarios():
    for scenario in get_all_scenarios():

