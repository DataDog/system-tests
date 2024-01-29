# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import coverage, features, scenarios
from .._test_iast_fixtures import BaseSourceTest, get_all_iast_events, get_iast_sources


@coverage.basic
@features.iast_source_kafka_key
class TestKafkaKey(BaseSourceTest):
    """Verify that kafka message key is tainted"""

    endpoint = "/iast/source/kafkakey/test"
    requests_kwargs = [{"method": "GET"}]
    source_type = "kafka.message.key"
    source_names = ["key"]
    source_value = "hello key!"

    @scenarios.integrations
    def test_source_reported(self):
        super().test_source_reported()

    def get_sources(self, request):
        iast_event = get_all_iast_events()
        return get_iast_sources(iast_event)

    @scenarios.integrations
    def test_telemetry_metric_instrumented_source(self):
        return super().test_telemetry_metric_instrumented_source()

    @scenarios.integrations
    def test_telemetry_metric_executed_source(self):
        return super().test_telemetry_metric_executed_source()
