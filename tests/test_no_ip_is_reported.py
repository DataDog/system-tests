# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Misc checks around data integrity during components' lifetime"""
import socket
from utils import interfaces, coverage, scenario


def is_ip(value):
    try:
        socket.inet_aton(value)
        return True
    except:
        return False


@coverage.good
@scenario("NO_SCENARIO_FOR_NOW")
class Test_NoIpIsReported:
    """ Used to check that no IP is reported by agent """

    def test_no_ip(self):
        """ Check no ip is present """
        allowed_keys = {
            "request.application.tracer_version",
            "request.payload.dependencies[].version",
            "request.tracerPayloads[].tracerVersion",
        }

        def assert_no_ip(data, root):
            if data is None or isinstance(data, (bool, int, float, bytes)):
                pass  # nothing interesting here
            elif isinstance(data, bytes):
                pass  # sorry :(
            elif isinstance(data, str):
                if (
                    root not in allowed_keys
                    and len(data) > 7
                    and not data.isdigit()
                    and " " not in data
                    and is_ip(data)
                ):
                    raise ValueError(f"There is an ip: {root}={data}")
            elif isinstance(data, dict):
                for key, value in data.items():
                    assert_no_ip(value, f"{root}.{key}")
            elif isinstance(data, list):
                for value in data:
                    assert_no_ip(value, f"{root}[]")
            else:
                raise TypeError(f"Unsupported type: {data}")

        def validator(data):
            assert_no_ip(data["request"]["content"], "request")

        interfaces.agent.validate(validator, success_by_default=True)
