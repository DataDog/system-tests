from collections import defaultdict
from datetime import datetime, timedelta
import time
from utils import context, interfaces, missing_feature, bug, flaky, irrelevant, weblog, scenarios, features
from utils.tools import logger
from utils.interfaces._misc_validators import HeadersPresenceValidator, HeadersMatchValidator

INTAKE_TELEMETRY_PATH = "/api/v2/apmtelemetry"
AGENT_TELEMETRY_PATH = "/telemetry/proxy/api/v2/apmtelemetry"


def get_header(data, origin, name):
    for h in data[origin]["headers"]:
        if h[0].lower() == name:
            return h[1]
    return None


def get_request_type(data):
    return data["request"]["content"].get("request_type")


def not_onboarding_event(data):
    return get_request_type(data) != "apm-onboarding-event"


def is_v2_payload(data):
    return data["request"]["content"].get("api_version") == "v2"


def is_v1_payload(data):
    return data["request"]["content"].get("api_version") == "v1"


@features.telemetry_instrumentation
class Test_Telemetry:
    """Test that instrumentation telemetry is sent"""

    # containers for telemetry request to check consistency between library payloads and agent payloads
    library_requests = {}
    agent_requests = {}

    def validate_library_telemetry_data(self, validator, success_by_default=False):
        telemetry_data = list(interfaces.library.get_telemetry_data(flatten_message_batches=False))

        if len(telemetry_data) == 0 and not success_by_default:
            raise Exception("No telemetry data to validate on")

        for data in telemetry_data:
            validator(data)

    def validate_agent_telemetry_data(self, validator, success_by_default=False):
        telemetry_data = list(interfaces.agent.get_telemetry_data())

        if len(telemetry_data) == 0 and not success_by_default:
            raise Exception("No telemetry data to validate on")

        for data in telemetry_data:
            validator(data)

    def test_telemetry_message_data_size(self):
        """Test telemetry message data size"""

        def validator(data):
            if data["request"]["length"] >= 5_000_000:
                raise Exception(f"Received message size is more than 5MB")

        self.validate_library_telemetry_data(validator)
        self.validate_agent_telemetry_data(validator)

    @flaky(True, reason="Backend is far away from being stable enough")
    def test_status_ok(self):
        """Test that telemetry requests are successful"""

        def validator(data):
            response_code = data["response"]["status_code"]
            assert 200 <= response_code < 300, f"Got response code {response_code} in {data['log_filename']}"

        self.validate_agent_telemetry_data(validator)
        self.validate_library_telemetry_data(validator)

    @bug(
        context.agent_version >= "7.36.0" and context.agent_version < "7.37.0",
        reason="Version reporting of trace agent is broken in 7.36.x release",
    )
    def test_telemetry_proxy_enrichment(self):
        """Test telemetry proxy adds necessary information"""

        header_presence_validator = HeadersPresenceValidator(
            request_headers=["dd-agent-hostname", "dd-agent-env"],
            response_headers=(),
            check_condition=not_onboarding_event,
        )
        header_match_validator = HeadersMatchValidator(
            request_headers={"via": r"trace-agent 7\..+"}, response_headers=(), check_condition=not_onboarding_event,
        )

        self.validate_agent_telemetry_data(header_presence_validator)
        self.validate_agent_telemetry_data(header_match_validator)

    @irrelevant(True, reason="cgroup in weblog is 0::/, so this test can't work")
    def test_telemetry_message_has_datadog_container_id(self):
        """Test telemetry messages contain datadog-container-id"""
        interfaces.agent.assert_headers_presence(
            path_filter=INTAKE_TELEMETRY_PATH, request_headers=["datadog-container-id"],
        )

    def test_telemetry_message_required_headers(self):
        """Test telemetry messages contain required headers"""

        interfaces.agent.assert_headers_presence(
            path_filter=INTAKE_TELEMETRY_PATH, request_headers=["dd-api-key"],
        )
        interfaces.library.assert_headers_presence(
            path_filter=AGENT_TELEMETRY_PATH,
            request_headers=["dd-telemetry-api-version", "dd-telemetry-request-type"],
            check_condition=not_onboarding_event,
        )

    @missing_feature(library="python")
    @flaky(library="ruby", reason="AIT-8418")
    @flaky(library="java", reason="AIT-9152")
    def test_seq_id(self):
        """Test that messages are sent sequentially"""

        MAX_OUT_OF_ORDER_LAG = 0.3  # s
        FMT = "%Y-%m-%dT%H:%M:%S.%f"

        telemetry_data = list(interfaces.library.get_telemetry_data(flatten_message_batches=False))
        if len(telemetry_data) == 0:
            raise ValueError("No telemetry data to validate on")

        runtime_ids = set((data["request"]["content"]["runtime_id"] for data in telemetry_data))
        for runtime_id in runtime_ids:
            logger.debug(f"Validating telemetry messages for runtime_id {runtime_id}")
            max_seq_id = 0
            received_max_time = None
            seq_ids = []

            for data in telemetry_data:
                if runtime_id != data["request"]["content"]["runtime_id"]:
                    continue
                seq_id = data["request"]["content"]["seq_id"]
                timestamp_start = data["request"]["timestamp_start"]
                curr_message_time = datetime.strptime(timestamp_start, FMT)
                logger.debug(f"Message at {timestamp_start.split('T')[1]} in {data['log_filename']}, seq_id: {seq_id}")

                if 200 <= data["response"]["status_code"] < 300:
                    seq_ids.append((seq_id, data["log_filename"]))
                else:
                    logger.info(f"Response is {data['response']['status_code']}, tracer should resend the message")

                if seq_id > max_seq_id:
                    max_seq_id = seq_id
                    received_max_time = curr_message_time
                else:
                    if received_max_time is not None and (curr_message_time - received_max_time) > timedelta(
                        seconds=MAX_OUT_OF_ORDER_LAG
                    ):
                        raise ValueError(
                            f"Received message with seq_id {seq_id} to far more than"
                            f"100ms after message with seq_id {max_seq_id}"
                        )

            # sort by seq_id, seq_ids is an array of (id, filename), so the key is the first element
            seq_ids.sort(key=lambda item: item[0])

            for i in range(len(seq_ids) - 1):
                diff = seq_ids[i + 1][0] - seq_ids[i][0]
                if diff == 0:
                    raise ValueError(
                        f"Detected 2 telemetry messages with same seq_id {seq_ids[i + 1][1]} and {seq_ids[i][1]}"
                    )

                if diff > 1:
                    logger.error(f"{seq_ids[i + 1][0]} {seq_ids[i][0]}")
                    raise ValueError(
                        f"Detected non consecutive seq_ids between {seq_ids[i + 1][1]} and {seq_ids[i][1]}"
                    )

    @missing_feature(context.library < "ruby@1.22.0", reason="app-started not sent")
    @flaky(context.library <= "python@1.20.2", reason="app-started is sent twice")
    @features.telemetry_app_started_event
    def test_app_started_sent_exactly_once(self):
        """Request type app-started is sent exactly once"""

        count_by_runtime_id = defaultdict(lambda: 0)

        for data in interfaces.library.get_telemetry_data():
            if get_request_type(data) == "app-started":
                logger.debug(
                    f"Found app-started in {data['log_filename']}. Response from agent: {data['response']['status_code']}"
                )
                runtime_id = data["request"]["content"]["runtime_id"]
                if data["response"]["status_code"] == 202:
                    count_by_runtime_id[runtime_id] += 1

        assert all((count == 1 for count in count_by_runtime_id.values()))

    @missing_feature(context.library < "ruby@1.22.0", reason="app-started not sent")
    @bug(library="python", reason="app-started not sent first")
    @features.telemetry_app_started_event
    def test_app_started_is_first_message(self):
        """Request type app-started is the first telemetry message or the first message in the first batch"""
        telemetry_data = list(interfaces.library.get_telemetry_data(flatten_message_batches=False))
        assert len(telemetry_data) > 0, "No telemetry messages"
        if telemetry_data[0]["request"]["content"].get("request_type") == "message-batch":
            first_message = telemetry_data[0]["request"]["content"]["payload"][0]
            assert (
                first_message.get("request_type") == "app-started"
            ), "app-started was not the first message in the first batch"
        else:
            for data in telemetry_data:
                req_content = data["request"]["content"]
                if req_content["request_type"] == "app-started":
                    seq_id = req_content["seq_id"]
                    assert seq_id == 1, f"app-started found but it was not the first message sent"
                    return

            raise Exception(f"app-started message not found")

    @bug(
        library="java",
        weblog_variant="spring-boot-openliberty",
        reason="https://datadoghq.atlassian.net/browse/APPSEC-6583",
    )
    @bug(
        library="java", weblog_variant="spring-boot-wildfly",
    )
    def test_proxy_forwarding(self):
        """Test that all telemetry requests sent by library are forwarded correctly by the agent"""

        def save_data(data, container):
            # payloads are identifed by their seq_id/runtime_id
            if not_onboarding_event(data):
                key = data["request"]["content"]["seq_id"], data["request"]["content"]["runtime_id"]
                container[key] = data

        self.validate_library_telemetry_data(
            lambda data: save_data(data, self.library_requests), success_by_default=False
        )
        self.validate_agent_telemetry_data(lambda data: save_data(data, self.agent_requests), success_by_default=False)

        # At the end, check that all data are consistent
        for key, agent_data in self.agent_requests.items():
            agent_message, agent_log_file = agent_data["request"]["content"], agent_data["log_filename"]

            if key not in self.library_requests:
                # once the library interface is validated, weblog is not stopped. But it can send other data, and
                # they won't be seen. The agent interface wait 5 second after, and can collect data. So if the
                # library sent some data during this 5s, the agent interface will see it, but not the library
                # interface. For now, simply do not consider this use case, waiting for a better solution.

                pass

                # logger.error(str({
                #     "library_requests": [{"seq_id": s, "runtime_id": r} for s, r in self.library_requests],
                #     "agent_requests": [{"seq_id": s, "runtime_id": r} for s, r in self.agent_requests],
                # }))

                # raise Exception(
                #     f"Agent proxy forwarded a message that was not sent by the library: {agent_log_file}",
                # )
            else:
                lib_data = self.library_requests.pop(key)
                lib_message, lib_log_file = lib_data["request"]["content"], lib_data["log_filename"]

                if agent_message != lib_message:
                    raise Exception(
                        f"Telemetry proxy message different in messages {lib_log_file} and {agent_log_file}:\n"
                        f"library sent {lib_message}\n"
                        f"agent sent {agent_message}"
                    )

        if len(self.library_requests) != 0:
            for s, r in self.library_requests.keys():
                logger.error(f"seq_id: {s}, runtime_id: {r}")

            raise Exception("The following telemetry messages were not forwarded by the agent")

    @irrelevant(library="java")
    @irrelevant(library="nodejs")
    @irrelevant(library="dotnet")
    @irrelevant(library="golang")
    @irrelevant(library="python")
    @missing_feature(context.library >= "ruby@1.22.0", reason="Telemetry V2 sends app-dependencies-loaded")
    @features.dd_telemetry_dependency_collection_enabled_supported
    def test_app_dependencies_loaded_not_sent(self):
        """app-dependencies-loaded request should not be sent"""
        # Request type app-dependencies-loaded is never sent from certain language tracers
        # In case this changes we need to adjust the backend, by adding the language to this list
        # https://github.com/DataDog/dd-go/blob/prod/domains/appsec/libs/vulnerability_management/model.go#L262
        # This change means we cannot deduplicate runtime with the same library dependencies in the backend since
        # we never have guarantees that we have all the dependencies at one point in time

        def validator(data):
            if get_request_type(data) == "app-dependencies-loaded":
                raise Exception("request_type app-dependencies-loaded should not be used by this tracer")

        self.validate_library_telemetry_data(validator)

    @flaky(context.library < "nodejs@4.13.1", reason="Heartbeats are sometimes sent too fast")
    @bug(context.library < "java@1.18.0", reason="Telemetry interval drifts")
    @missing_feature(context.library < "ruby@1.13.0", reason="DD_TELEMETRY_HEARTBEAT_INTERVAL not supported")
    @flaky(library="ruby")
    @bug(context.library >= "nodejs@4.21.0", reason="AIT-9176")
    @bug(context.library > "php@0.90")
    @flaky(context.library <= "php@0.90", reason="Heartbeats are sometimes sent too slow")
    @features.telemetry_heart_beat_collected
    def test_app_heartbeat(self):
        """Check for heartbeat or messages within interval and valid started and closing messages"""

        prev_message_time = None
        expected_heartbeat_interval = context.telemetry_heartbeat_interval

        # This interval can't be perfeclty exact, give some room for tests
        UPPER_LIMIT = timedelta(seconds=expected_heartbeat_interval * 2).total_seconds()
        LOWER_LIMIT = timedelta(seconds=expected_heartbeat_interval * 0.75).total_seconds()

        fmt = "%Y-%m-%dT%H:%M:%S.%f"

        telemetry_data = list(interfaces.library.get_telemetry_data())
        assert len(telemetry_data) > 0, "No telemetry messages"

        heartbeats = [d for d in telemetry_data if d["request"]["content"].get("request_type") == "app-heartbeat"]
        assert len(heartbeats) >= 2, "Did not receive, at least, 2 heartbeats"

        # depending on the tracer, the very first heartbeat may be sent in a request that pays the
        # connection initialization time. This time is very unpredictible, so we remove the very
        # first heartbeat from the list
        heartbeats.pop(0)

        for data in heartbeats:
            curr_message_time = datetime.strptime(data["request"]["timestamp_start"], fmt)
            if prev_message_time is None:
                logger.debug(f"Heartbeat in {data['log_filename']}: {curr_message_time}")
            else:
                delta = (curr_message_time - prev_message_time).total_seconds()
                logger.debug(f"Heartbeat in {data['log_filename']}: {curr_message_time} => {delta}s ellapsed")

                assert (
                    delta < UPPER_LIMIT
                ), f"Heartbeat sent too slow ({delta}s). It should be sent every {expected_heartbeat_interval}s"
                assert (
                    delta > LOWER_LIMIT
                ), f"Heartbeat sent too fast ({delta}s). It should be sent every {expected_heartbeat_interval}s"

            prev_message_time = curr_message_time

    def setup_app_dependencies_loaded(self):
        weblog.get("/load_dependency")

    @irrelevant(library="php")
    @irrelevant(library="cpp")
    @irrelevant(library="golang")
    @irrelevant(library="python")
    @missing_feature(context.library < "ruby@1.22.0", reason="Telemetry V2 is not implemented yet")
    @bug(
        library="java",
        reason="""
        A Java application can be redeployed to the same server for many times (for the same JVM process). 
        That means, every new deployment/reload of application will cause reloading classes/dependencies and as the result we will see duplications.
        """,
    )
    def test_app_dependencies_loaded(self):
        """test app-dependencies-loaded requests"""

        test_loaded_dependencies = {
            "dotnet": {"NodaTime": False},
            "nodejs": {"glob": False},
            "java": {"httpclient": False},
            "ruby": {"bundler": False},
        }

        test_defined_dependencies = {
            "dotnet": {},
            "nodejs": {
                "body-parser": False,
                "cookie-parser": False,
                "express": False,
                "express-xml-bodyparser": False,
                "pg": False,
                "glob": False,
            },
            "java": {
                "spring-boot-starter-json": False,
                "spring-boot-starter-jdbc": False,
                "jackson-dataformat-xml": False,
                "dd-trace-api": False,
                "opentracing-api": False,
                "opentracing-util": False,
                "postgresql": False,
                "java-driver-core": False,
                "metrics-core": False,
                "mongo-java-driver": False,
                "ognl": False,
                "protobuf-java": False,
                "grpc-netty-shaded": False,
                "grpc-protobuf": False,
                "grpc-stub": False,
                "jaxb-api": False,
                "bcprov-jdk15on": False,
                "hsqldb": False,
                "spring-boot-starter-security": False,
                "spring-ldap-core": False,
                "spring-security-ldap": False,
                "unboundid-ldapsdk": False,
                "httpclient": False,
            },
            "ruby": {},
        }

        seen_loaded_dependencies = test_loaded_dependencies[context.library.library]
        seen_defined_dependencies = test_defined_dependencies[context.library.library]

        for data in interfaces.library.get_telemetry_data():
            content = data["request"]["content"]
            if content.get("request_type") == "app-started":
                if "dependencies" in content["payload"]:
                    for dependency in content["payload"]["dependencies"]:
                        dependency_id = dependency["name"]  # +dep["version"]
                        if dependency_id in seen_loaded_dependencies:
                            raise Exception("Loaded dependency should not be in app-started")
                        if dependency_id not in seen_defined_dependencies:
                            continue
                        seen_defined_dependencies[dependency_id] = True
            elif content.get("request_type") == "app-dependencies-loaded":
                for dependency in content["payload"]["dependencies"]:
                    dependency_id = dependency["name"]  # +dependency["version"]
                    if seen_loaded_dependencies.get(dependency_id) is True:
                        raise Exception(
                            "Loaded dependency event sent multiple times for same dependency " + dependency_id
                        )
                    if dependency_id in seen_defined_dependencies:
                        seen_defined_dependencies[dependency_id] = True
                    if dependency_id in seen_loaded_dependencies:
                        seen_loaded_dependencies[dependency_id] = True

        for dependency, seen in seen_loaded_dependencies.items():
            if not seen:
                raise Exception(dependency + " not received in app-dependencies-loaded message")

    @irrelevant(library="ruby")
    @irrelevant(library="golang")
    @irrelevant(library="dotnet")
    @irrelevant(library="python")
    @irrelevant(library="php")
    @irrelevant(library="java")
    @irrelevant(library="nodejs")
    def test_api_still_v1(self):
        """Test that the telemetry api is still at version v1
        If this test fails, please mark Test_TelemetryV2 as released for the current version of the tracer,
        and this test as no longer relevant
        """

        def validator(data):
            assert is_v1_payload(data)

        self.validate_library_telemetry_data(validator=validator, success_by_default=True)

    @irrelevant(library="cpp")
    @missing_feature(
        context.library in ("golang", "cpp", "php"), reason="Telemetry is not implemented yet. ",
    )
    @missing_feature(context.library < "ruby@1.22.0", reason="Telemetry V2 is not implemented yet")
    @bug(
        library="python",
        reason="""
            configuration is not properly populating for python
        """,
    )
    def test_app_started_client_configuration(self):
        """Assert that default and other configurations that are applied upon start time are sent with the app-started event"""
        test_configuration = {
            "dotnet": {},
            "nodejs": {"hostname": "proxy", "port": 8126, "appsec.enabled": True},
            # to-do :need to add configuration keys once python bug is fixed
            "python": {},
            "java": {"trace_agent_port": 8126, "telemetry_heartbeat_interval": 2},
            "ruby": {"DD_AGENT_TRANSPORT": "TCP"},
        }
        configuration_map = test_configuration[context.library.library]

        def validator(data):
            if get_request_type(data) == "app-started":
                content = data["request"]["content"]
                configurations = content["payload"]["configuration"]
                configurations_present = []
                for cnf in configurations:
                    configuration_name = cnf["name"]
                    if context.library.library == "java":
                        # support for older versions of Java Tracer
                        configuration_name = configuration_name.replace(".", "_")
                    if configuration_name in configuration_map:
                        expected_value = str(configuration_map.get(configuration_name))
                        configuration_value = str(cnf["value"])
                        if configuration_value != expected_value:
                            raise Exception(
                                "Client Configuration "
                                + configuration_name
                                + " expected value is "
                                + str(expected_value)
                                + " but found "
                                + str(configuration_value)
                            )
                        configurations_present.append(configuration_name)
                for cnf in configuration_map:
                    if cnf not in configurations_present:
                        raise Exception(
                            "Client Configuration information is not accurately reported, "
                            + cnf
                            + " is not present in configuration on app-started event"
                        )

        self.validate_library_telemetry_data(validator)

    def setup_app_product_change(self):
        weblog.get("/enable_product")

    @missing_feature(
        context.library in ("dotnet", "nodejs", "java", "python", "golang", "cpp", "php", "ruby"),
        reason="Weblog GET/enable_product and app-product-change event is not implemented yet.",
    )
    def test_app_product_change(self):
        """Test product change data when product is enabled"""

        telemetry_data = list(interfaces.library.get_telemetry_data())
        if len(telemetry_data) == 0:
            raise Exception("No telemetry data to validate on")

        app_product_change_event_found = False
        for data in telemetry_data:
            if get_request_type(data) == "app-product-change":
                content = data["request"]["content"]
                app_product_change_event_found = True
                products = content["payload"]["products"]
                for product in products:
                    appsec_enabled = product["appsec"]["enabled"]
                    profiler_enabled = product["profiler"]["enabled"]
                    dynamic_instrumentation_enabled = product["dynamic_instrumentation"]["enabled"]
                    assert (
                        appsec_enabled is True
                    ), f"Product appsec Product profiler enabled was expected to be True, found False"
                    assert profiler_enabled is True, f"Product profiler enabled was expected to be True, found False"
                    assert (
                        dynamic_instrumentation_enabled is False
                    ), f"Product dynamic_instrumentation enabled was expected to be False, found True"

        if app_product_change_event_found is False:
            raise Exception("app-product-change is not emitted when product change is enabled")


