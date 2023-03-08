import pytest
import pulumi
import json
import logging


def pytest_generate_tests(metafunc):
    testing_machines = []
    with open("pulumi.output.json", "r") as f:
        obj = json.load(f)
        machine_desc = dict()
        for key, value in obj.items():
            machine_desc["private_ip"] = value
            machine_desc["name"] = key
            testing_machines.append(machine_desc)
        metafunc.parametrize("machine_desc", testing_machines)
