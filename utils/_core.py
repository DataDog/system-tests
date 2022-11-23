# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.


from ._weblog import weblog


class BaseTestCase:
    def weblog_get(self, path="/", params=None, headers=None, cookies=None, **kwargs):
        return weblog.get(path, params=params, headers=headers, cookies=cookies, **kwargs)

    def weblog_post(self, path="/", params=None, data=None, headers=None, **kwargs):
        return weblog.post(path, params=params, data=data, headers=headers, **kwargs)

    def weblog_trace(self, path="/", params=None, data=None, headers=None, **kwargs):
        return weblog.trace(path, params=params, data=data, headers=headers, **kwargs)

    def weblog_request(self, method, path="/", params=None, data=None, headers=None, **kwargs):
        return weblog.request(method, path, params=params, data=data, headers=headers, **kwargs)

    def weblog_grpc(self, string_value):
        return weblog.grpc(string_value)
