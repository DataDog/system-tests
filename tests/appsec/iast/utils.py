import json
from utils import weblog, interfaces, context, logger, irrelevant
from utils._weblog import HttpResponse


def _get_expectation(d: str | dict | None) -> str | None:
    if d is None or isinstance(d, str):
        return d

    if isinstance(d, dict):
        expected = d.get(context.library.name)
        if isinstance(expected, dict):
            expected = expected.get(context.weblog_variant)
        return expected

    raise TypeError(f"Unsupported expectation type: {d}")


def _get_span_meta(request: HttpResponse):
    span = interfaces.library.get_root_span(request)
    meta = span.get("meta", {})
    meta_struct = span.get("meta_struct", {})
    return meta, meta_struct


def get_iast_event(request: HttpResponse) -> dict | list | None:
    meta, meta_struct = _get_span_meta(request=request)
    assert "_dd.iast.json" in meta or "iast" in meta_struct, "No IAST info found tag in span"
    return meta.get("_dd.iast.json") or meta_struct.get("iast")


def assert_iast_vulnerability(
    request: HttpResponse,
    vulnerability_count: int | None = None,
    vulnerability_type: str | None = None,
    expected_location: str | None = None,
    expected_evidence: str | None = None,
) -> None:
    iast = get_iast_event(request=request)
    assert isinstance(iast, dict)
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


def assert_metric(request: HttpResponse, metric: str, *, expected: bool) -> None:
    spans_checked = 0
    metric_available = False
    for _, __, span in interfaces.library.get_spans(request):
        if metric in span["metrics"]:
            metric_available = True
        spans_checked += 1
    assert spans_checked == 1
    assert metric_available == expected


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


def get_all_iast_events() -> list:
    spans = [span[2] for span in interfaces.library.get_spans()]
    assert spans, "No spans found"
    spans_meta = [span.get("meta") for span in spans if span.get("meta")]
    spans_meta_struct = [span.get("meta_struct") for span in spans if span.get("meta_struct")]
    assert spans_meta or spans_meta_struct, "No spans meta found"
    iast_events = [meta.get("_dd.iast.json") for meta in spans_meta if meta.get("_dd.iast.json")]
    iast_events += [metastruct.get("iast") for metastruct in spans_meta_struct if metastruct.get("iast")]
    assert iast_events, "No iast events found"

    return iast_events


def get_iast_sources(iast_events: list) -> list:
    sources: list = []

    for event in iast_events:
        sources.extend(event.get("sources", []))

    assert sources, "No sources found"

    return sources


class BaseSinkTestWithoutTelemetry:
    vulnerability_type: str | None = None
    http_method: str
    insecure_endpoint: str | None = None
    secure_endpoint: str | None = None
    params: dict | None = None
    data: dict | None = None
    headers: dict | None = None
    secure_headers: dict | None = None
    insecure_headers: dict | None = None
    location_map: str | dict | None = None
    evidence_map: str | dict | None = None

    insecure_request: HttpResponse
    secure_request: HttpResponse

    @property
    def expected_location(self) -> str | None:
        return _get_expectation(self.location_map)

    @property
    def expected_evidence(self) -> str | None:
        return _get_expectation(self.evidence_map)

    def setup_insecure(self) -> None:
        # optimize by attaching requests to the class object, to avoid calling it several times. We can't attach them
        # to self, and we need to attach the request on class object, as there are one class instance by test case

        if not hasattr(self.__class__, "insecure_request"):
            assert self.insecure_endpoint is not None, f"{self}.insecure_endpoint must not be None"

            self.__class__.insecure_request = weblog.request(
                method=self.http_method,
                path=self.insecure_endpoint,
                params=self.params,
                data=self.data,
                headers=self.insecure_headers if self.insecure_headers is not None else self.headers,
            )

        self.insecure_request = self.__class__.insecure_request

    def test_insecure(self) -> None:
        assert_iast_vulnerability(
            request=self.insecure_request,
            vulnerability_type=self.vulnerability_type,
            expected_location=self.expected_location,
            expected_evidence=self.expected_evidence,
        )

    def check_test_insecure(self) -> None:
        # to avoid false positive, we need to check that iast is implemented
        # AND that the insecure endpoint is vulnerable

        interfaces.library.assert_iast_implemented()
        self.test_insecure()

    def setup_secure(self) -> None:
        # optimize by attaching requests to the class object, to avoid calling it several times. We can't attach them
        # to self, and we need to attach the request on class object, as there are one class instance by test case

        if not hasattr(self.__class__, "secure_request"):
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

    def test_secure(self) -> None:
        # to avoid false positive, we need to check first that the insecure endpoint is vulnerable
        self.check_test_insecure()

        self.assert_no_iast_event(self.secure_request, self.vulnerability_type)

    @staticmethod
    def assert_no_iast_event(request: HttpResponse, tested_vulnerability_type: str | None = None) -> None:
        assert request.status_code == 200, f"Request failed with status code {request.status_code}"

        meta, meta_struct = _get_span_meta(request=request)
        iast_json = (meta or {}).get("_dd.iast.json", (meta_struct or {}).get("iast"))
        if iast_json is not None:
            if tested_vulnerability_type is None:
                logger.error(json.dumps(iast_json, indent=2))
                raise ValueError("Unexpected vulnerability reported")
            elif iast_json["vulnerabilities"]:
                for vuln in iast_json["vulnerabilities"]:
                    if vuln["type"] == tested_vulnerability_type:
                        logger.error(json.dumps(iast_json, indent=2))
                        raise ValueError(f"Unexpected vulnerability reported: {vuln['type']}")


