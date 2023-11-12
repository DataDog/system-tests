# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.
from utils import context, bug, missing_feature, irrelevant, scenarios, flaky
from utils.tools import logger
import pytest
from utils import weblog, interfaces
from .sql_utils import BaseDbIntegrationsTestClass
# Define the data for test case generation
test_sql_operations = ["select","insert","update","delete","procedure","select_error"]
test_sql_services = ["mysql","postgres","mssql"]
# Define the pytest_generate_tests hook to generate test cases
def pytest_generate_tests(metafunc):
    if 'test_sql_service' in metafunc.fixturenames and context.scenario == scenarios.integrations_v3:
        test_parameters = []
        test_ids = []
        for test_sql_service in test_sql_services:
            logger.info("Initializing DB...")
            weblog.get(
                        "/db", params={"service": test_sql_service, "operation": "init"}, timeout=20 )
            for test_sql_operation in test_sql_operations:
                  weblog_request = weblog.get("/db", params={"service": test_sql_service, "operation": test_sql_operation})
                  test_parameters.append(pytest.param(test_sql_service, test_sql_operation,weblog_request, marks=[]))
                 # test_parameters.append(test_sql_service, test_sql_operation, weblog_request)
                  test_ids.append( "srv:" + test_sql_service + ",op:" + test_sql_operation)    
        # Generate test cases based on the test_data list     
        metafunc.parametrize('test_sql_service,test_sql_operation,weblog_request', test_parameters,ids=test_ids)
        
def missing_feature2(condition=None, library=None, weblog_variant=None, reason=None):
    """decorator, allow to mark a test function/class as missing"""

    def decorator(function_or_class):
       
        return function_or_class

    return decorator

import functools
import inspect

def missing_sql_feature(func=None,condition=None,library=None, reason=None):
    if func is None:
        return functools.partial(missing_sql_feature, condition=condition, library=library, reason=reason)
    @functools.wraps(func)
    def decorator(*args, **kwargs):
        codition_param_values={}
        for param_name in inspect.signature(condition).parameters:
            codition_param_values[param_name] = kwargs.get(param_name)
       # logger.info(f"RMM ARGS: {args}")
       # logger.info(f"RMM kwargs: {kwargs}")
       # pytest.xfail(reason='some bug')
        if condition(**codition_param_values):
            full_reason = "irrelevant:" if reason is None else f"irrelevant: {reason}"
            pytest.skip(full_reason)
        
        return func(*args, **kwargs)
    return decorator

@scenarios.integrations_v3
class Test_One():
    @missing_sql_feature (library="TEST", condition=lambda test_sql_operation: test_sql_operation == "select",reason="ESTO Y AQUELLO")
  #  @missing_feature(library="nodejs", reason="OTRAOTRA")
    def test_addition(self, test_sql_service, test_sql_operation, weblog_request ):
        logger.debug(f"Parametrizedd for operation::{test_sql_operation} and service: {test_sql_service}")
        assert True     
    @irrelevant(library="nodejs", reason="TRUKUTRUKU")
    def test_addition2(self ):
        logger.debug("Parametrizedd!!")
        assert True     