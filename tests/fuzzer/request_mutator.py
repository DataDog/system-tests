# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import random
import os
from pathlib import Path
import re
from urllib.parse import quote
from utils._context.containers import WeblogContainer
from tests.fuzzer.tools import data
from tests.fuzzer.tools.random_strings import get_random_unicode as gru, get_random_string, string_lists


def _get_data_file(name: str):
    dir_path = Path(os.path.realpath(__file__)).parent
    return open(os.path.join(dir_path, "data", name), "rb").read()


def _clean_string(item: str, allowed: list[str] | None = None, forbidden: str | None = None) -> str:
    if allowed is not None:
        item = "".join(c for c in item if c in allowed)

    if forbidden is not None:
        item = "".join(c for c in item if c not in forbidden)

    return item


def _random_number():
    _integers = [
        -(2**64) - 1,
        -1025,
        -100000,
        1025,
        0,
        1,
        -1,
        100000,
        2**64 + 1,
        0.0,
        0.1,
        3.14,
    ]

    return random.choice(_integers)


def _mutate_string(item: str, alphabet: list[str] | str = string_lists.unicode):
    if len(item) == 0:
        return get_random_string(alphabet)

    start = random.randint(0, len(item) - 1)
    end = random.randint(start, len(item) - 1)

    return item[:start] + random.choice(alphabet) + item[end:]


def _mutate_dict(item: dict):
    if len(item) != 0:
        key = random.choice(tuple(item))
        item[key] = _mutate_item(item[key])

    return item


def _mutate_list(item: list):
    if len(item) != 0:
        i = random.randint(0, len(item) - 1)
        item[i] = _mutate_item(item[i])

    return item


def _mutate_item(item: float | str | list | dict | bool):
    if isinstance(item, (int, float)):
        item = _random_number()

    if isinstance(item, str):
        item = _mutate_string(item)

    elif isinstance(item, list):
        item = _mutate_list(item)

    elif isinstance(item, dict):
        item = _mutate_dict(item)

    elif isinstance(item, bool):
        item = random.choice((True, False))

    else:
        # TODO: other use cases
        pass

    return item


def _reduce_item(item: list | dict | str | float | bool):
    if isinstance(item, (str, float, int, bool)) or len(item) == 0:
        pass

    elif isinstance(item, list):
        _reduce_list(item)

    elif isinstance(item, dict):
        _reduce_dict(item)

    else:
        raise ValueError(f"Can't enlarge {type(item)}")


def _reduce_list(item: list):
    item.pop(random.randint(0, len(item) - 1))


def _reduce_dict(item: dict):
    item.pop(random.choice(tuple(item)))


def _enlarge_item(item: dict | list, key: str, value: dict | list):
    if isinstance(item, dict):
        _enlarge_dict(item, key, value)
    elif isinstance(item, list):
        _enlarge_list(item, key, value)


def _enlarge_dict(item: dict, key: str, value: dict | list):
    if len(item) == 0:
        item[key] = value
    else:
        sub_item = random.choice(tuple(item.values()))

        if isinstance(sub_item, dict):
            _enlarge_dict(sub_item, key, value)
        elif isinstance(sub_item, list):
            _enlarge_list(sub_item, key, value)
        else:
            item[key] = value


def _enlarge_list(item: list, key: str, value: dict | list):
    if len(item) == 0:
        item.append(value)
    else:
        sub_item = random.choice(item)

        if isinstance(sub_item, dict):
            _enlarge_dict(sub_item, key, value)
        elif isinstance(sub_item, list):
            _enlarge_list(sub_item, key, value)
        else:
            item.insert(random.randint(0, len(item) - 1), value)


def _get_string_from_list(items: list[str] | tuple[str, ...], characters: list[str] | str, min_length: int = 0):
    result = random.choice(items)
    return result if result else get_random_string(characters, min_length=min_length)


