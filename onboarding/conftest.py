import pytest
import pulumi
import json
import logging
import os

_docs = {}


def _getParams(key, ip):
    test_metadata = dict()
    test_metadata["private_ip"] = ip
    # key format example: privateIp_host__amazon-linux-x86__agent-prod__autoinjection-java-dev__lang-variant-OpenJDK11__weblog-test-app-java
    key = key.replace("privateIp_", "")
    key_parts = key.split("__")
    test_metadata["scenario"] = key_parts[0]
    test_metadata["machine"] = key_parts[1]
    test_metadata["agent"] = key_parts[2]
    language_version = key_parts[3].replace("autoinjection-", "")
    language_version_parts = language_version.split("-")
    test_metadata["language"] = language_version_parts[0]
    test_metadata["version"] = language_version_parts[1]  # dev or pro
    test_metadata["lang_variant"] = key_parts[4].replace("lang-variant-", "")
    test_metadata["weblog_variant"] = key_parts[5].replace("weblog-", "")
    test_metadata["installed_version"] = getInstalledVersions(
        ip
    )  # datadog-apm-inject and datadog-apm-library-<lang> version

    return test_metadata


def pytest_generate_tests(metafunc):
    """ We execute a test for each line of the pulumi export (fo each ip) """
    ips = []
    with open("pulumi.output.json", "r") as f:
        obj = json.load(f)
        for key, value in obj.items():
            if key.startswith("privateIp_"):
                ips.append(_getParams(key, value)["private_ip"])

        metafunc.parametrize("ip", ips)


def pytest_json_modifyreport(json_report):
    print("Updating json report...")
    allData = []
    with open("pulumi.output.json", "r") as f:

        obj = json.load(f)
        for key, value in obj.items():
            if key.startswith("privateIp_"):
                allData.append(_getParams(key, value))

    # clean useless and volumetric data
    del json_report["collectors"]

    # Add usefull information
    json_report["metadata"] = allData
    json_report["docs"] = _docs

    # TODO Extract versions
    json_report["context"] = {"library": {"version": ""}}

    # TODO Create and manage skip reason decorators
    for test in json_report["tests"]:
        test["skip_reason"] = None


def getInstalledVersions(ip):
    versions_file_path = "logs/pulumi_installed_versions.log"
    with open(versions_file_path) as fh:
        for line in fh:
            if line.startswith(ip):
                return line.replace(ip + " 172.17.0.1", ip).replace(
                    ip + " :", ""
                )  # Machine with docker also returns the ip 172.17.0.1
    return ""


def pytest_collection_modifyitems(session, config, items):
    for item in items:
        _collect_item_metadata(item)


# called when each test item is collected and extracts doc info
def _collect_item_metadata(item):

    _docs[item.nodeid] = item.obj.__doc__
    _docs[item.parent.nodeid] = item.parent.obj.__doc__
    if hasattr(item.parent.parent, "obj"):
        _docs[item.parent.parent.nodeid] = item.parent.parent.obj.__doc__
