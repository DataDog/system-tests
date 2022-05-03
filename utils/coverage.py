# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.


def not_testable(klass):
    assert not hasattr(klass, "__coverage__"), f"coverage has been declared twice fr {klass}"

    def test(self):
        pass

    setattr(klass, "__coverage__", "not-testable")
    setattr(klass, "test_fake", test)

    return klass


def not_implemented(klass):
    assert not hasattr(klass, "__coverage__"), f"coverage has been declared twice fr {klass}"

    def test(self):
        pass

    setattr(klass, "__coverage__", "not-implemented")
    setattr(klass, "test_fake", test)

    return klass


def basic(klass):
    assert not hasattr(klass, "__coverage__"), f"coverage has been declared twice fr {klass}"

    setattr(klass, "__coverage__", "basic")
    return klass


def good(klass):
    assert not hasattr(klass, "__coverage__"), f"coverage has been declared twice fr {klass}"

    setattr(klass, "__coverage__", "good")
    return klass


def complete(klass):
    assert not hasattr(klass, "__coverage__"), f"coverage has been declared twice fr {klass}"
    setattr(klass, "__coverage__", "complete")
    return klass
