from enum import Enum
import json
from utils import weblog, interfaces, context
from utils.tools import logging

DetectionStage = Enum("DetectionStage", ["REQUEST", "STARTUP"])


def _get_expectation(d):
    if d is None or isinstance(d, str):
        return d

    if isinstance(d, dict):
        expected = d.get(context.library.library)
        if isinstance(expected, dict):
            expected = expected.get(context.weblog_variant)
        return expected

    raise TypeError(f"Unsupported expectation type: {d}")


def _get_span_meta(request):
    spans = [span for _, span in interfaces.library.get_root_spans(request=request)]
    assert spans, "No root span found"
    span = spans[0]
    meta = span.get("meta", {})
    return meta


def get_iast_event(request):
    meta = _get_span_meta(request=request)
    assert "_dd.iast.json" in meta, "No _dd.iast.json tag in span"
    return meta["_dd.iast.json"]


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


def _check_telemetry_response_from_agent():
    # Java tracer (at least) disable telemetry if agent answer 403
    # Checking that agent answers 200
    # we do not fail the test, because we are not sure it's the official behavior
    for data in interfaces.library.get_telemetry_data():
        code = data["response"]["status_code"]
        if code != 200:
            filename = data["log_filename"]
            logging.warning(f"Agent answered {code} on {filename}, it may cause telemetry issues")
            return


class BaseSinkTestWithoutTelemetry:
    vulnerability_type = None
    http_method = None
    insecure_endpoint = None
    secure_endpoint = None
    params = None
    data = None
    headers = None
    location_map = None
    evidence_map = None

    insecure_request = None
    secure_request = None

    detection_stage = DetectionStage.REQUEST

    @property
    def expected_location(self):
        return _get_expectation(self.location_map)

    @property
    def expected_evidence(self):
        return _get_expectation(self.evidence_map)

    def setup_insecure(self):

        # optimize by attaching requests to the class object, to avoid calling it several times. We can't attach them
        # to self, and we need to attach the request on class object, as there are one class instance by test case

        if self.__class__.insecure_request is None:
            assert self.insecure_endpoint is not None, f"{self}.insecure_endpoint must not be None"

            self.__class__.insecure_request = weblog.request(
                method=self.http_method,
                path=self.insecure_endpoint,
                params=self.params,
                data=self.data,
                headers=self.headers,
            )

        self.insecure_request = self.__class__.insecure_request

    def test_insecure(self):
        assert_iast_vulnerability(
            request=self.insecure_request if self.detection_stage == DetectionStage.REQUEST else None,
            vulnerability_count=1,
            vulnerability_type=self.vulnerability_type,
            expected_location=self.expected_location,
            expected_evidence=self.expected_evidence,
        )

    def setup_secure(self):

        # optimize by attaching requests to the class object, to avoid calling it several times. We can't attach them
        # to self, and we need to attach the request on class object, as there are one class instance by test case

        if self.__class__.secure_request is None:
            assert self.secure_endpoint is not None, f"Please set {self}.secure_endpoint"
            assert isinstance(self.secure_endpoint, str), f"Please set {self}.secure_endpoint"

            self.__class__.secure_request = weblog.request(
                method=self.http_method,
                path=self.secure_endpoint,
                params=self.params,
                data=self.data,
                headers=self.headers,
            )

        self.secure_request = self.__class__.secure_request

    def test_secure(self):
        self.assert_no_iast_event(self.secure_request)

    @staticmethod
    def assert_no_iast_event(request):
        meta = _get_span_meta(request=request)
        iast_json = meta.get("_dd.iast.json")
        assert iast_json is None, f"Unexpected vulnerabilities reported: {iast_json}"


class BaseSinkTest(BaseSinkTestWithoutTelemetry):
    def setup_telemetry_metric_instrumented_sink(self):
        self.setup_insecure()

    def test_telemetry_metric_instrumented_sink(self):

        _check_telemetry_response_from_agent()

        expected_namespace = "iast"
        expected_metric = "instrumented.sink"
        series = interfaces.library.get_telemetry_metric_series(expected_namespace, expected_metric)
        assert series, f"Got no series for metric {expected_metric}"
        logging.debug("Series: %s", series)

        # lower the vulnerability_type, as all assertion will be case-insensitive
        expected_tag = f"vulnerability_type:{self.vulnerability_type}".lower()

        # Filter by taking only series where expected tag is in the list serie.tags (case insentive check)
        series = [serie for serie in series if expected_tag in map(str.lower, serie["tags"])]

        assert len(series) != 0, f"Got no series for metric {expected_metric} with tag {expected_tag}"

        for s in series:
            assert s["_computed_namespace"] == expected_namespace
            assert s["metric"] == expected_metric
            assert s["common"] is True
            assert s["type"] == "count"
            assert len(s["points"]) == 1
            p = s["points"][0]
            assert p[1] >= 1

    def setup_telemetry_metric_executed_sink(self):
        self.setup_insecure()

    def test_telemetry_metric_executed_sink(self):

        _check_telemetry_response_from_agent()

        expected_namespace = "iast"
        expected_metric = "executed.sink"
        series = interfaces.library.get_telemetry_metric_series(expected_namespace, expected_metric)
        assert series, f"Got no series for metric {expected_metric}"
        logging.debug("Series: %s", series)

        # lower the vulnerability_type, as all assertion will be case-insensitive
        expected_tag = f"vulnerability_type:{self.vulnerability_type}".lower()

        # Filter by taking only series where expected tag is in the list serie.tags (case insentive check)
        series = [serie for serie in series if expected_tag in map(str.lower, serie["tags"])]

        assert len(series) != 0, f"Got no series for metric {expected_metric} with tag {expected_tag}"

        for s in series:
            assert s["_computed_namespace"] == expected_namespace
            assert s["metric"] == expected_metric
            assert s["common"] is True
            assert s["type"] == "count"
            assert len(s["points"]) == 1
            p = s["points"][0]
            assert p[1] >= 1