class RequestMutator:
    allow_empty_header_key = True
    allow_colon_in_first_in_header_key = True
    allowed_json_payload_types: tuple[type, ...] = (dict, tuple, list, str, float, int)
    max_path_length = 65000

    methods: tuple[str, ...] = (
        "ACL",
        "BASELINE-CONTROL",
        "CHECKIN",
        "CHECKOUT",
        "COPY",
        "CONNECT",
        "DELETE",
        "GET",
        "HEAD",
        "LABEL",
        "LOCK",
        "M-SEARCH",
        "MERGE",
        "MKACTIVITY",
        "MKCALENDAR",
        "MKCOL",
        "MKWORKSPACE",
        "MOVE",
        "NOTIFY",
        "OPTIONS",
        "ORDERPATCH",
        "PATCH",
        "POST",
        "PROPFIND",
        "PROPPATCH",
        "PUT",
        "PURGE",
        "REPORT",
        "SEARCH",
        "SUBSCRIBE",
        "TRACE",
        "UNCHECKOUT",
        "UNLOCK",
        "UNSUBSCRIBE",
        "UPDATE",
        "VERSION-CONTROL",
        # invalid methods, but we test them :)
        "PATATE",
        "RR RR",
        "M\x00M",
    )

    payload_types = ["json", "data"]

    ip_header_keys = (
        "x-forwarded-for",
        "x-client-ip",
        "x-real-ip",
        "x-forwarded",
        "x-cluster-client-ip",
        "forwarded-for",
        "forwarded",
        "via",
    )
    generic_header_keys = ("", "User-Agent", "Content-length", "content-type")

    header_values = ["", "../", "( ) {", *data.blns]
    user_agents = (
        "Arachni/v1.2.1",
        "md5(acunetix_wvs_security_test)",
        "black widow",
        " blackwidow ",
        " brutus ",
        " bsqlbf ",
        " cgichk ",
        "commix/ ",
        " crowdstrike ",
        " dirbuster ",
        " evilScanner ",
        "gobuster/ ",
        "GoogleSecurityScanner",
        " rendel-scan ",
        " havij ",
        " jaascois ",
    )
    header_characters: list[str] = string_lists.unicode

    charsets: tuple[str, ...] = (
        "utf-8",
        "ISO-8859-1",
        "Windows-1251",
        "Windows-1252",
        "Shift JIS",
        "GB2312",
        "EUC-KR",
        "ISO-8859-9",
        # less common one
        "Windows-874",
        "ISO-8859-15",
        "US-ASCII",
        "Windows-1255",
        "TIS-620",
        "ISO-8859-7",
        "Windows-1253",
        "UTF-16",
        "KOI8-R",
        "Windows-1257",
        "GB18030",
        "UTF-7",
        "KS C 5601",
        "ISO-8859-8",
        "Windows-31J",
        "ISO-8859-5",
        "ISO-8859-4",
        "ANSI_X3.110-1983",
        "ISO-8859-6",
        "KOI8-U",
        "ISO-8859-3",
        "Windows-1258",
        "ISO-2022-JP",
        "ISO-8859-11",
        "ISO-8859-13",
        "Big5 HKSCS",
        "ISO-8859-10",
        "ISO-8859-16",
        "Windows-949",
        "IBM850",
    )

    payload_values = [
        None,
        "",
        0,
        -1,
        2**64 + 1,
        True,
        False,
        *data.blns,
        "ok",
        "union select from",
        "<vmlframe src=",
        "http-equiv:+set-cookie",
        "require('.')",
        "file_0?",
        "zlib://",
        "1234-1234-1234-1234",
    ]

    file_data = [
        _get_data_file("image1.jpg"),
        _get_data_file("video1.mp4"),
        _get_data_file("pdf1.pdf"),
        _get_data_file("html1.html"),
        _get_data_file("html2.html"),
        _get_data_file("html3.html"),
        _get_data_file("html4.html"),
        _get_data_file("html5.html"),
        _get_data_file("html6.html"),
        _get_data_file("html7.html"),
    ]

    # These items causes false positive, never test them
    invalid_methods: tuple[str, ...] = ()
    invalid_header_keys: tuple[str, ...] = ()

    def __init__(self, *, no_mutation: bool = False):
        self.methods = tuple(method for method in self.methods if method not in self.invalid_methods)

        self.invalid_header_keys = tuple(key.lower() for key in self.invalid_header_keys)

        self.header_keys = tuple(
            key for key in self.generic_header_keys + self.ip_header_keys if key.lower() not in self.invalid_header_keys
        )

        self.no_mutation = no_mutation

    #############################
    def mutate(self, request: dict, mutations: int = 3) -> None:
        if self.no_mutation:
            return

        # list of methods to execute
        # the second value is a weight. The probability of execution of one
        # method i is: weight_i/sum(weights)
        mutators = [
            (self.change_method, 1),
            (self.set_random_path, 1),
            (self.mutate_path, 1),
            (self.add_header, 100),
            (self.remove_header, 100),
            (self.mutate_header_value, 500),
            (self.mutate_payload, 500),
            (self.set_random_payload, 50),
            (self.reduce_payload, 100),
            (self.enlarge_payload, 10),
            (self.add_cookie, 100),
            (self.remove_cookie, 100),
        ]

        methods = [item[0] for item in mutators]
        weights = [item[1] for item in mutators]

        for method in random.choices(methods, weights, k=mutations):
            method(request)

    ################################
    def change_method(self, request: dict) -> None:
        request["method"] = random.choice(self.methods)

    def set_random_path(self, request: dict) -> None:
        path_length = random.randint(0, 32)
        items = (quote(item) for item in random.choices(data.blns, k=path_length))
        request["path"] = ("/" + "/".join(items))[: self.max_path_length]

    def mutate_path(self, request: dict) -> None:
        path = _mutate_string(request["path"], "/azerty?&=")

        if not path.startswith("/"):
            path = "/" + path

        request["path"] = path[: self.max_path_length]

    def add_cookie(self, request: dict) -> None:
        cookies = request.get("cookies", {})

        key = self.get_cookie_key()
        cookies[key] = self.get_cookie_value()

    def remove_cookie(self, request: dict) -> None:
        cookies = request.get("cookies")

        if not cookies or len(cookies) == 0:
            return

        cookies.pop(random.choice(tuple(cookies)))

    def add_header(self, request: dict) -> None:
        if "headers" not in request:
            request["headers"] = []

        key = self.get_header_key()
        request["headers"].append([key, self.get_header_value(key)])

    def remove_header(self, request: dict) -> None:
        headers = request.get("headers")

        if not headers or len(headers) == 0:
            return

        headers.pop(random.randint(0, len(headers) - 1))

    def mutate_header_value(self, request: dict) -> None:
        headers = request.get("headers")

        if not headers or len(headers) == 0:
            return

        header = random.choice(headers)
        header[1] = self.get_header_value(header[0], header[1])

    def mutate_ip(self, ip: str | None) -> str:
        if ip is None:
            ip = random.choice(
                tuple(f"{i}.0.0.0" for i in range(100))
                + (
                    # blocked ips
                    "123.14.51.61",
                    "14.51.61.0/7",
                    "::0000:0000:0000:0000:0370:7334",
                    "2001:0db8:0000:0000:0000:8a2e:0370:7334",  # public ipv6 ip
                    "fe80::1ff:fe23:4567:890a",  # private ipv6 ip
                    "::0000:0000:0000:0000:0370:0/16",
                    # other fun ip
                    "fe80--1ff-fe23-4567-890as3.ipv6-literal.net",
                    r"2001:db8::8a2e:370:7334%eth2",
                    r"2001:db8::8a2e:370:7335%eth2",
                )
            )

        pos = random.randint(0, len(ip) - 1)
        if ip[pos].isnumeric():
            ip = ip[:pos] + random.choice("0123456789") + ip[pos + 1 :]

        return ip

    def set_random_payload(self, request: dict) -> None:
        request.pop("data", None)
        request.pop("json", None)

        payload_type = random.choice(self.payload_types)
        request[payload_type] = self.get_random_payload(payload_type)

    def mutate_payload(self, request: dict) -> None:
        for payload_type in ("data", "json"):
            if payload_type in request:
                request[payload_type] = _mutate_item(request[payload_type])

    def reduce_payload(self, request: dict) -> None:
        if "json" in request:
            _reduce_item(request["json"])
        elif "data" in request:
            _reduce_item(request["data"])

    def enlarge_payload(self, request: dict) -> None:
        for payload_type in ("data", "json"):
            if payload_type in request:
                key = self.get_payload_key()
                value = self.get_payload_value(allow_nested=payload_type == "json")
                _enlarge_item(request[payload_type], key, value)

    ################################
    def get_cookie_key(self) -> str:
        return gru()

    def get_cookie_value(self) -> str:
        return gru()

    def get_header_key(self) -> str:
        result = random.choice(self.header_keys)
        result = result if result else get_random_string(self.header_characters, min_length=1)

        if not self.allow_colon_in_first_in_header_key and result.startswith(":"):
            result = re.sub(r"^:*", "", result)

        return result

    def get_header_value(self, key: str, previous_value: str | None = None) -> str:
        if previous_value:
            return _mutate_string(previous_value, self.header_characters)

        key = key.lower()

        if key == "user-agent":
            return _get_string_from_list(self.user_agents, self.header_characters, min_length=1)

        if key == "content-length":
            return str(random.choice((-1, 0, 1, 12, 2**32, "nan")))

        if key == "content-type":
            return self._get_random_content_type()

        if key in self.ip_header_keys:
            return self.mutate_ip(previous_value)

        return _get_string_from_list(self.header_values, self.header_characters, min_length=1)

    def _get_random_content_type(self) -> str:
        return "text/html;charset=" + self._get_random_charset()

    def _get_random_charset(self) -> str:
        # https://w3techs.com/technologies/overview/character_encoding
        return random.choice(self.charsets)

    def get_random_payload(self, payload_type: str) -> str | dict:
        if payload_type == "json":
            count = random.randint(1, 10)
            return {self.get_payload_key(): self.get_payload_value(allow_nested=True) for _ in range(count)}

        choice = random.randint(0, 50)
        if choice <= 1:
            return gru(1000, 10000)

        if choice < 2:
            return {"file": random.choice(self.file_data)}

        count = random.randint(1, 10)
        return {self.get_payload_key(): self.get_payload_value() for _ in range(count)}

    def get_payload_key(self) -> str:
        return random.choice(data.blns)

    def get_payload_value(self, *, allow_nested: bool = False) -> dict | list:
        if not allow_nested:
            return random.choice(self.payload_values)

        return random.choice(
            (
                {self.get_payload_key(): self.get_payload_value()},
                [self.get_payload_value()],
            )
        )

    ################################
    def clean_request(self, request: dict) -> None:
        """The purpose if this function is to clean requests from corpus that may cause a HTTP 500 response"""

        # request["path"] = request["path"][:self.max_path_length]

        if "_comment" in request:
            del request["_comment"]

        if request["method"] in self.invalid_methods:
            request["method"] = "POST"

        # sinatra returns 500 is json is not a dict
        if "json" in request and not isinstance(request["json"], self.allowed_json_payload_types):
            del request["json"]

        if "headers" in request:
            request["headers"] = [[k, v] for k, v in request["headers"] if k.lower() not in self.invalid_header_keys]

            request["headers"] = [
                [
                    _clean_string(k, allowed=self.header_characters),
                    _clean_string(v, allowed=self.header_characters),
                ]
                for k, v in request["headers"]
            ]

            if not self.allow_colon_in_first_in_header_key:
                request["headers"] = [[re.sub(r"^:*", "", k), v] for k, v in request["headers"]]

            if not self.allow_empty_header_key:
                request["headers"] = [[k, v] for k, v in request["headers"] if len(k) != 0]

    def __str__(self):
        return f"<{self.__class__.__name__}>"