@features.telemetry_instrumentation
class Test_APMOnboardingInstallID:
    """Tests that APM onboarding install information is correctly propagated"""

    def test_traces_contain_install_id(self):
        """Assert that at least one trace carries APM onboarding info"""

        def validate_at_least_one_span_with_tag(tag):
            for _, span in interfaces.agent.get_spans():
                meta = span.get("meta", {})
                if tag in meta:
                    break
            else:
                raise Exception(f"Did not find tag {tag} in any spans")

        validate_at_least_one_span_with_tag("_dd.install.id")
        validate_at_least_one_span_with_tag("_dd.install.time")
        validate_at_least_one_span_with_tag("_dd.install.type")


@features.telemetry_api_v2_implemented
class Test_TelemetryV2:
    """Test telemetry v2 specific constraints"""

    @missing_feature(library="golang", reason="Product started missing")
    @missing_feature(library="dotnet", reason="Product started missing")
    @missing_feature(library="php", reason="Product started missing (both in libdatadog and php)")
    @missing_feature(library="python", reason="Product started missing in app-started payload")
    def test_app_started_product_info(self):
        """Assert that product information is accurately reported by telemetry"""

        for data in interfaces.library.get_telemetry_data(flatten_message_batches=True):
            if not is_v2_payload(data):
                continue
            if get_request_type(data) == "app-started":
                products = data["request"]["content"]["payload"]["products"]
                assert (
                    "appsec" in products
                ), "Product information is not accurately reported by telemetry on app-started event"

    @missing_feature(context.library < "ruby@1.22.0", reason="dd-client-library-version missing")
    @bug(library="python", reason="library versions do not match due to different origins")
    def test_telemetry_v2_required_headers(self):
        """Assert library add the relevant headers to telemetry v2 payloads """

        def validator(data):
            telemetry = data["request"]["content"]
            assert get_header(data, "request", "dd-telemetry-api-version") == telemetry.get("api_version")
            assert get_header(data, "request", "dd-telemetry-request-type") == telemetry.get("request_type")
            application = telemetry.get("application", {})
            assert get_header(data, "request", "dd-client-library-language") == application.get("language_name")
            assert get_header(data, "request", "dd-client-library-version") == application.get("tracer_version")

        interfaces.library.validate_telemetry(validator=validator, success_by_default=True)


