from utils import interfaces, rfc, weblog, scenarios, context, bug, missing_feature, flaky, features
from utils.tools import logger

TELEMETRY_REQUEST_TYPE_GENERATE_METRICS = "generate-metrics"
TELEMETRY_REQUEST_TYPE_DISTRIBUTIONS = "distributions"


def _setup(self):
    """
    Common setup for all tests in this module. They all depend on the same set
    of requests, which must be run only once.
    """
    # Run only once, even across multiple class instances.
    if hasattr(Test_TelemetryMetrics, "__common_setup_done"):
        return
    r_plain = weblog.get("/", headers={"x-forwarded-for": "80.80.80.80"})
    r_triggered = weblog.get("/", headers={"x-forwarded-for": "80.80.80.80", "user-agent": "Arachni/v1"})
    r_blocked = weblog.get(
        "/",
        headers={"x-forwarded-for": "80.80.80.80", "user-agent": "dd-test-scanner-log-block"},
        # XXX: hack to prevent rid inhibiting the dd-test-scanner-log-block rule
        rid_in_user_agent=False,
    )
    Test_TelemetryMetrics.__common_setup_done = True


@features.waf_telemetry
class Test_TelemetryResponses:
    """ Test response from backend/agent """

    setup_all_telemetry_requests_are_successful = _setup

    @flaky(True, reason="Backend is far away from being stable enough")
    def test_all_telemetry_requests_are_successful(self):
        """Tests that all telemetry requests succeed."""
        for data in interfaces.library.get_telemetry_data():
            assert data["response"]["status_code"] == 202


@rfc("https://docs.google.com/document/d/1qBDsS_ZKeov226CPx2DneolxaARd66hUJJ5Lh9wjhlE")
@scenarios.appsec_waf_telemetry
@features.waf_telemetry
class Test_TelemetryMetrics:
    """Test instrumentation telemetry metrics, type of metrics generate-metrics"""

    setup_headers_are_correct = _setup

    @bug(context.library < "java@1.13.0", reason="Missing two headers")
    def test_headers_are_correct(self):
        """Tests that all telemetry requests have correct headers."""
        for data in interfaces.library.get_telemetry_data(flatten_message_batches=False):
            request_type = data["request"]["content"].get("request_type")
            _validate_headers(data["request"]["headers"], request_type)

    setup_metric_waf_init = _setup

    @flaky(context.weblog_variant == "django-poc", reason="APPSEC-10509")
    def test_metric_waf_init(self):
        """Test waf.init metric."""
        expected_metric_name = "waf.init"
        mandatory_tag_prefixes = {
            "waf_version",
            "event_rules_version",
        }
        valid_tag_prefixes = {
            "waf_version",
            "event_rules_version",
            "version",
            "lib_language",
        }
        series = self._find_series(TELEMETRY_REQUEST_TYPE_GENERATE_METRICS, "appsec", expected_metric_name)
        # TODO(Python). Gunicorn creates 2 process (main gunicorn process + X child workers). It generates two init
        if context.library == "python" and context.weblog_variant not in ("fastapi", "uwsgi-poc"):
            assert len(series) == 2
        else:
            assert len(series) == 1
        s = series[0]
        assert s["_computed_namespace"] == "appsec"
        assert s["metric"] == expected_metric_name
        assert s["common"] is True
        assert s["type"] == "count"

        full_tags = set(s["tags"])
        self._assert_valid_tags(
            full_tags=full_tags, valid_prefixes=valid_tag_prefixes, mandatory_prefixes=mandatory_tag_prefixes
        )

        assert len(s["points"]) == 1
        p = s["points"][0]
        assert p[1] == 1

    setup_metric_waf_updates = _setup

    @missing_feature(reason="Test not implemented")
    @bug(context.library < "java@1.13.0", reason="Missing tags")
    def test_metric_waf_updates(self):
        """Test waf.updates metric."""
        expected_metric_name = "waf.updates"
        mandatory_tag_prefixes = {
            "waf_version",
            "event_rules_version",
        }
        valid_tag_prefixes = {
            "waf_version",
            "event_rules_version",
            "version",
            "lib_language",
        }
        series = self._find_series(TELEMETRY_REQUEST_TYPE_GENERATE_METRICS, "appsec", expected_metric_name)
        assert len(series) == 1
        s = series[0]
        assert s["_computed_namespace"] == "appsec"
        assert s["metric"] == expected_metric_name
        assert s["common"] is True
        assert s["type"] == "count"

        full_tags = set(s["tags"])
        self._assert_valid_tags(
            full_tags=full_tags, valid_prefixes=valid_tag_prefixes, mandatory_prefixes=mandatory_tag_prefixes
        )

        assert len(s["points"]) == 1
        p = s["points"][0]
        assert p[1] == 1

    setup_metric_waf_requests = _setup

    @bug(context.library < "java@1.13.0", reason="Missing tags")
    def test_metric_waf_requests(self):
        """Test waf.requests metric."""
        expected_metric_name = "waf.requests"
        valid_tag_prefixes = {
            "waf_version",
            "event_rules_version",
            "rule_triggered",
            "request_blocked",
            "request_excluded",
            "waf_timeout",
            "version",
            "lib_language",
        }
        mandatory_tag_prefixes = {
            "waf_version",
            "event_rules_version",
            "rule_triggered",
            "request_blocked",
        }
        series = self._find_series(TELEMETRY_REQUEST_TYPE_GENERATE_METRICS, "appsec", expected_metric_name)
        logger.debug(series)
        # Depending on the timing, there might be more than 3 series. For example, if a warmup
        # request goes first, we might have two series for rule_triggered:false,blocked_request:false
        assert len(series) >= 3

        matched_not_blocked = 0
        matched_triggered = 0
        matched_blocked = 0
        for s in series:
            assert s["_computed_namespace"] == "appsec"
            assert s["metric"] == expected_metric_name
            assert s["common"] is True
            assert s["type"] == "count"
            assert len(s["points"]) == 1
            p = s["points"][0]

            full_tags = set(s["tags"])
            self._assert_valid_tags(
                full_tags=full_tags, valid_prefixes=valid_tag_prefixes, mandatory_prefixes=mandatory_tag_prefixes
            )

            if len(full_tags & {"request_blocked:false", "rule_triggered:false"}) == 2:
                matched_not_blocked += 1
                assert p[1] >= 1
            elif len(full_tags & {"request_blocked:false", "rule_triggered:true"}) == 2:
                matched_triggered += 1
                assert p[1] == 1
            elif len(full_tags & {"request_blocked:true", "rule_triggered:true"}) == 2:
                matched_blocked += 1
                assert p[1] == 1
            else:
                raise ValueError(f"Unexpected tags: {full_tags}")

        # XXX: Warm up requests might generate more than one series.
        assert matched_not_blocked >= 1
        assert matched_triggered == 1
        assert matched_blocked == 1

    setup_waf_requests_match_traced_requests = _setup

    @bug(context.library < "java@1.29.0", reason="APPSEC-51509")
    def test_waf_requests_match_traced_requests(self):
        """Total waf.requests metric should match the number of requests in traces."""
        spans = [s for _, s in interfaces.library.get_root_spans()]
        spans = [
            s
            for s in spans
            if s.get("meta", {}).get("span.kind") == "server"
            # excluding graphql introspection query executed on startup in nodejs
            and s.get("meta", {}).get("graphql.operation.name") != "IntrospectionQuery"
        ]
        request_count = len(spans)
        assert request_count >= 3

        expected_metric_name = "waf.requests"
        total_requests_metric = 0
        for series in self._find_series(TELEMETRY_REQUEST_TYPE_GENERATE_METRICS, "appsec", expected_metric_name):
            for point in series["points"]:
                total_requests_metric += point[1]
        assert (
            total_requests_metric == request_count
        ), "Number of requests in traces do not match waf.requests metric total"

    def _find_series(self, request_type, namespace, metric):
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

    def _assert_valid_tags(self, full_tags, valid_prefixes, mandatory_prefixes):
        full_tags = set(full_tags)
        tag_prefixes = {t.split(":")[0] for t in full_tags}

        invalid_tags = tag_prefixes - valid_prefixes
        assert not invalid_tags

        missing_tags = mandatory_prefixes - tag_prefixes
        assert not missing_tags


