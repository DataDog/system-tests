import json
from utils import weblog, interfaces, context
from utils.tools import logger


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
    request, vulnerability_count=None, vulnerability_type=None, expected_location=None, expected_evidence=None
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
    if vulnerability_count is not None:
        assert len(vulns) == vulnerability_count


def _check_telemetry_response_from_agent():
    # Java tracer (at least) disable telemetry if agent answer 403
    # Checking that agent answers 200
    # we do not fail the test, because we are not sure it's the official behavior
    for data in interfaces.library.get_telemetry_data():
        code = data["response"]["status_code"]
        if code != 200:
            filename = data["log_filename"]
            logger.warning(f"Agent answered {code} on {filename}, it may cause telemetry issues")
            return


def get_all_iast_events():
    spans = [span[2] for span in interfaces.library.get_spans()]
    assert spans, "No spans found"
    spans_meta = [span.get("meta") for span in spans]
    assert spans_meta, "No spans meta found"
    iast_events = [meta.get("_dd.iast.json") for meta in spans_meta if meta.get("_dd.iast.json")]
    assert iast_events, "No iast events found"

    return iast_events


def get_iast_sources(iast_events):
    sources = [event.get("sources") for event in iast_events if event.get("sources")]
    assert sources, "No sources found"
    sources = sum(sources, [])  # set all the sources in a single list
    return sources


class BaseSinkTestWithoutTelemetry:
    vulnerability_type = None
    http_method = None
    insecure_endpoint = None
    secure_endpoint = None
    params = None
    data = None
    headers = None
    secure_headers = None
    insecure_headers = None
    location_map = None
    evidence_map = None

    insecure_request = None
    secure_request = None

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
                headers=self.insecure_headers if self.insecure_headers is not None else self.headers,
            )

        self.insecure_request = self.__class__.insecure_request

    def test_insecure(self):
        assert_iast_vulnerability(
            request=self.insecure_request,
            vulnerability_type=self.vulnerability_type,
            expected_location=self.expected_location,
            expected_evidence=self.expected_evidence,
        )

    def check_test_insecure(self):
        # to avoid false positive, we need to check that iast is implemented
        # AND that the insecure endpoint is vulnerable

        interfaces.library.assert_iast_implemented()
        self.test_insecure()

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
                headers=self.secure_headers if self.secure_headers is not None else self.headers,
            )

        self.secure_request = self.__class__.secure_request

    def test_secure(self):
        # to avoid false positive, we need to check first that the insecure endpoint is vulnerable
        self.check_test_insecure()

        self.assert_no_iast_event(self.secure_request, self.vulnerability_type)

    @staticmethod
    def assert_no_iast_event(request, tested_vulnerability_type=None):
        assert request.status_code == 200, f"Request failed with status code {request.status_code}"

        for data, _, span in interfaces.library.get_spans(request=request):
            logger.info(f"Looking for IAST events in {data['log_filename']}")
            meta = span.get("meta", {})
            iast_json = meta.get("_dd.iast.json")
            if iast_json is not None:
                if tested_vulnerability_type is None:
                    logger.error(json.dumps(iast_json, indent=2))
                    raise ValueError("Unexpected vulnerability reported")
                elif iast_json["vulnerabilities"]:
                    for vuln in iast_json["vulnerabilities"]:
                        if vuln["type"] == tested_vulnerability_type:
                            logger.error(json.dumps(iast_json, indent=2))
                            raise ValueError(f"Unexpected vulnerability reported: {vuln['type']}")


def validate_stack_traces(request):

    spans = [span for _, span in interfaces.library.get_root_spans(request=request)]
    assert spans, "No root span found"
    span = spans[0]
    meta = span.get("meta", {})
    assert "_dd.iast.json" in meta, "No iast event in root span"
    iast = meta["_dd.iast.json"]
    assert iast["vulnerabilities"], "Expected at least one vulnerability"

    # To simplify as we are relaying in insecure_request that is expected to have one vulnerability
    vuln = iast["vulnerabilities"][0]

    assert vuln["stackId"], "no 'stack_id's present'"
    assert "meta_struct" in span, "'meta_struct' not found in span"
    assert "_dd.stack" in span["meta_struct"], "'_dd.stack' not found in 'meta_struct'"
    assert "vulnerability" in span["meta_struct"]["_dd.stack"], "'exploit' not found in '_dd.stack'"

    stack_trace = span["meta_struct"]["_dd.stack"]["vulnerability"][0]
    assert stack_trace, "No stack traces to validate"

    assert "language" in stack_trace, "'language' not found in stack trace"
    assert stack_trace["language"] in (
        "php",
        "python",
        "nodejs",
        "java",
        "dotnet",
        "go",
        "ruby",
    ), "unexpected language"

    # Ensure the stack ID corresponds to an appsec event
    assert "id" in stack_trace, "'id' not found in stack trace"
    assert stack_trace["id"] == vuln["stackId"], "'id' doesn't correspond to an appsec event"

    assert "frames" in stack_trace, "'frames' not found in stack trace"
    assert len(stack_trace["frames"]) <= 32, "stack trace above size limit (32 frames)"

    # Vulns without location path are not expected to have a stack trace
    location = vuln["location"]
    assert location is not None and "path" in location, "This vulnerability is not expected to have a stack trace"

    locationFrame = None
    for frame in stack_trace["frames"]:
        # We are looking for the frame that corresponds to the location of the vulnerability, we will need to update this to cover all tracers
        if (
            location["path"] in frame["class_name"]
            and location["method"] in frame["function"]
            and location["line"] == frame["line"]
        ):
            locationFrame = frame
    assert locationFrame is not None, "location not found in stack trace"


