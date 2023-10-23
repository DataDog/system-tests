# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

import os
import random
import string
import urllib
import re

import requests
import grpc
import google.protobuf.struct_pb2 as pb

from utils.tools import logger, HttpResponse, GrpcResponse
import utils.grpc.weblog_pb2_grpc as grpcapi


class _Weblog:
    def __init__(self):
        if "SYSTEM_TESTS_WEBLOG_PORT" in os.environ:
            self.port = int(os.environ["SYSTEM_TESTS_WEBLOG_PORT"])
        else:
            self.port = 7777

        if "SYSTEM_TESTS_WEBLOG_GRPC_PORT" in os.environ:
            self._grpc_port = int(os.environ["SYSTEM_TESTS_WEBLOG_GRPC_PORT"])
        else:
            self._grpc_port = 7778

        if "SYSTEM_TESTS_WEBLOG_HOST" in os.environ:
            self.domain = os.environ["SYSTEM_TESTS_WEBLOG_HOST"]
        elif "DOCKER_HOST" in os.environ:
            m = re.match(r"(?:ssh:|tcp:|fd:|)//(?:[^@]+@|)([^:]+)", os.environ["DOCKER_HOST"])
            if m is not None:
                self.domain = m.group(1)
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
        params=None,
        data=None,
        headers=None,
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

        response_data = {
            "request": {"method": method, "url": url, "headers": headers, "params": params},
            "status_code": None,
            "headers": {},
            "text": None,
        }

        timeout = kwargs.pop("timeout", 5)
        try:
            req = requests.Request(method, url, params=params, data=data, headers=headers, **kwargs)
            r = req.prepare()
            r.url = url
            logger.debug(f"Sending request {rid}: {method} {url}")

            r = requests.Session().send(r, timeout=timeout, stream=stream, allow_redirects=allow_redirects)
            response_data["status_code"] = r.status_code
            response_data["headers"] = r.headers
            response_data["text"] = r.text

        except Exception as e:
            logger.error(f"Request {rid} raise an error: {e}")
        else:
            logger.debug(f"Request {rid}: {r.status_code}")

        return HttpResponse(response_data)

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

    def grpc(self, string_value):

        rid = "".join(random.choices(string.ascii_uppercase, k=36))

        # We cannot set the user agent for each request. For now, start a new channel for each query
        _grpc_client = grpcapi.WeblogStub(
            grpc.insecure_channel(
                f"{self.domain}:{self._grpc_port}",
                options=(("grpc.enable_http_proxy", 0), ("grpc.primary_user_agent", f"system_tests rid/{rid}")),
            )
        )

        logger.debug(f"Sending grpc request {rid}")

        request = pb.Value(string_value=string_value)  # pylint: disable=no-member

        response_data = {
            "request": {"rid": rid, "string_value": string_value},
        }

        try:
            _grpc_client.Unary(request)
            response_data["response"] = "TODO"

        except Exception as e:
            logger.error(f"Request {rid} raise an error: {e}")
            response_data["response"] = None

        return GrpcResponse(response_data)


weblog = _Weblog()
