import json

from utils import weblog, interfaces, context
from utils.tools import logging


def _get_expectation(d):
    if d is None:
        return None
    if isinstance(d, str):
        return d
    elif callable(d):
        return d()
    else:
        expected = d.get(context.library.library)
        if isinstance(expected, dict):
            expected = expected.get(context.weblog_variant)
        return expected


def _get_span_meta(request):
    spans = [span for _, span in interfaces.library.get_root_spans(request=request)]
    assert spans, "No root span found"
    span = spans[0]
    meta = span.get("meta", {})
    return meta


def get_iast_event(request):
    meta = _get_span_meta(request=request)
    assert "_dd.iast.json" in meta, "No _dd.iast.json tag in span"
    return json.loads(meta["_dd.iast.json"])


def assert_iast_vulnerability(
    request, vulnerability_count=1, vulnerability_type=None, expected_location=None, expected_evidence=None
):
    iast = get_iast_event(request=request)
    assert iast["vulnerabilities"], "Expected at least one vulnerability"
    vulns = iast["vulnerabilities"]
    if vulnerability_type:
        vulns = [v for v in vulns if v["type"] == vulnerability_type]
        assert vulns, f"No vulnerability of type {vulnerability_type}"
    if expected_location:
        vulns = [v for v in vulns if v.get("location", {}).get("path", "") == expected_location]
        assert vulns, f"No vulnerability with location {expected_location}"
    if expected_evidence:
        vulns = [v for v in vulns if v.get("evidence", {}).get("value", "") == expected_evidence]
        assert vulns, f"No vulnerability with evidence value {expected_evidence}"
    assert len(vulns) == vulnerability_count


class SinkFixture:
    def __init__(
        self,
        vulnerability_type,
        http_method,
        insecure_endpoint,
        secure_endpoint,
        data,
        location_map=None,
        evidence_map=None,
    ):
        self.vulnerability_type = vulnerability_type
        self.http_method = http_method
        self.insecure_endpoint = insecure_endpoint
        self.secure_endpoint = secure_endpoint
        self.data = data
        self.expected_location = _get_expectation(location_map)
        self.expected_evidence = _get_expectation(evidence_map)
        self.insecure_request = None
        self.secure_request = None

    def setup_insecure(self):
        if self.insecure_request is None:
            self.insecure_request = weblog.request(method=self.http_method, path=self.insecure_endpoint, data=self.data)

    def test_insecure(self):
        assert_iast_vulnerability(
            request=self.insecure_request,
            vulnerability_count=1,
            vulnerability_type=self.vulnerability_type,
            expected_location=self.expected_location,
            expected_evidence=self.expected_evidence,
        )

    def setup_secure(self):
        if self.secure_request is None:
            self.secure_request = weblog.request(method=self.http_method, path=self.secure_endpoint, data=self.data)

    def test_secure(self):
        meta = _get_span_meta(request=self.secure_request)
        iast_json = meta.get("_dd.iast.json")
        assert iast_json is None, f"Unexpected vulnerabilities reported: {iast_json}"

    def setup_telemetry_metric_instrumented_sink(self):
        self.setup_insecure()

    def test_telemetry_metric_instrumented_sink(self):
        expected_namespace = "iast"
        expected_metric = "instrumented.sink"
        series = interfaces.library.get_telemetry_metric_series(expected_namespace, expected_metric)
        assert series, f"Got no series for metric {expected_metric}"
        logging.debug("Series: %s", series)
        expected_tag = f"vulnerability_type:{self.vulnerability_type}"
        series = [s for s in series if expected_tag in s["tags"]]
        assert series, f"Got no series for metric {expected_metric} with tag {expected_tag}"
        for s in series:
            assert s["_computed_namespace"] == expected_namespace
            assert s["metric"] == expected_metric
            assert s["common"] is True
            assert s["type"] == "count"
            assert set(s["tags"]) == {expected_tag}
            assert len(s["points"]) == 1
            p = s["points"][0]
            assert p[1] >= 1

    def setup_telemetry_metric_executed_sink(self):
        self.setup_insecure()

    def test_telemetry_metric_executed_sink(self):
        expected_namespace = "iast"
        expected_metric = "executed.sink"
        series = interfaces.library.get_telemetry_metric_series(expected_namespace, expected_metric)
        assert series, f"Got no series for metric {expected_metric}"
        logging.debug("Series: %s", series)
        expected_tag = f"vulnerability_type:{self.vulnerability_type}"
        series = [s for s in series if expected_tag in s["tags"]]
        assert series, f"Got no series for metric {expected_metric} with tag {expected_tag}"
        for s in series:
            assert s["_computed_namespace"] == expected_namespace
            assert s["metric"] == expected_metric
            assert s["common"] is True
            assert s["type"] == "count"
            assert set(s["tags"]) == {expected_tag}
            assert len(s["points"]) == 1
            p = s["points"][0]
            assert p[1] >= 1


