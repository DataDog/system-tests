# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.
from utils import context, bug, missing_feature, irrelevant, scenarios, flaky
from utils.tools import logger
import pytest

all_params = {
    "test_addnums": {
        "params": ["num1", "num2", "output"],
        "values":
            [
                [2, 2, 4],
                [3, 7, 10],
                [48, 52, 100]
            ]
 
    },
    "test_foobar":
        {
            "params": ["foo", "bar"],
            "values": [
                [1, 2],
                ["moo", "mar"],
                [0.5, 3.14]
            ]
        }
}


def pytest_generate_tests(metafunc):
    fct_name = metafunc.function.__name__
    if fct_name in all_params:
        params = all_params[fct_name]
        metafunc.parametrize(params["params"], params["values"], ids=["id4", "id5", "id6"])


            
@scenarios.integrations_v4
class Test_Dos():
    #db_service, operation, spans
    

    def test_addnums(self, num1, num2, output):
        assert num1 + num2 == output


    def test_foobar(self, foo, bar):
        assert type(foo) == type(bar) 
