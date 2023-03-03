import pytest
import pulumi
import json

def pytest_generate_tests(metafunc):
    private_ips = []
    with open("pulumi.output.json", "r") as f:
        obj = json.load(f)
        for key, value in obj.items():
            private_ips.append(value)
        metafunc.parametrize("private_ip", private_ips)