@features.telemetry_api_v2_implemented
class Test_ProductsDisabled:
    """Assert that product information are not reported when products are disabled in telemetry"""

    @scenarios.telemetry_app_started_products_disabled
    def test_app_started_product_disabled(self):

        data_found = False
        app_started_found = False

        telemetry_data = interfaces.library.get_telemetry_data()

        for data in telemetry_data:
            data_found = True

            if get_request_type(data) != "app-started":
                continue

            app_started_found = True

            payload = data["request"]["content"]["payload"]

            assert (
                "products" in payload
            ), f"Product information was expected in app-started event, but was missing in {data['log_filename']}"

            for product, details in payload["products"].items():
                assert (
                    details.get("enabled") is False
                ), f"Product information expected to indicate {product} is disabled, but found enabled"

        if not data_found:
            raise ValueError("No telemetry data to validate on")

        if not app_started_found:
            raise ValueError("app-started event not found in telemetry data")


@features.dd_telemetry_dependency_collection_enabled_supported
@scenarios.telemetry_dependency_loaded_test_for_dependency_collection_disabled
class Test_DependencyEnable:
    """ Tests on DD_TELEMETRY_DEPENDENCY_COLLECTION_ENABLED flag """

    def setup_app_dependency_loaded_not_sent_dependency_collection_disabled(self):
        weblog.get("/load_dependency")

    def test_app_dependency_loaded_not_sent_dependency_collection_disabled(self):
        """app-dependencies-loaded request should not be sent if DD_TELEMETRY_DEPENDENCY_COLLECTION_ENABLED is false"""

        for data in interfaces.library.get_telemetry_data():
            if get_request_type(data) == "app-dependencies-loaded":
                raise Exception("request_type app-dependencies-loaded should not be sent by this tracer")


