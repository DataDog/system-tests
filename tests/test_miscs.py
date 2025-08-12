# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2022 Datadog, Inc.

from utils import weblog, interfaces, features, context

# those tests are linked to unix_domain_sockets_support_for_traces only for UDS weblogs
optional_uds_feature = (
    features.unix_domain_sockets_support_for_traces if "uds" not in context.weblog_variant else features.not_reported
)


@optional_uds_feature
class Test_Basic:
    """Make sure the spans endpoint is successful"""

    def setup_spans_generation(self):
        self.r = weblog.get("/spans")

    def test_spans_generation(self):
        interfaces.library.assert_trace_exists(self.r, span_type="web")