def validate_stack_traces(request: HttpResponse) -> None:
    span = interfaces.library.get_root_span(request)
    meta = span.get("meta", {})
    meta_struct = span.get("meta_struct", {})
    iast = meta.get("_dd.iast.json") or meta_struct.get("iast")
    assert iast is not None, "No iast event in root span"
    assert iast["vulnerabilities"], "Expected at least one vulnerability"

    assert "meta_struct" in span, "'meta_struct' not found in span"
    assert (
        "_dd.stack" in span["meta_struct"]
    ), "'_dd.stack' not found in 'meta_struct'. Please check if the test should be marked as irrelevant (not expected to have a stack trace)"
    stack_traces = span["meta_struct"]["_dd.stack"]["vulnerability"]
    stack_trace = stack_traces[0]
    vulns = [
        i for i in iast["vulnerabilities"] if i.get("location") and i["location"].get("stackId") == stack_trace["id"]
    ]
    assert (
        len(vulns) >= 1
    ), f"Expected at least one vulnerability per stack trace Id.\nVulnerabilities: {vulns}\nStack trace: {stack_traces}"
    vuln = vulns[0]

    assert vuln["location"], "no 'location' present'"
    assert vuln["location"]["stackId"], "no 'stack_id's present'"
    assert isinstance(vuln["location"]["stackId"], str), "'stackId' is not a string"
    assert "meta_struct" in span, "'meta_struct' not found in span"
    assert "_dd.stack" in span["meta_struct"], "'_dd.stack' not found in 'meta_struct'"
    assert "vulnerability" in span["meta_struct"]["_dd.stack"], "'vulnerability' not found in '_dd.stack'"

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

    # Ensure the stack ID corresponds to an iast event
    assert "id" in stack_trace, "'id' not found in stack trace"
    assert "frames" in stack_trace, "'frames' not found in stack trace"
    assert len(stack_trace["frames"]) <= 32, "stack trace above size limit (32 frames)"

    # Vulns without location are not expected to have a stack trace
    location = vuln["location"]
    assert location is not None, "This vulnerability is not expected to have a stack trace"

    location_frame = None
    for frame in stack_trace["frames"]:
        # We are looking for the frame that corresponds to the location of the vulnerability, we will need to update this to cover all tracers
        # currently support: Java, Python, Node.js
        if (
            (
                stack_trace["language"] == "java"
                and (
                    location["path"] in frame["class_name"]
                    and location["method"] in frame["function"]
                    and location["line"] == frame["line"]
                )
            )
            or (
                stack_trace["language"] == "nodejs"
                and (frame.get("file", "").endswith(location["path"]) and location["line"] == frame["line"])
            )
            or (
                stack_trace["language"] == "dotnet"
                # we are not able to ensure that other fields are available in location
                and (location["method"] in frame["function"])
            )
            or (
                stack_trace["language"] == "python"
                and (
                    frame.get("file", "").endswith(location["path"])
                    and location["line"] == frame["line"]
                    and ("method" in location and location["method"] == frame["function"])
                    # classes are not in Python stack traces and don't need to match the file so we
                    # can't check them in Python vs the frame (and some previous versions doesn't have them)
                    # and "class_name" in location
                )
            )
        ):
            location_frame = frame
    assert location_frame is not None, "location not found in stack trace"


