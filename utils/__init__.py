# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from typing import TYPE_CHECKING

# singletons
from utils._weblog import weblog, HttpResponse
from utils._context.core import context
from utils._context._scenarios import scenarios, scenario_groups
from utils._decorators import (
    bug,
    irrelevant,
    missing_feature,
    rfc,
    flaky,
    incomplete_test_app,
    slow,
    scenario_crash,
    auxiliary_test,
)
from utils._logger import logger
from utils import interfaces, _remote_config as remote_config
from utils.interfaces._core import ValidationError
from utils._features import features

if TYPE_CHECKING:
    # Exposed for type annotations only: these are not available at runtime, so tests
    # must import them under `if TYPE_CHECKING:` (with `from __future__ import annotations`)
    from utils.docker_fixtures import (
        FrameworkTestClientApi as FrameworkTestClientApi,
        ParametricTestClientApi as ParametricTestClientApi,
        TestAgentAPI as TestAgentAPI,
    )
    from utils.docker_fixtures._test_agent import AgentRequest as AgentRequest
    from utils.docker_fixtures.spec.trace import Span as Span
    from utils.dd_types import (
        DataDogAgentSpan as DataDogAgentSpan,
        DataDogLibrarySpan as DataDogLibrarySpan,
        DataDogLibraryTrace as DataDogLibraryTrace,
    )

__all__ = [
    "HttpResponse",
    "ValidationError",
    "auxiliary_test",
    "bug",
    "context",
    "features",
    "flaky",
    "incomplete_test_app",
    "interfaces",
    "irrelevant",
    "logger",
    "missing_feature",
    "remote_config",
    "rfc",
    "scenario_crash",
    "scenario_groups",
    "scenarios",
    "slow",
    "weblog",
]
