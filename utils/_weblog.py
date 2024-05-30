# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from collections import defaultdict
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

from utils.tools import logger, generate_curl_command
import utils.grpc.weblog_pb2_grpc as grpcapi

# monkey patching header validation in requests module, as we want to be able to send anything to weblog
requests.utils._validate_header_part = lambda *args, **kwargs: None  # pylint: disable=protected-access


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
        self.request = GrpcRequest(data["request"])
        self.response = data["response"]


class HttpRequest:
    def __init__(self, data):
        self.headers = CaseInsensitiveDict(data.get("headers", {}))
        self.method = data["method"]
        self.url = data["url"]

    def __repr__(self) -> str:
        return f"HttpRequest(method:{self.method}, url:{self.url}, headers:{self.headers})"


class HttpResponse:
    def __init__(self, data):
        self.request = HttpRequest(data["request"])
        self.status_code = data["status_code"]
        self.headers = CaseInsensitiveDict(data.get("headers", {}))
        self.text = data["text"]


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
                json.dump(dict(self.responses), f, indent=2, cls=ResponseEncoder)
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
        cookies=None,
        stream=None,
        domain=None,
        port=None,
        allow_redirects=True,
        rid_in_user_agent=True,
        **kwargs,
    ):

        if self.current_nodeid is None:
            raise ValueError("Weblog calls can only be done during setup")

        if self.replay:
            return self.get_request_from_logs()

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
            req = requests.Request(method, url, params=params, data=data, headers=headers, cookies=cookies, **kwargs)
            r = req.prepare()
            r.url = url
            curl_command = generate_curl_command(method, url, headers, params)
            logger.debug(f"Sending request {rid}: {method} {url}")
            logger.info(f"Here is a curl command to try it out: {curl_command}")

            r = requests.Session().send(r, timeout=timeout, stream=stream, allow_redirects=allow_redirects)
            response_data["status_code"] = r.status_code
            response_data["headers"] = r.headers
            response_data["text"] = r.text

        except Exception as e:
            logger.error(f"Request {rid} raise an error: {e}")
            logger.info(f"Here is the culprit:  {curl_command}")

        else:
            logger.debug(f"Request {rid}: {r.status_code}")
            logger.info(f"To try it out: {curl_command} {curl_command}")

        self.responses[self.current_nodeid].append(response_data)

        return HttpResponse(response_data)

    def get_request_from_logs(self):
        return HttpResponse(self._pop_response_data_from_logs())

    def get_grpc_request_from_logs(self):
        return GrpcResponse(self._pop_response_data_from_logs())

    def _pop_response_data_from_logs(self):
        if self.current_nodeid not in self.responses:
            raise ValueError(
                f"I do not have any request made by {self.current_nodeid}. You may need to relaunch it in normal mode"
            )

        if len(self.responses[self.current_nodeid]) == 0:
            raise ValueError(
                f"I have no more request made by {self.current_nodeid}. You may need to relaunch it in normal mode"
            )

        return self.responses[self.current_nodeid].pop(0)

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

        if self.replay:
            return self.get_grpc_request_from_logs()

        if self.current_nodeid is None:
            raise ValueError("Weblog calls can only be done during setup")

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

        self.responses[self.current_nodeid].append(response_data)

        return GrpcResponse(response_data)


weblog = _Weblog()