class FlaskRequestMutator(RequestMutator):
    invalid_methods = ("RR RR",)
    header_characters = list(_clean_string("".join(RequestMutator.header_characters), forbidden=" "))


class SinatraRequestMutator(RequestMutator):
    invalid_methods = (
        "PATATE",
        "RR RR",
        "M\x00M",
        "CONNECT",
        "PURGE",
        "MKCALENDAR",
        "UPDATE",
        "CHECKOUT",
        "CHECKIN",
        "SEARCH",
        "LOCK",
        "UPDATE",
        "MOVE",
        "NOTIFY",
        "MKCOL",
        "ORDERPATCH",
        "PROPPATCH",
        "UNLOCK",
        "TRACE",
        "MKACTIVITY",
        "MKCALENDAR",
        "BASELINE-CONTROL",
        "PROPFIND",
        "LABEL",
        "SUBSCRIBE",
        "UNSUBSCRIBE",
        "M-SEARCHMERGE",
        "MKWORKSPACE",
        "UNCHECKOUT",
        "COPY",
        "VERSION-CONTROL",
        "ACL",
        "REPORT",
    )
    max_path_length = 2048
    header_characters = list(
        _clean_string(
            string_lists.latin1,
            forbidden=(
                " [] ¡¢£¤¥¦§¨©ª«¬­®¯°±²³´µ¶·¸¹º»¼½¾¿ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖ×ØÙÚÛÜÝÞßàáâãäåæçèéêëìíîïðñòóôõö÷øùúûüýþÿ"
            ),
        ),
    )
    allowed_json_payload_types = (dict,)
    allow_empty_header_key = False


