# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from typing import Any
from collections.abc import Callable

from ._data import _Data

data = _Data()


def apply_method(obj: str | bool | float | list | dict | None, key_callback: Callable, value_callback: Callable) -> Any:  # noqa: ANN401
    """Recursyvly apply methods on a JSON-like object"""
    if obj is None or isinstance(obj, (str, float, int, bool)):
        return value_callback(obj)

    if isinstance(obj, list):
        return [apply_method(value, key_callback, value_callback) for value in obj]

    if isinstance(obj, dict):
        return {key_callback(key): apply_method(value, key_callback, value_callback) for key, value in obj.items()}

    raise TypeError("Unexpcted type : " + str(type(obj)))
