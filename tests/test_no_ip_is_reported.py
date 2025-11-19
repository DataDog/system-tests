# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

"""Misc checks around data integrity during components' lifetime"""

import socket
from utils import interfaces, scenarios, features


def is_ip(value: str):
    try:
        socket.inet_aton(value)
        return True
    except:
        return False


@scenarios.todo
@features.library_scrubbing
class Test_NoIpIsReported:
    """Used to check that no IP is reported by agent"""

    def test_no_ip(self):
        """Check no ip is present"""
        allowed_keys = {
            "request.application.tracer_version",
            "request.payload.dependencies[].version",
            "request.tracerPayloads[].tracerVersion",
        }

        def assert_no_ip(data: dict | list | bytes | str | float | bool, root: str):
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

        def validator(data: dict):
            assert_no_ip(data["request"]["content"], "request")

        interfaces.agent.validate_all(validator, allow_no_data=True)