@features.telemetry_message_batch
class Test_MessageBatch:
    """ Tests on Message batching """

    def setup_message_batch_enabled(self):
        weblog.get("/load_dependency")
        weblog.get("/enable_integration")
        weblog.get("/enable_product")

    def test_message_batch_enabled(self):
        """Test that events are sent in message batches"""
        event_list = []
        for data in interfaces.library.get_telemetry_data(flatten_message_batches=False):
            content = data["request"]["content"]
            event_list.append(content.get("request_type"))

        assert "message-batch" in event_list, f"Expected one or more message-batch events: {event_list}"


@features.telemetry_api_v2_implemented
class Test_Log_Generation:
    """Assert that logs reported by default, and not reported when logs generation is disabled in telemetry"""

    def _get_filename_with_logs(self):
        all_data = interfaces.library.get_telemetry_data()
        return [data["log_filename"] for data in all_data if get_request_type(data) == "logs"]

    @scenarios.telemetry_log_generation_disabled
    def test_log_generation_disabled(self):
        """ When DD_TELEMETRY_LOGS_COLLECTION_ENABLED=false, no log should be sent"""
        assert len(self._get_filename_with_logs()) == 0, "Library shouldn't have sent any log"

    def test_log_generation_enabled(self):
        """ By default, some logs should be sent"""
        assert len(self._get_filename_with_logs()) != 0


