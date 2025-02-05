# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import json
import os
import random
import string
import urllib
import re

import requests
from requests.structures import CaseInsensitiveDict
import grpc
import google.protobuf.struct_pb2 as pb

from utils.tools import logger
import utils.grpc.weblog_pb2_grpc as grpcapi

# monkey patching header validation in requests module, as we want to be able to send anything to weblog
requests.utils._validate_header_part = lambda *args, **kwargs: None  # type: ignore[attr-defined]  # noqa: ARG005, SLF001


class ResponseEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, CaseInsensitiveDict):
            return dict(o.items())
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, o)


# some GRPC request wrapper to fit into validator model
class GrpcRequest:
    def __init__(self, data):
        # self.content = request
        # fake the HTTP header model
        self.headers = {"user-agent": f"rid/{data['rid']}"}


class GrpcResponse:
    def __init__(self, data):
        self._data = data
        self.request = GrpcRequest(data["request"])
        self.response = data["response"]

    def serialize(self) -> dict:
        return self._data | {"__class__": "GrpcResponse"}


class HttpRequest:
    def __init__(self, data):
        self.headers: CaseInsensitiveDict = CaseInsensitiveDict(data.get("headers", {}))
        self.method: str = data["method"]
        self.url: str = data["url"]
        self.params = data["params"]

    def __repr__(self) -> str:
        return f"HttpRequest(method:{self.method}, url:{self.url}, headers:{self.headers})"


class HttpResponse:
    def __init__(self, data):
        self._data = data
        self.request = HttpRequest(data["request"])
        self.status_code = data["status_code"]
        self.headers: CaseInsensitiveDict = CaseInsensitiveDict(data.get("headers", {}))
        self.text = data["text"]
        self.cookies = data["cookies"]

    def serialize(self) -> dict:
        return self._data | {"__class__": "HttpResponse"}

    def __repr__(self) -> str:
        return f"HttpResponse(status_code:{self.status_code}, headers:{self.headers}, text:{self.text})"


# TODO : this should be build by weblog container
class _Weblog:
    def __init__(self):
        if "SYSTEM_TESTS_WEBLOG_PORT" in os.environ:
            self.port = int(os.environ["SYSTEM_TESTS_WEBLOG_PORT"])
        else:
            self.port = 7777

        if "SYSTEM_TESTS_WEBLOG_GRPC_PORT" in os.environ:
            self.grpc_port = int(os.environ["SYSTEM_TESTS_WEBLOG_GRPC_PORT"])
        else:
            self.grpc_port = 7778

        if "SYSTEM_TESTS_WEBLOG_HOST" in os.environ:
            self.domain = os.environ["SYSTEM_TESTS_WEBLOG_HOST"]
        elif "DOCKER_HOST" in os.environ:
            m = re.match(r"(?:ssh:|tcp:|fd:|)//(?:[^@]+@|)([^:]+)", os.environ["DOCKER_HOST"])
            if m is not None:
                self.domain = m.group(1)
            else:
                self.domain = "localhost"
        else:
            self.domain = "localhost"

    def get(self, path="/", params=None, headers=None, cookies=None, **kwargs):
        return self.request("GET", path, params=params, headers=headers, cookies=cookies, **kwargs)

    def post(self, path="/", params=None, data=None, headers=None, **kwargs):
        return self.request("POST", path, params=params, data=data, headers=headers, **kwargs)

    def trace(self, path="/", params=None, data=None, headers=None, **kwargs):
        return self.request("TRACE", path, params=params, data=data, headers=headers, **kwargs)

    def request(
        self,
        method,
        path="/",
        *,
        params=None,
        data=None,
        headers=None,
        cookies=None,
        stream=None,
        domain=None,
        port=None,
        allow_redirects=True,
        rid_in_user_agent=True,
        **kwargs,
    ):
        rid = "".join(random.choices(string.ascii_uppercase, k=36))
        headers = {**headers} if headers else {}  # get our own copy of headers, as we'll modify them

        user_agent_key = "User-Agent"
        for k in headers:
            if k.lower() == "user-agent":
                user_agent_key = k
                break

        user_agent = headers.get(user_agent_key, "system_tests")
        # Inject a request id (rid) to be able to correlate traces generated from this request.
        # This behavior can be disabled with rid_in_user_agent=False, which should be rarely needed.
        if rid_in_user_agent:
            headers[user_agent_key] = f"{user_agent} rid/{rid}"

        if method == "GET" and params:
            url = self._get_url(path, domain, port, params)
        else:
            url = self._get_url(path, domain, port)

        status_code = None
        headers = {}
        text = None
        cookies = None

        timeout = kwargs.pop("timeout", 5)
        try:
            req = requests.Request(method, url, params=params, data=data, headers=headers, cookies=cookies, **kwargs)
            r = req.prepare()
            r.url = url
            logger.debug(f"Sending request {rid}: {method} {url}")

            s = requests.Session()
            response = s.send(r, timeout=timeout, stream=stream, allow_redirects=allow_redirects)
            status_code = response.status_code
            headers = response.headers
            text = response.text
            cookies = requests.utils.dict_from_cookiejar(s.cookies)

        except Exception as e:
            logger.error(f"Request {rid} raise an error: {e}")
        else:
            logger.debug(f"Request {rid}: {response.status_code}")

        return HttpResponse(
            {
                "request": {"method": method, "url": url, "headers": headers, "params": params},
                "status_code": status_code,
                "headers": headers,
                "text": text,
                "cookies": cookies,
            }
        )

    def warmup_request(self, domain=None, port=None, timeout=10):
        requests.get(self._get_url("/", domain, port), timeout=timeout)

    def _get_url(self, path, domain=None, port=None, query=None):
        """Return a query with the passed host"""
        # Make all absolute paths to be relative
        if path.startswith("/"):
            path = path[1:]

        if domain is None:
            domain = self.domain
        if port is None:
            port = self.port

        res = f"http://{domain}:{port}/{path}"

        if query:
            res += "?" + urllib.parse.urlencode(query)

        return res

    def grpc(self, string_value, *, streaming=False):
        rid = "".join(random.choices(string.ascii_uppercase, k=36))

        # We cannot set the user agent for each request. For now, start a new channel for each query
        _grpc_client = grpcapi.WeblogStub(
            grpc.insecure_channel(
                f"{self.domain}:{self.grpc_port}",
                options=(("grpc.enable_http_proxy", 0), ("grpc.primary_user_agent", f"system_tests rid/{rid}")),
            )
        )

        logger.debug(f"Sending grpc request {rid}")

        request = pb.Value(string_value=string_value)
        response_data = None

        try:
            if streaming:
                for response in _grpc_client.ServerStream(request):
                    response_data = response.string_value
            else:
                response = _grpc_client.Unary(request)
                response_data = response.string_value

        except Exception as e:
            logger.error(f"Request {rid} raise an error: {e}")

        return GrpcResponse({"request": {"rid": rid, "string_value": string_value}, "response": response_data})


weblog = _Weblog()