def validate_extended_location_data(
    request: HttpResponse, vulnerability_type: str | None, *, is_expected_location_required: bool = True
) -> None:
    span = interfaces.library.get_root_span(request)
    iast = span.get("meta", {}).get("_dd.iast.json") or span.get("meta_struct", {}).get("iast")
    assert iast, f"Expected at least one vulnerability in span {span.get('span_id')}"
    assert iast["vulnerabilities"], f"Expected at least one vulnerability: {iast['vulnerabilities']}"

    # Filter by vulnerability
    if vulnerability_type:
        vulns = [v for v in iast["vulnerabilities"] if not vulnerability_type or v["type"] == vulnerability_type]
        assert vulns, f"No vulnerability of type {vulnerability_type}"

    if not is_expected_location_required:
        return

    logger.debug(f"Vulnerabilities: {json.dumps(vulns, indent=2)}")
    assert len(vulns) == 1, "Expected a single vulnerability with the matching criteria"

    vuln = vulns[0]
    location = vuln["location"]

    stack_id = location.get("stackId")
    # XXX: Backwards compatibility trick for tracers that got `stackId` outside location.
    # The correct stackId location is tested else wher e.g. schema tests.
    if not stack_id:
        stack_id = vuln.get("stackId")

    if not stack_id:
        # If there is no stacktrace, just check for the presence of basic attributes.
        assert all(field in location for field in ["path", "line"])

        if context.library.name not in ("python", "nodejs"):
            assert all(field in location for field in ["class", "method"])
    else:
        assert "vulnerability" in span["meta_struct"]["_dd.stack"], "'vulnerability' not found in '_dd.stack'"
        stack_traces = span["meta_struct"]["_dd.stack"]["vulnerability"]
        assert stack_traces, "No vulnerability stack traces found"
        stack_traces = [s for s in stack_traces if s.get("id") == stack_id]
        assert stack_traces, f"No vulnerability stack trace found for id {stack_id}"
        stack_trace = stack_traces[0]

        assert "language" in stack_trace
        assert stack_trace["language"] in (
            "php",
            "python",
            "nodejs",
            "java",
            "dotnet",
            "go",
            "ruby",
        ), "unexpected language"
        assert "frames" in stack_trace

        # Verify frame matches location
        def _norm(s: str | None) -> str | None:
            return s if s else None

        location_match = False
        for frame in stack_trace["frames"]:
            logger.debug(frame)
            if not frame.get("file", "").endswith(location["path"]):
                logger.debug("path does not match")
            elif frame["line"] != location["line"]:
                logger.debug("line does not match")
            elif _norm(location.get("class")) != _norm(frame.get("class_name")):
                logger.debug("class does not match")
            elif _norm(location.get("method")) != _norm(frame.get("function")):
                logger.debug("method does not match")
            else:
                logger.debug("location match")
                location_match = True
                break

        assert location_match, f"location not found in stack trace, location={location}, stack_trace={stack_trace}"


def get_hardcoded_vulnerabilities(vulnerability_type: str) -> list:
    spans = [s for _, s in interfaces.library.get_root_spans()]
    assert spans, "No spans found"
    spans_meta = [span.get("meta") for span in spans]
    assert spans_meta, "No spans meta found"
    iast_events = [meta.get("_dd.iast.json") for meta in spans_meta if meta.get("_dd.iast.json")]
    assert iast_events, "No iast events found"

    vulnerabilities: list = []
    for event in iast_events:
        vulnerabilities.extend(event.get("vulnerabilities", []))

    assert vulnerabilities, "No vulnerabilities found"

    hardcoded_vulns = [vuln for vuln in vulnerabilities if vuln.get("type") == vulnerability_type]
    assert hardcoded_vulns, "No hardcoded vulnerabilities found"
    return hardcoded_vulns


