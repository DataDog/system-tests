# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils._core import BaseTestCase

# singletons
from utils._context.core import context
from utils._decorators import released, bug, irrelevant, missing_feature, rfc, flaky
from utils import interfaces
from utils._data_collector import data_collector
from utils import coverage
from utils._proxies import proxies
from utils.interfaces._core import ValidationError


class ValidationException(Exception):
    def __init__(self, message, extra_info=None) -> None:
        super().__init__(message)
        self.extra_info = extra_info
