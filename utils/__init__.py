# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import utils._remote_config as remote_config
    from utils import interfaces
    from utils._context._scenarios import scenario_groups as scenario_groups
    from utils._context._scenarios import scenarios as scenarios
    from utils._context.core import context as context
    from utils._decorators import auxiliary_test as auxiliary_test
    from utils._decorators import bug as bug
    from utils._decorators import flaky as flaky
    from utils._decorators import incomplete_test_app as incomplete_test_app
    from utils._decorators import irrelevant as irrelevant
    from utils._decorators import missing_feature as missing_feature
    from utils._decorators import rfc as rfc
    from utils._decorators import scenario_crash as scenario_crash
    from utils._decorators import slow as slow
    from utils._features import features as features
    from utils._logger import logger as logger
    from utils._weblog import HttpResponse as HttpResponse
    from utils._weblog import weblog as weblog
    from utils.interfaces._core import ValidationError as ValidationError

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

_LAZY_EXPORTS = {
    "HttpResponse": ("utils._weblog", "HttpResponse"),
    "ValidationError": ("utils.interfaces._core", "ValidationError"),
    "auxiliary_test": ("utils._decorators", "auxiliary_test"),
    "bug": ("utils._decorators", "bug"),
    "context": ("utils._context.core", "context"),
    "features": ("utils._features", "features"),
    "flaky": ("utils._decorators", "flaky"),
    "incomplete_test_app": ("utils._decorators", "incomplete_test_app"),
    "interfaces": ("utils.interfaces", None),
    "irrelevant": ("utils._decorators", "irrelevant"),
    "logger": ("utils._logger", "logger"),
    "missing_feature": ("utils._decorators", "missing_feature"),
    "remote_config": ("utils._remote_config", None),
    "rfc": ("utils._decorators", "rfc"),
    "scenario_crash": ("utils._decorators", "scenario_crash"),
    "scenario_groups": ("utils._context._scenarios", "scenario_groups"),
    "scenarios": ("utils._context._scenarios", "scenarios"),
    "slow": ("utils._decorators", "slow"),
    "weblog": ("utils._weblog", "weblog"),
}


def __getattr__(name: str) -> object:
    if name not in _LAZY_EXPORTS:
        raise AttributeError(f"module 'utils' has no attribute '{name}'")

    module_name, attribute_name = _LAZY_EXPORTS[name]
    module = import_module(module_name)
    value = module if attribute_name is None else getattr(module, attribute_name)
    globals()[name] = value
    return value