class BaseSinkTest(BaseSinkTestWithoutTelemetry):
    def setup_telemetry_metric_instrumented_sink(self) -> None:
        self.setup_insecure()

    def test_telemetry_metric_instrumented_sink(self) -> None:
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

    def setup_telemetry_metric_executed_sink(self) -> None:
        self.setup_insecure()

    def test_telemetry_metric_executed_sink(self) -> None:
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
    endpoint: str
    requests_kwargs: list[dict] | None = None
    source_type: str | None = None
    source_names: list[str] | None = None
    source_value: str | None = None
    requests: dict[str, HttpResponse]
    store: dict[str, HttpResponse] | None = None

    def setup_source_reported(self) -> None:
        assert isinstance(self.requests_kwargs, list), f"{self.__class__}.requests_kwargs must be a list of dicts"

        # optimize by attaching requests to the class object, to avoid calling it several times. We can't attach them
        # to self, and we need to attach the request on class object, as there are one class instance by test case

        if self.__class__.store is None:
            self.__class__.store = {}
            for kwargs in self.requests_kwargs:
                method = kwargs["method"]
                # store them as method:request to allow later custom test by method
                self.__class__.store[method] = weblog.request(path=self.endpoint, **kwargs)

        self.requests = self.__class__.store

    def test_source_reported(self) -> None:
        for request in self.requests.values():
            self.validate_request_reported(request)

    def check_test_telemetry_should_execute(self) -> None:
        interfaces.library.assert_iast_implemented()

        # to avoid false positive, we need to check that at least
        # one test is working before running the telemetry tests

        error: Exception = Exception("No test executed")
        for method in dir(self):
            if (
                callable(getattr(self, method))
                and not method.startswith("test_telemetry_metric_")
                and method.startswith("test_")
            ):
                try:
                    getattr(self, method)()
                    return
                except Exception as e:
                    error = e

        raise error

    def get_sources(self, request: HttpResponse) -> list:
        iast = get_iast_event(request=request)
        assert isinstance(iast, dict)
        return iast["sources"]

    def validate_request_reported(self, request: HttpResponse, source_type: str | None = None) -> None:
        if source_type is None:  # allow to overwrite source_type for parameter value node's use case
            source_type = self.source_type

        sources = self.get_sources(request)
        assert sources, "No source reported"
        if source_type:
            assert source_type in {s.get("origin") for s in sources}
            sources = [s for s in sources if s["origin"] == source_type]
        if self.source_names:
            assert isinstance(self.source_names, list)
            assert any(
                x in self.source_names for x in {s.get("name") for s in sources}
            ), f"Source {self.source_names} not in {sources}"
            sources = [s for s in sources if s["name"] in self.source_names]
        if self.source_value:
            assert self.source_value in {s.get("value") for s in sources}
            sources = [s for s in sources if s["value"] == self.source_value]
        assert (
            sources
        ), f"No source found with origin={source_type}, name={self.source_names}, value={self.source_value}"
        assert len(sources) == 1, "Expected a single source with the matching criteria"

    setup_telemetry_metric_instrumented_source = setup_source_reported

    def test_telemetry_metric_instrumented_source(self) -> None:
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

    def test_telemetry_metric_executed_source(self) -> None:
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
    vulnerability_type: str | None = None
    endpoint: str

    def setup_cookie_name_filter(self) -> None:
        prefix = "0" * 36
        cookie_name_1 = prefix + "name1"
        cookie_name_2 = "name2"
        cookie_name_3 = prefix + "name3"
        self.req1 = weblog.post(self.endpoint, data={"cookieName": cookie_name_1, "cookieValue": "value1"})
        self.req2 = weblog.post(self.endpoint, data={"cookieName": cookie_name_2, "cookieValue": "value2"})
        self.req3 = weblog.post(self.endpoint, data={"cookieName": cookie_name_3, "cookieValue": "value3"})

    @irrelevant(
        context.library >= "nodejs@5.50.0",
        reason="cookie name filtering is not present anymore after the change on cookie vuln hash calculation.",
    )
    def test_cookie_name_filter(self) -> None:
        assert_iast_vulnerability(
            request=self.req1,
            vulnerability_count=1,
            vulnerability_type=self.vulnerability_type,
        )
        assert_iast_vulnerability(
            request=self.req2,
            vulnerability_count=1,
            vulnerability_type=self.vulnerability_type,
        )

        meta, meta_struct = _get_span_meta(self.req3)
        assert "_dd.iast.json" not in meta, "No IAST info expected in span"
        assert "iast" not in meta_struct, "No IAST info expected in span"


def get_nodejs_iast_file_paths() -> dict[str, str]:
    return {
        "express4": "iast/index.js",
        "express4-typescript": "iast.ts",
        "express5": "iast/index.js",
        "fastify": "iast/index.js",
        "uds-express4": "iast/index.js",
    }
