# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.


def basic(klass):
    assert not hasattr(klass, "__coverage__"), f"coverage has been declared twice for {klass}"

    setattr(klass, "__coverage__", "basic")
    return klass


def good(klass):
    assert not hasattr(klass, "__coverage__"), f"coverage has been declared twice for {klass}"

    setattr(klass, "__coverage__", "good")
    return klass


def complete(klass):
    assert not hasattr(klass, "__coverage__"), f"coverage has been declared twice for {klass}"

    setattr(klass, "__coverage__", "complete")
    return klass
