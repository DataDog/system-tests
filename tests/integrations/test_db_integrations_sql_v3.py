# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.



from utils import context, sql_bug, missing_sql_feature,sql_irrelevant, missing_feature,irrelevant,scenarios
from utils.tools import logger

import pytest
from utils import weblog, interfaces
from .sql_utils import BaseDbIntegrationsTestClass


class Test_One:
    @missing_sql_feature(condition=lambda test_sql_operation: test_sql_operation == "insert", reason="ESTO Y AQUELLO")
    @missing_sql_feature(
        library="nodejs", condition=lambda test_sql_operation: test_sql_operation == "select", reason="ESTO Y AQUELLO"
    )
    #  @missing_feature(library="nodejs", reason="OTRAOTRA")
    @pytest.mark.usefixtures("manage_sql_decorators")  # Mandatory for decorators to work :-(
    def test_addition(self, test_sql_service, test_sql_operation, weblog_request):
        logger.debug(f"Parametrizedd for operation::{test_sql_operation} and service: {test_sql_service}")
        assert True

    @irrelevant(library="nodejs", reason="TRUKUTRUKU")
    def test_addition2(self):
        logger.debug("Parametrizedd!!")
        assert True