class BaseSinkTest(BaseSinkTestWithoutTelemetry):
    def setup_telemetry_metric_instrumented_sink(self):
        self.setup_insecure()

    def test_telemetry_metric_instrumented_sink(self):
        self.check_test_insecure()

        _check_telemetry_response_from_agent()

        expected_namespace = "iast"
        expected_metric = "instrumented.sink"
        series = interfaces.library.get_telemetry_metric_series(expected_namespace, expected_metric)
        assert series, f"Got no series for metric {expected_metric}"
        logger.debug("Series: %s", series)

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
        self.check_test_insecure()

        _check_telemetry_response_from_agent()

        expected_namespace = "iast"
        expected_metric = "executed.sink"
        series = interfaces.library.get_telemetry_metric_series(expected_namespace, expected_metric)
        assert series, f"Got no series for metric {expected_metric}"
        logger.debug("Series: %s", series)

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

    def check_test_telemetry_should_execute(self):
        interfaces.library.assert_iast_implemented()

        # to avoid false positive, we need to check that at least
        # one test is working before running the telemetry tests

        at_least_one_success = False
        error = None
        for method in dir(self):
            if (
                callable(getattr(self, method))
                and not method.startswith("test_telemetry_metric_")
                and method.startswith("test_")
            ):
                try:
                    getattr(self, method)()
                    at_least_one_success = True
                except Exception as e:
                    error = e
        if not at_least_one_success:
            raise error

    def get_sources(self, request):
        iast = get_iast_event(request=request)
        sources = iast["sources"]
        return sources

    def validate_request_reported(self, request, source_type=None):
        if source_type is None:  # allow to overwrite source_type for parameter value node's use case
            source_type = self.source_type

        sources = self.get_sources(request)
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
        self.check_test_telemetry_should_execute()

        _check_telemetry_response_from_agent()

        expected_namespace = "iast"
        expected_metric = "instrumented.source"
        series = interfaces.library.get_telemetry_metric_series(expected_namespace, expected_metric)
        assert series, f"Got no series for metric {expected_metric}"
        logger.debug(f"Series: {json.dumps(series, indent=2)}")

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
        self.check_test_telemetry_should_execute()

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

        logger.debug(f"Series:\n{json.dumps(series, indent=2)}")

        for s in series:
            assert s["_computed_namespace"] == expected_namespace
            assert s["metric"] == expected_metric
            assert s["common"] is True
            assert s["type"] == "count"
            assert len(s["points"]) == 1
            p = s["points"][0]
            assert p[1] >= 1


class BaseTestCookieNameFilter:
    vulnerability_type = None
    endpoint = None

    def setup_cookie_name_filter(self):
        prefix = "0" * 36
        cookieName1 = prefix + "name1"
        cookieName2 = "name2"
        cookieName3 = prefix + "name3"
        self.req1 = weblog.post(self.endpoint, data={"cookieName": cookieName1, "cookieValue": "value1"})
        self.req2 = weblog.post(self.endpoint, data={"cookieName": cookieName2, "cookieValue": "value2"})
        self.req3 = weblog.post(self.endpoint, data={"cookieName": cookieName3, "cookieValue": "value3"})

    def test_cookie_name_filter(self):
        assert_iast_vulnerability(request=self.req1, vulnerability_count=1, vulnerability_type=self.vulnerability_type)
        assert_iast_vulnerability(request=self.req2, vulnerability_count=1, vulnerability_type=self.vulnerability_type)

        meta_req3 = _get_span_meta(self.req3)
        assert "_dd.iast.json" not in meta_req3
