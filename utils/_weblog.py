# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from collections import defaultdict
import json
import os
import random
import string
import urllib

import requests
import grpc
import google.protobuf.struct_pb2 as pb

from utils.tools import logger
import utils.grpc.weblog_pb2_grpc as grpcapi


class _FailedQuery:
    def __init__(self, request):
        self.request = request
        self.status_code = None


# some GRPC request wrapper to fit into validator model
class GrpcRequest:
    def __init__(self, data):
        # self.content = request
        # fake the HTTP header model
        self.headers = {"user-agent": f"rid/{data['rid']}"}


class GrpcResponse:
    def __init__(self, data):
        self.request = GrpcRequest(data["request"])
        self.response = data["response"]


class HttpRequest:
    def __init__(self, data):
        self.headers = data.get("headers", {})
        self.method = data["method"]
        self.url = data["url"]


class HttpResponse:
    def __init__(self, data):
        self.request = HttpRequest(data["request"])
        self.status_code = data["status_code"]


class _Weblog:
    _grpc_port = 7778

    def __init__(self):
        if "DOCKER_HOST" in os.environ:
            self.domain = os.environ["DOCKER_HOST"]
            self.domain = self.domain.replace("ssh://docker@", "")
        else:
            self.domain = "localhost"

        self.responses = defaultdict(list)
        self.current_nodeid = None  # will be used to store request made by a given nodeid
        self.replay = False

    def init_replay_mode(self, log_folder):
        self.replay = True

        with open(f"{log_folder}/weblog_responses.json", "r", encoding="utf-8") as f:
            self.responses = json.load(f)

    def save_requests(self, log_folder):
        if self.replay:
            return

        try:
            with open(f"{log_folder}/weblog_responses.json", "w", encoding="utf-8") as f:
                json.dump(dict(self.responses), f, indent=2)
        except:
            logger.exception("Can't save responses log")

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
        port=7777,
        allow_redirects=True,
        rid_in_user_agent=True,
        **kwargs,
    ):

        if self.replay:
            return self.get_request_from_logs()

        rid = "".join(random.choices(string.ascii_uppercase, k=36))
        headers = headers or {}

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

        try:
            req = requests.Request(method, url, params=params, data=data, headers=headers, **kwargs)
            r = req.prepare()
            r.url = url
            logger.debug(f"Sending request {rid}: {method} {url}")

            r = requests.Session().send(r, timeout=5, stream=stream, allow_redirects=allow_redirects)
        except Exception as e:
            logger.error(f"Request {rid} raise an error: {e}")
            return _FailedQuery(request=r)

        logger.debug(f"Request {rid}: {r.status_code}")

        self.responses[self.current_nodeid].append(
            {
                "request": {"method": method, "url": url, "headers": headers, "params": params, "data": data},
                "status_code": r.status_code,
            }
        )

        return r

    def get_request_from_logs(self):
        return HttpResponse(self.responses[self.current_nodeid].pop(0))

    def get_grpc_request_from_logs(self):
        return GrpcResponse(self.responses[self.current_nodeid].pop(0))

    def _get_url(self, path, domain, port, query=None):
        """Return a query with the passed host"""
        # Make all absolute paths to be relative
        if path.startswith("/"):
            path = path[1:]

        domain = domain if domain is not None else self.domain

        res = f"http://{domain}:{port}/{path}"

        if query:
            res += "?" + urllib.parse.urlencode(query)

        return res

    def grpc(self, string_value):

        if self.replay:
            return self.get_grpc_request_from_logs()

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

        data = {
            "request": {"rid": rid, "string_value": string_value},
        }

        try:
            _grpc_client.Unary(request)
            data["response"] = "TODO"

        except Exception as e:
            logger.error(f"Request {rid} raise an error: {e}")
            data["response"] = None

        self.responses[self.current_nodeid].append(data)

        return GrpcResponse(data)


weblog = _Weblog()