class SourceFixture:
    def __init__(self, http_method, endpoint, request_kwargs, source_type, source_name, source_value):
        self.http_method = http_method
        self.endpoint = endpoint
        self.request_kwargs = request_kwargs
        self.source_type = source_type
        self.source_name = source_name
        self.source_value = source_value
        self.request = None

    def setup(self):
        if self.request is None:
            self.request = weblog.request(method=self.http_method, path=self.endpoint, **self.request_kwargs)

    def test(self):
        iast = get_iast_event(request=self.request)
        sources = iast["sources"]
        assert sources, "No source reported"
        if self.source_type:
            assert self.source_type in {s.get("origin") for s in sources}
            sources = [s for s in sources if s["origin"] == self.source_type]
        if self.source_name:
            assert self.source_name in {s.get("name") for s in sources}
            sources = [s for s in sources if s["name"] == self.source_name]
        if self.source_value:
            assert self.source_value in {s.get("value") for s in sources}
            sources = [s for s in sources if s["value"] == self.source_value]
        assert (
            sources
        ), f"No source found with origin={self.source_type}, name={self.source_name}, value={self.source_value}"
        assert len(sources) == 1, "Expected a single source with the matching criteria"

    def setup_telemetry_metric_instrumented_source(self):
        self.setup()

    def test_telemetry_metric_instrumented_source(self):
        expected_namespace = "iast"
        expected_metric = "instrumented.source"
        series = interfaces.library.get_telemetry_metric_series(expected_namespace, expected_metric)
        assert series, f"Got no series for metric {expected_metric}"
        logging.debug("Series: %s", series)
        expected_tag = f"source_type:{self.source_type}"
        series = [s for s in series if expected_tag in s["tags"]]
        assert series, f"Got no series for metric {expected_metric} with tag {expected_tag}"
        for s in series:
            assert s["_computed_namespace"] == expected_namespace
            assert s["metric"] == expected_metric
            assert s["common"] is True
            assert s["type"] == "count"
            assert set(s["tags"]) == {expected_tag}
            assert len(s["points"]) == 1
            p = s["points"][0]
            assert p[1] >= 1

    def setup_telemetry_metric_executed_source(self):
        self.setup()

    def test_telemetry_metric_executed_source(self):
        expected_namespace = "iast"
        expected_metric = "executed.source"
        series = interfaces.library.get_telemetry_metric_series(expected_namespace, expected_metric)
        assert series, f"Got no series for metric {expected_metric}"
        logging.debug("Series: %s", series)
        expected_tag = f"source_type:{self.source_type}"
        series = [s for s in series if expected_tag in s["tags"]]
        assert series, f"Got no series for metric {expected_metric} with tag {expected_tag}"
        for s in series:
            assert s["_computed_namespace"] == expected_namespace
            assert s["metric"] == expected_metric
            assert s["common"] is True
            assert s["type"] == "count"
            assert set(s["tags"]) == {expected_tag}
            assert len(s["points"]) == 1
            p = s["points"][0]
            assert p[1] >= 1