class BaseSourceTest:
    endpoint = None
    requests_kwargs = None
    source_type = None
    source_names = None
    source_value = None
    requests: dict = None

    def setup_source_reported(self):
        assert isinstance(self.requests_kwargs, list), f"{self.__class__}.requests_kwargs must be a list of dicts"

        # optimize by attaching requests to the class object, to avoid calling it several times. We can't attach them
        # to self, and we need to attach the request on class object, as there are one class instance by test case

        if self.__class__.requests is None:
            self.__class__.requests = {}
            for kwargs in self.requests_kwargs:
                method = kwargs["method"]
                # store them as method:request to allow later custom test by method
                self.__class__.requests[method] = weblog.request(path=self.endpoint, **kwargs)

        self.requests = self.__class__.requests

    def test_source_reported(self):
        for request in self.requests.values():
            self.validate_request_reported(request)

    def validate_request_reported(self, request, source_type=None):
        if source_type is None:  # allow to overwrite source_type for parameter value node's use case
            source_type = self.source_type

        iast = get_iast_event(request=request)
        sources = iast["sources"]
        assert sources, "No source reported"
        if source_type:
            assert source_type in {s.get("origin") for s in sources}
            sources = [s for s in sources if s["origin"] == source_type]
        if self.source_names:
            assert isinstance(self.source_names, list)
            assert any(x in self.source_names for x in {s.get("name") for s in sources})
            sources = [s for s in sources if s["name"] in self.source_names]
        if self.source_value:
            assert self.source_value in {s.get("value") for s in sources}
            sources = [s for s in sources if s["value"] == self.source_value]
        assert (
            sources
        ), f"No source found with origin={source_type}, name={self.source_names}, value={self.source_value}"
        assert len(sources) == 1, "Expected a single source with the matching criteria"

    setup_telemetry_metric_instrumented_source = setup_source_reported

    def test_telemetry_metric_instrumented_source(self):

        _check_telemetry_response_from_agent()

        expected_namespace = "iast"
        expected_metric = "instrumented.source"
        series = interfaces.library.get_telemetry_metric_series(expected_namespace, expected_metric)
        assert series, f"Got no series for metric {expected_metric}"
        logging.debug(f"Series: {json.dumps(series, indent=2)}")

        # lower the source_type, as all assertion will be case-insensitive
        expected_tag = f"source_type:{self.source_type}".lower()

        # Filter by taking only series where expected tag is in the list serie.tags (case insentive check)
        series = [serie for serie in series if expected_tag in map(str.lower, serie["tags"])]

        assert len(series) != 0, f"Got no series for metric {expected_metric} with tag {expected_tag}"

        for s in series:
            assert s["_computed_namespace"] == expected_namespace
            assert s["metric"] == expected_metric
            assert s["common"] is True
            assert s["type"] == "count"
            assert len(s["points"]) == 1
            p = s["points"][0]
            assert p[1] >= 1

    setup_telemetry_metric_executed_source = setup_source_reported

    def test_telemetry_metric_executed_source(self):

        _check_telemetry_response_from_agent()

        expected_namespace = "iast"
        expected_metric = "executed.source"
        series = interfaces.library.get_telemetry_metric_series(expected_namespace, expected_metric)
        assert series, f"Got no series for metric {expected_metric}"

        # lower the source_type, as all assertion will be case-insensitive
        expected_tag = f"source_type:{self.source_type}".lower()

        # Filter by taking only series where expected tag is in the list serie.tags (case insentive check)
        series = [serie for serie in series if expected_tag in map(str.lower, serie["tags"])]

        assert len(series) != 0, f"Got no series for metric {expected_metric} with tag {expected_tag}"

        logging.debug(f"Series:\n{json.dumps(series, indent=2)}")

        for s in series:
            assert s["_computed_namespace"] == expected_namespace
            assert s["metric"] == expected_metric
            assert s["common"] is True
            assert s["type"] == "count"
            assert len(s["points"]) == 1
            p = s["points"][0]
            assert p[1] >= 1
