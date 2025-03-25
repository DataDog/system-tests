# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import os
import sys
import json
from pathlib import Path
from tests.fuzzer.tools.random_strings import get_random_unicode as gru


def get_simple_gets_corpus() -> list:
    return [{"method": "GET", "path": "/"}]


def get_attack10_corpus() -> list:
    result = []
    for _ in range(9):
        result.append({"method": "GET", "path": "/"})

    result.append({"method": "GET", "path": "/x?a='%20OR%20TRUE--"})

    return result


def get_big_requests_corpus() -> list:
    """Send huge requests.

    Should be run with -c 1
    Need a better ouput to interrpret results...
    """

    waf_triggers = {
        "headers": ["../", "( ) {"],
        "payload": [
            "union select from",
            "<vmlframe src=",
            "http-equiv:+set-cookie",
            "require('.')",
            "file_0?",
            "zlib://",
        ],
    }

    sys.setrecursionlimit(100000)

    def _get_base_request(comment, path="/", payload_name="json", method="GET"):
        result = {
            "method": method,
            "path": path,
            "headers": {"x-fuzzing-comment": comment},
        }

        if method != "GET":
            result[payload_name] = {}

        return result

    def _get_nested(size, depth, string_size=20):
        if depth == 0:
            return {f"{i}": None for i in range(size)}

        return {gru(2, 2): _get_nested(size, depth - 1, string_size) for i in range(size)}

    def _get_nested_arrays(size, depth, string_size=20):
        if depth == 0:
            return [gru(string_size, string_size) for i in range(size)]

        return [_get_nested_arrays(size, depth - 1, string_size) for i in range(size)]

    def _get_waf_triggers_request(comment, payload_name="json", r1=10, r2=1):
        request = _get_base_request(comment, payload_name=payload_name, method="POST")

        payload = request[payload_name]

        for i in range(30):
            for j, item in enumerate(waf_triggers["headers"]):
                request["headers"][f"{j}{i}"] = str(i) + item

        for i in range(r1):
            for j, item in enumerate(waf_triggers["payload"]):
                payload[f"{j}{i}"] = str(i) + (item * r2)

        return request

    def _get_nested_array_requests(comment, size, depth, string_size=20):
        request = _get_base_request(comment, method="POST")
        request["json"]["data"] = _get_nested_arrays(size, depth, string_size=string_size)

        return request

    def _get_nested_dict_requests(comment, size, depth, string_size=20):
        request = _get_base_request(comment, method="POST")
        request["json"]["data"] = _get_nested(size, depth, string_size=string_size)

        return request

    def _get_big_data(comment, payload_name="json", count=20000, string_size=20):
        request = _get_base_request(comment, payload_name=payload_name, method="POST")

        for _ in range(count):
            request[payload_name][gru(string_size, string_size)] = gru(string_size, string_size)

        return request

    def _get_random_data(comment, payload_name="data", size=2000000):
        request = _get_base_request(comment, payload_name=payload_name)

        request["headers"] = {"Content-type": "text/plain"}
        request[payload_name] = bytearray(os.urandom(size))

        return request

    def _get_long_url(comment):
        return _get_base_request(comment, path="/" * 8000)

    result = []
    result.append(_get_long_url("long url"))
    result.append(_get_big_data("lot of flat data", "data", count=10000, string_size=100))
    result.append(_get_base_request("base"))
    result.append(_get_waf_triggers_request("waf trigs"))
    result.append(_get_waf_triggers_request("waf trigger count", r1=10000))
    result.append(_get_waf_triggers_request("waf trigger size", r2=5000))
    result.append(_get_waf_triggers_request("waf triggers in data", payload_name="data"))
    result.append(_get_waf_triggers_request("waf triggers big data", payload_name="data", r1=10000))
    result.append(_get_nested_array_requests("nested std", 8, 4))
    result.append(_get_nested_array_requests("nested deep", 2, 15, string_size=3))
    result.append(_get_nested_dict_requests("nest dict", 7, 4))
    result.append(_get_nested_dict_requests("nest dict deep", 2, 13))
    result.append(_get_nested_dict_requests("lot of data", 150, 1))
    result.append(_get_big_data("lot of flat json2", payload_name="json"))
    result.append(_get_random_data("random", size=100000000))

    return result


def get_saved_corpus(source) -> list:
    if source is None:
        source = str(Path(os.path.realpath(__file__)).parent)
        source = os.path.join(source, "corpus")

    result = []

    def _load_file(filename):
        if filename.endswith(".json"):
            with open(filename, "r", encoding="utf-8") as f:
                _add_request(json.load(f))
        elif filename.endswith(".dump"):
            with open(filename, "r", encoding="utf-8") as f:
                for line in f:
                    if len(line.strip()) != 0:
                        _add_request(json.loads(line))
        else:
            raise ValueError(f"{filename} file must be a .dump or a .json")

    def _add_request(request):
        assert request["path"].startswith("/")
        result.append(request)

    def _load_dir(base_dirname):
        for _, dirnames, filenames in os.walk(base_dirname):
            for dirname in dirnames:
                _load_dir(os.path.join(base_dirname, dirname))

            for filename in filenames:
                if filename.endswith((".json", ".dump")):
                    _load_file(os.path.join(base_dirname, filename))

    if Path(source).is_file():
        _load_file(source)
    elif Path(source).is_dir():
        _load_dir(source)
    else:
        raise ValueError(f"{source} is not a file or a dir")

    return result


def get_corpus(corpus=None) -> list:
    if corpus == "attack10":
        return get_attack10_corpus()

    if corpus == "gets":
        return get_simple_gets_corpus()

    if corpus == "bigs":
        return get_big_requests_corpus()

    return get_saved_corpus(corpus)


if __name__ == "__main__":
    print(get_corpus())