def _validate_headers(headers, request_type):
    """https://github.com/DataDog/instrumentation-telemetry-api-docs/blob/main/GeneratedDocumentation/ApiDocs/v2/how-to-use.md"""

    expected_language = context.library.library
    if expected_language == "java":
        expected_language = "jvm"

    # empty value means we don't care about the content, but we want to check the key exists
    # a set means "any of"
    expected_headers = {
        "Content-Type": {"application/json", "application/json; charset=utf-8"},
        "DD-Telemetry-Request-Type": request_type,
        "DD-Client-Library-Language": expected_language,
        "DD-Client-Library-Version": "",
    }

    if context.library == "python":
        # APM Python migrates Telemetry to V2
        expected_headers["DD-Telemetry-API-Version"] = "v2"
    elif context.library > "nodejs@4.20.0":
        # APM Node.js migrates Telemetry to V2
        expected_headers["DD-Telemetry-API-Version"] = "v2"
    elif context.library >= "java@1.23.0":
        expected_headers["DD-Telemetry-API-Version"] = "v2"
    else:
        expected_headers["DD-Telemetry-API-Version"] = "v1"

    expected_headers = {k.lower(): v for k, v in expected_headers.items()}

    seen_headers = set()
    for key, value in headers:
        lower_key = key.lower()
        expected_value = expected_headers.get(lower_key)
        if expected_value is None:
            # Irrelevant header
            continue
        assert lower_key not in seen_headers, f"Duplicated header {lower_key}"
        seen_headers.add(lower_key)
        if isinstance(expected_value, set):
            assert value in expected_value
        elif expected_value != "":
            assert value == expected_value
        else:
            assert value, f"Empty {key} header"

    missing_headers = set(expected_headers.keys()) - seen_headers
    assert not missing_headers, f"Missing required headers: {missing_headers}"