class NodeRequestMutator(RequestMutator):
    header_characters = list(
        _clean_string(
            string_lists.latin1,
            forbidden=(
                " [] ¡¢£¤¥¦§¨©ª«¬­®¯°±²³´µ¶·¸¹º»¼½¾¿ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖ×"
                'ØÙÚÛÜÝÞßàáâãäåæçèéêëìíîïðñòóôõö÷øùúûüýþÿ\u00a0,\\;/()"<>?!{}=@'
            ),
        ),
    )
    allow_empty_header_key = False

    invalid_methods = (
        "BASELINE-CONTROL",
        "CHECKIN",
        "MKWORKSPACE",
        "LABEL",
        "M-SEARCHMERGE",
        "UPDATE",
        "VERSION-CONTROL",
        "ORDERPATCH",
        "UNCHECKOUT",
    )
    invalid_header_keys = ("Content-length",)


class RailsRequestMutator(RequestMutator):
    invalid_methods = (
        "PATATE",
        "CONNECT",
        "NOTIFY",
        "SUBSCRIBE",
        "UNSUBSCRIBE",
        "M-SEARCHMERGE",
        "PURGE",
    )
    invalid_header_keys = ("Content-length",)
    max_path_length = 2048


class JavaRequestMutator(RequestMutator):
    invalid_methods = (
        "VERSION-CONTROL",
        "UNLOCK",
        "PROPPATCH",
        "LABEL",
        "REPORT",
        "PATH",
        "MKACTIVITY",
        "CHECKOUT",
        "PATCH",
        "MKCOL",
        "MERGE",
        "ORDERPATCH",
        "ACL",
        "MKCALENDAR",
        "MOVE",
        "UPDATE",
        "UNCHECKOUT",
        "SEARCH",
        "PROPFIND",
        "COPY",
        "BASELINE-CONTROL",
        "LOCK",
        "MKWORKSPACE",
        "CHECKIN",
        "PATATE",
        "RR RR",
        "M\x00M",
        "PURGE",
        "M-SEARCHMERGE",
        "NOTIFY",
        "UNSUBSCRIBE",
        "SUBSCRIBE",
    )

    invalid_header_keys = ("Content-length",)

    charsets: tuple[str, ...] = tuple(charset for charset in RequestMutator.charsets if charset not in ("ISO-8859-16",))


