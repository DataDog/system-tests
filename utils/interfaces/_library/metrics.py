# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils.interfaces._core import BaseValidation


class _BaseMetricValidation(BaseValidation):
    path_filters = "/v0.4/traces"

    def __init__(self, metric_name):
        super().__init__()
        self.metric_name = metric_name

    def check(self, data):
        for item in data["request"]["content"]:
            for sub_item in item:
                if "metrics" in sub_item and self.metric_name in sub_item["metrics"]:
                    self.set_status(not self.is_success_on_expiry)
                    break


class _MetricExistence(_BaseMetricValidation):
    is_success_on_expiry = False


class _MetricAbsence(_BaseMetricValidation):
    is_success_on_expiry = True