@features.telemetry_metrics_collected
@scenarios.telemetry_metric_generation_disabled
class Test_Metric_Generation_Disabled:
    """Assert that metrics are not reported when metric generation is disabled in telemetry"""

    def test_metric_generation_disabled(self):
        for data in interfaces.library.get_telemetry_data(flatten_message_batches=True):
            if get_request_type(data) == "generate-metrics":
                raise Exception("Metric generate event is sent when metric generation is disabled")


@features.telemetry_metrics_collected
@scenarios.telemetry_metric_generation_enabled
class Test_Metric_Generation_Enabled:
    """Assert that metrics are reported when metric generation is enabled in telemetry"""

    def setup_metric_generation_enabled(self):
        weblog.get("/")
        # Wait for at least 2 metric flushes, i.e. 20s
        METRIC_FLUSH_INTERVAL = 10  # This is constant by design
        logger.debug("Waiting 20s for metric flushes...")
        time.sleep(METRIC_FLUSH_INTERVAL * 2)
        logger.debug("Wait complete")

    def test_metric_generation_enabled(self):
        self.assert_general_metrics()
        self.assert_tracer_metrics()
        self.assert_telemetry_metrics()

    def assert_general_metrics(self):

        namespace = "general"
        self.assert_count_metric(namespace, "logs_created", expect_at_least=1)

    def assert_tracer_metrics(self):

        namespace = "tracers"
        self.assert_count_metric(namespace, "spans_created", expect_at_least=1)
        self.assert_count_metric(namespace, "spans_finished", expect_at_least=1)
        self.assert_count_metric(namespace, "spans_enqueued_for_serialization", expect_at_least=1)
        self.assert_count_metric(namespace, "trace_segments_created", expect_at_least=1)
        self.assert_count_metric(namespace, "trace_chunks_enqueued_for_serialization", expect_at_least=1)
        self.assert_count_metric(namespace, "trace_chunks_sent", expect_at_least=1)
        self.assert_count_metric(namespace, "trace_segments_closed", expect_at_least=1)
        self.assert_count_metric(namespace, "trace_api.requests", expect_at_least=1)
        self.assert_count_metric(namespace, "trace_api.responses", expect_at_least=1)

    def assert_telemetry_metrics(self):

        namespace = "telemetry"
        self.assert_count_metric(namespace, "telemetry_api.requests", expect_at_least=1)
        self.assert_count_metric(namespace, "telemetry_api.responses", expect_at_least=1)

    def assert_count_metric(self, namespace, metric, expect_at_least):
        series = list(interfaces.library.get_telemetry_metric_series(namespace, metric))
        if len(series) == 0 and expect_at_least > 0:
            raise Exception(f"No telemetry data received for metric {namespace}.{metric}")

        count = 0
        for s in series:
            # assert correct type (count)
            # assert points total
            assert s["common"] is True
            assert s["type"] == "count"
            assert len(s["points"]) >= 1
            for p in s["points"]:
                count = count + p[1]

        assert count >= expect_at_least
