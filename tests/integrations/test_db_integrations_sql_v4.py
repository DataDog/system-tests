# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.
from utils import context, bug, missing_feature, irrelevant, scenarios, flaky
from utils.tools import logger
import pytest

# Define the data for test case generation
test_data = [
        ((1, 2), 3),   # Input: (1, 2) | Expected Output: 3
        ((0, 0), 0),   # Input: (0, 0) | Expected Output: 0
        ((-1, 1), 0),  # Input: (-1, 1) | Expected Output: 0
        ((-1, 1), 0),  # Input: (-1, 1) | Expected Output: 0
]
    
# Define the pytest_generate_tests hook to generate test cases
def pytest_generate_tests(metafunc):
    if 'test_input' in metafunc.fixturenames:
        # Generate test cases based on the test_data list
         metafunc.parametrize('test_input,expected_output', test_data)
            
@scenarios.integrations_v4
class Test_Dos():
    #db_service, operation, spans
    
    """ MsSql integration with Datadog tracer+agent """
    def test_v3(self):
        logger.debug("MY FIRST TESTS")
        assert True

    # Define the actual test function
    def test_addition(self, test_input, expected_output):
        logger.debug("Parametrizedd!!")
        assert True     
