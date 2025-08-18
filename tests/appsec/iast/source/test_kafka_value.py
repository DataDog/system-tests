# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import features, scenarios
from tests.appsec.iast.utils import BaseSourceTest, get_all_iast_events, get_iast_sources
from utils._context._scenarios.dynamic import dynamic_scenario



@features.iast_source_kafka_value
@dynamic_scenario(mandatory={})
class TestKafkaValue(BaseSourceTest):
    """Verify that kafka message value is tainted"""

    endpoint = "/iast/source/kafkavalue/test"
    requests_kwargs = [{"method": "GET"}]
    source_type = "kafka.message.value"
    source_value = "hello value!"

    def get_sources(self, request):  # noqa: ARG002
        iast_event = get_all_iast_events()
        return get_iast_sources(iast_event)