class PhpRequestMutator(RequestMutator):
    header_characters = list(
        _clean_string(
            string_lists.latin1,
            forbidden=(
                " []\u00c3¡¢£¤¥¦§¨©ª«¬­®¯°±²³´µ¶·¸¹º»¼½¾¿ÀÁÂÃÄÅÆÇÈÉÊËÌÍÎÏÐÑÒÓÔÕÖ"
                "×ØÙÚÛÜÝÞßàáâãäåæçèéêëìíîïðñòóôõö÷øùúûüýþÿ<>\\\u00a0;()={?,@"
            ),
        ),
    )
    allow_empty_header_key = False
    allow_colon_in_first_in_header_key = False
    invalid_methods = (
        "CHECKIN",
        "UPDATE",
        "VERSION-CONTROL",
        "M-SEARCHMERGE",
        "LABEL",
        "UNCHECKOUT",
        "CONNECT",
        "BASELINE-CONTROL",
        "ORDERPATCH",
        "PURGE",
        "PATATE",
        "MKWORKSPACE",
        "ACL",
        "M\x00M",
        "RR RR",
    )

    invalid_header_keys = ("Content-length",)


def get_mutator(*, no_mutation: bool, weblog: WeblogContainer) -> RequestMutator:
    if weblog.weblog_variant == "basic-sinatra":
        return SinatraRequestMutator(no_mutation=no_mutation)

    if weblog.weblog_variant == "rails":
        return RailsRequestMutator(no_mutation=no_mutation)

    if weblog.library == "java":
        return JavaRequestMutator(no_mutation=no_mutation)

    if weblog.library == "nodejs":
        return NodeRequestMutator(no_mutation=no_mutation)

    if weblog.library == "php":
        return PhpRequestMutator(no_mutation=no_mutation)

    if weblog.weblog_variant == "flask":
        return FlaskRequestMutator(no_mutation=no_mutation)

    return RequestMutator(no_mutation=no_mutation)
