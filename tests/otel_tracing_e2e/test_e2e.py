import json
import os

from opentelemetry import trace, propagate
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import DEPLOYMENT_ENVIRONMENT, Resource, SERVICE_NAME
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.semconv.trace import SpanAttributes
from opentelemetry.propagators.b3 import B3MultiFormat, B3SingleFormat
from _validator import validate_trace
from utils import context, weblog, interfaces, scenarios, missing_feature


class E2ETestBase:
    def setup_main(self):
        self.setup_opentelemetry()
        self.use_128_bits_trace_id = False
        with self.tracer.start_as_current_span(name="runner.get", kind=trace.SpanKind.CLIENT) as span:
            span.set_attribute(SpanAttributes.HTTP_METHOD, "GET")
            span.set_attribute(SpanAttributes.HTTP_URL, "http://weblog:7777")
            headers = {}
            propagate.get_global_textmap().inject(headers)
            self.r = weblog.get(path="/", headers=headers)
            span.set_attribute(SpanAttributes.HTTP_STATUS_CODE, self.r.status_code)
            self.trace_id = span.get_span_context().trace_id
            self.root_span_id = span.get_span_context().span_id

    def setup_opentelemetry(self):
        resource = Resource.create(
            attributes={SERVICE_NAME: "system-tests-runner", DEPLOYMENT_ENVIRONMENT: "system-tests"}
        )
        dd_site = os.environ.get("DD_SITE")
        if dd_site is None or dd_site == "":
            dd_site = "datad0g.com"
        exporter = OTLPSpanExporter(
            endpoint=f"https://trace.agent.{dd_site}/api/v0.2/traces",
            headers={"dd-protocol": "otlp", "dd-api-key": os.environ.get("DD_API_KEY"),},
        )
        processor = BatchSpanProcessor(span_exporter=exporter, max_export_batch_size=1)
        trace.set_tracer_provider(TracerProvider(resource=resource, active_span_processor=processor))
        self.tracer = trace.get_tracer("system-tests-runner")

    def test_main(self):
        response = interfaces.backend._wait_for_trace(
            rid=self.r, trace_id=self._get_dd_trace_id(), retries=5, sleep_interval_multiplier=2.0
        )
        trace_data = json.loads(response["response"]["content"])["trace"]
        validate_trace(trace_data, self._get_dd_trace_id(), self.root_span_id, self.trace_id)

    def _get_dd_trace_id(self):
        if self.use_128_bits_trace_id:
            return self.trace_id
        trace_id_bytes = self.trace_id.to_bytes(16, "big")
        return int.from_bytes(trace_id_bytes[8:], "big")


@scenarios.otel_tracing_e2e_w3c
@missing_feature(
    context.library != "java_otel", reason="OTel tests only support OTel instrumented applications at the moment.",
)
class Test_E2E_W3C(E2ETestBase):
    pass  # Use the default propagator TraceContextTextMapPropagator (W3C propagator)


@scenarios.otel_tracing_e2e_b3
@missing_feature(
    context.library != "java_otel", reason="OTel tests only support OTel instrumented applications at the moment.",
)
class Test_E2E_B3(E2ETestBase):
    def setup_main(self):
        propagate.set_global_textmap(B3SingleFormat())
        E2ETestBase.setup_main(self)


@scenarios.otel_tracing_e2e_b3_multi
@missing_feature(
    context.library != "java_otel", reason="OTel tests only support OTel instrumented applications at the moment.",
)
class Test_E2E_B3_Multi(E2ETestBase):
    def setup_main(self):
        propagate.set_global_textmap(B3MultiFormat())
        E2ETestBase.setup_main(self)
