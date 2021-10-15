# Unless explicitly stated otherwise all files in this repository are licensed under the the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2021 Datadog, Inc.

from utils import BaseTestCase, context, interfaces, skipif, released


@released(cpp="not relevant")
@released(golang="?" if context.weblog_variant != "echo-poc" else "not relevant: echo is not instrumented")
@released(dotnet="1.29.0", java="?", nodejs="?", php="?", python="?", ruby="?")
class Test_Retention(BaseTestCase):
    def test_events_retain_traces(self):
        """ AppSec retain APM traces when associated with a security event. """

        APPSEC_KEEP = 4

        def validate_appsec_span(span):
            if span.get("parent_id") not in (0, None):  # do nothing if not root span
                return

            if "appsec.event" not in span["meta"]:
                raise Exception("Can't find appsec.event in span's meta")

            if span["meta"]["appsec.event"] != "true":
                raise Exception(f'appsec.event in span\'s meta should be "true", not {span["meta"]["appsec.event"]}')

            if "_sampling_priority_v1" not in span["metrics"]:
                raise Exception("Metric _sampling_priority_v1 should be set on traces that are manually kept")

            if span["metrics"]["_sampling_priority_v1"] != APPSEC_KEEP:
                raise Exception(f"Trace id {span['trace_id']} , sampling priority should be {APPSEC_KEEP}")

            return True

        r = self.weblog_get("/waf/", headers={"User-Agent": "Arachni/v1"})
        interfaces.library.add_span_validation(r, validate_appsec_span)


@released(cpp="not relevant")
@released(golang="?" if context.weblog_variant != "echo-poc" else "not relevant: echo is not instrumented")
@released(dotnet="1.29.0", java="?", nodejs="?", php="?", python="?", ruby="?")
class Test_AppSecMonitoring(BaseTestCase):
    def test_events_retain_traces(self):
        """ AppSec store in APM traces some data when enabled. """

        RUNTIME_FAMILY = ["nodejs", "ruby", "jvm", "dotnet", "go", "php", "python"]

        def validate_appsec_span(span):
            if span.get("parent_id") not in (0, None):  # do nothing if not root span
                return

            if "_dd.appsec.enabled" not in span["metrics"]:
                raise Exception("Can't find _dd.appsec.enabled in span's metrics")

            if span["metrics"]["_dd.appsec.enabled"] != "true":
                raise Exception(
                    f'_dd.appsec.enabled in span\'s metrics should be "true", not {span["metrics"]["_dd.appsec.enabled"]}'
                )

            if "_dd.runtime_family" not in span["meta"]:
                raise Exception("Can't find _dd.runtime_family in span's meta")

            if span["metrics"]["_dd.runtime_family"] not in RUNTIME_FAMILY:
                raise Exception(f"_dd.runtime_family {span['_dd.runtime_family']} , should be in {RUNTIME_FAMILY}")

            return True

        interfaces.library.add_span_validation(validator=validate_appsec_span)
