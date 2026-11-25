# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.
from __future__ import annotations

from utils import features, scenarios
from tests.appsec.iast.utils import BaseSourceTest, get_all_iast_events, get_iast_sources
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from utils import HttpResponse


@features.iast_source_kafka_value
@scenarios.integrations
class TestKafkaValue(BaseSourceTest):
    """Verify that kafka message value is tainted"""

    endpoint = "/iast/source/kafkavalue/test"
    requests_kwargs = [{"method": "GET"}]
    source_type = "kafka.message.value"
    source_value = "hello value!"

    def get_sources(self, request: HttpResponse):  # noqa: ARG002
        iast_event = get_all_iast_events()
        return get_iast_sources(iast_event)
