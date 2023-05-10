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
        interfaces.library.expect_iast_vulnerabilities(
            self.insecure_request,
            vulnerability_count=1,
            vulnerability_type=self.vulnerability_type,
            location_path=self.expected_location,
            evidence=self.expected_evidence,
        )

    def setup_secure(self):
        if self.secure_request is None:
            self.secure_request = weblog.request(method=self.http_method, path=self.secure_endpoint, data=self.data)

    def test_secure(self):
        interfaces.library.expect_no_vulnerabilities(self.secure_request)

    def setup_telemetry_metric_instrumented_sink(self):
        self.setup_insecure()

    def test_telemetry_metric_instrumented_sink(self):
        expected_namespace = "iast"
        expected_metric = "instrumented.sink"
        series = _find_telemetry_metric_series("generate-metrics", expected_namespace, expected_metric)
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
        series = _find_telemetry_metric_series("generate-metrics", expected_namespace, expected_metric)
        assert len(series) >= 1
        logging.debug(f"Metrics: {series}")
        expected_tag = f"vulnerability_type:{self.vulnerability_type}"
        relevant_series = [s for s in series if expected_tag in s["tags"]]
        assert len(relevant_series) >= 1
        for s in relevant_series:
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
        interfaces.library.expect_iast_sources(
            self.request, source_count=1, origin=self.source_type, name=self.source_name, value=self.source_value,
        )

    def setup_telemetry_metric_instrumented_source(self):
        self.setup()

    def test_telemetry_metric_instrumented_source(self):
        expected_namespace = "iast"
        expected_metric = "instrumented.source"
        series = _find_telemetry_metric_series("generate-metrics", expected_namespace, expected_metric)
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
        series = _find_telemetry_metric_series("generate-metrics", expected_namespace, expected_metric)
        assert len(series) >= 1
        logging.debug(f"Metrics: {series}")
        expected_tag = f"source_type:{self.source_type}"
        relevant_series = [s for s in series if expected_tag in s["tags"]]
        assert len(relevant_series) >= 1
        for s in relevant_series:
            assert s["_computed_namespace"] == expected_namespace
            assert s["metric"] == expected_metric
            assert s["common"] is True
            assert s["type"] == "count"
            assert set(s["tags"]) == {expected_tag}
            assert len(s["points"]) == 1
            p = s["points"][0]
            assert p[1] >= 1


def _find_telemetry_metric_series(request_type, namespace, metric):
    series = []
    for data in interfaces.library.get_telemetry_data():
        content = data["request"]["content"]
        if content.get("request_type") != request_type:
            continue
        fallback_namespace = content["payload"].get("namespace")
        for serie in content["payload"]["series"]:
            computed_namespace = serie.get("namespace", fallback_namespace)
            # Inject here the computed namespace considering the fallback. This simplifies later assertions.
            serie["_computed_namespace"] = computed_namespace
            if computed_namespace == namespace and serie["metric"] == metric:
                series.append(serie)
    return series
