from datetime import datetime, timedelta
import time
from utils import context, interfaces, missing_feature, bug, flaky, released, irrelevant, weblog, scenarios
from utils.tools import logger
from utils.interfaces._misc_validators import HeadersPresenceValidator, HeadersMatchValidator


@released(python="1.7.0", dotnet="2.12.0", java="0.108.1", nodejs="3.2.0", ruby="1.4.0", golang="1.49.0")
@bug(context.uds_mode and context.library < "nodejs@3.7.0")
@missing_feature(library="cpp")
@missing_feature(library="php")
@missing_feature(weblog_variant="spring-boot-3-native", reason="GraalVM. Tracing support only")
class Test_Telemetry:
    """Test that instrumentation telemetry is sent"""

    # containers for telemetry request to check consistency between library payloads and agent payloads
    library_requests = {}
    agent_requests = {}

    def validate_library_telemetry_data(self, validator, success_by_default=False):
        telemetry_data = list(interfaces.library.get_telemetry_data(flatten_message_batches=False))

        if len(telemetry_data) == 0:
            if not success_by_default:
                raise Exception("No telemetry data to validate on")

        for data in telemetry_data:
            validator(data)

    def validate_agent_telemetry_data(self, validator, success_by_default=False):
        telemetry_data = list(interfaces.agent.get_telemetry_data())

        if len(telemetry_data) == 0:
            if not success_by_default:
                raise Exception("No telemetry data to validate on")

        for data in telemetry_data:
            validator(data)

    def test_telemetry_message_data_size(self):
        """Test telemetry message data size"""

        def validator(data):
            if data["request"]["length"] / 1000000 >= 5:
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

        def not_onboarding_event(data):
            return data["request"]["content"].get("request_type") != "apm-onboarding-event"

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
            path_filter="/api/v2/apmtelemetry", request_headers=["datadog-container-id"],
        )

    def test_telemetry_message_required_headers(self):
        """Test telemetry messages contain required headers"""

        def not_onboarding_event(data):
            return data["request"]["content"].get("request_type") != "apm-onboarding-event"

        interfaces.agent.assert_headers_presence(
            path_filter="/api/v2/apmtelemetry",
            request_headers=["dd-api-key", "dd-telemetry-api-version", "dd-telemetry-request-type"],
            check_condition=not_onboarding_event,
        )

    @missing_feature(library="python")
    # @flaky(library="ruby", reason="Sometimes, seq_id jump from N to N+2")
    def test_seq_id(self):
        """Test that messages are sent sequentially"""

        MAX_OUT_OF_ORDER_LAG = 0.3  # s

        max_seq_id = 0
        received_max_time = None
        seq_ids = []

        fmt = "%Y-%m-%dT%H:%M:%S.%f"

        telemetry_data = list(interfaces.library.get_telemetry_data(flatten_message_batches=False))
        if len(telemetry_data) == 0:
            raise Exception("No telemetry data to validate on")

        for data in telemetry_data:

            seq_id = data["request"]["content"]["seq_id"]
            timestamp_start = data["request"]["timestamp_start"]
            curr_message_time = datetime.strptime(timestamp_start, fmt)
            logger.debug(f"Telemetry message at {timestamp_start.split('T')[1]} {seq_id} in {data['log_filename']}")

            if 200 <= data["response"]["status_code"] < 300:
                seq_ids.append((seq_id, data["log_filename"]))
            if seq_id > max_seq_id:
                max_seq_id = seq_id
                received_max_time = curr_message_time
            else:
                if received_max_time is not None and (curr_message_time - received_max_time) > timedelta(
                    seconds=MAX_OUT_OF_ORDER_LAG
                ):
                    raise Exception(
                        f"Received message with seq_id {seq_id} to far more than"
                        f"100ms after message with seq_id {max_seq_id}"
                    )

        seq_ids.sort()
        for i in range(len(seq_ids) - 1):
            diff = seq_ids[i + 1][0] - seq_ids[i][0]
            if diff == 0:
                raise Exception(
                    f"Detected 2 telemetry messages with same seq_id {seq_ids[i + 1][1]} and {seq_ids[i][1]}"
                )

            if diff > 1:
                logger.error(f"{seq_ids[i + 1][0]} {seq_ids[i][0]}")
                raise Exception(f"Detected non consecutive seq_ids between {seq_ids[i + 1][1]} and {seq_ids[i][1]}")

    @bug(library="ruby", reason="app-started not sent")
    def test_app_started_sent_exactly_once(self):
        """Request type app-started is sent exactly once"""

        count = 0

        for data in interfaces.library.get_telemetry_data():
            if data["request"]["content"].get("request_type") == "app-started":
                logger.debug(
                    f"Found app-started in {data['log_filename']}. Response from agent: {data['response']['status_code']}"
                )
                if data["response"]["status_code"] == 202:
                    count += 1

        assert count == 1

    @bug(library="ruby", reason="app-started not sent")
    @bug(library="python", reason="app-started not sent first")
    @flaky(library="nodejs", reason="APPSEC-10465")
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
            first_message = telemetry_data[0]["request"]["content"]
            assert first_message.get("request_type") == "app-started", "app-started was not the first message"

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

        def not_onboarding_event(data):
            return data["request"]["content"].get("request_type") != "apm-onboarding-event"

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
    def test_app_dependencies_loaded_not_sent(self):
        """app-dependencies-loaded request should not be sent"""
        # Request type app-dependencies-loaded is never sent from certain language tracers
        # In case this changes we need to adjust the backend, by adding the language to this list
        # https://github.com/DataDog/dd-go/blob/prod/domains/appsec/libs/vulnerability_management/model.go#L262
        # This change means we cannot deduplicate runtime with the same library dependencies in the backend since
        # we never have guarantees that we have all the dependencies at one point in time

        def validator(data):
            if data["request"]["content"].get("request_type") == "app-dependencies-loaded":
                raise ValueError("request_type app-dependencies-loaded should not be used by this tracer")

        self.validate_library_telemetry_data(validator)

    # @flaky(library="dotnet", reason="Heartbeats are sometimes sent too slowly")
    # @flaky(library="python", reason="Heartbeats are sometimes sent too slowly")
    @flaky(library="nodejs", reason="AIT-7943")
    @bug(context.library < "java@1.18.0", reason="Telemetry interval drifts")
    @missing_feature(context.library < "ruby@1.13.0", reason="DD_TELEMETRY_HEARTBEAT_INTERVAL not supported")
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
    @irrelevant(library="ruby")
    @bug(
        library="java",
        reason="""
        A Java application can be redeployed to the same server for many times (for the same JVM process). 
        That means, every new deployment/reload of application will cause reloading classes/dependencies and as the result we will see duplications.
        """,
    )
    @bug(library="dotnet", reason="NodaTime not received in app-dependencies-loaded message")
    def test_app_dependencies_loaded(self):
        """test app-dependencies-loaded requests"""

        test_loaded_dependencies = {
            "dotnet": {"NodaTime": False},
            "nodejs": {"glob": False},
            "java": {"httpclient": False},
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

    @missing_feature(
        context.library in ("java", "nodejs", "golang", "dotnet"), reason="Telemetry V2 is not implemented yet. ",
    )
    def test_app_started_product_info(self):
        """Assert that product information is accurately reported by telemetry"""

        def validator(data):
            if data["request"]["content"].get("request_type") == "app-started":
                content = data["request"]["content"]
                products = content["application"]["products"]
                assert (
                    "appsec" in products
                ), "Product information is not accurately reported by telemetry on app-started event"

        self.validate_library_telemetry_data(validator)

    @irrelevant(library="cpp")
    @missing_feature(
        context.library in ("golang", "ruby", "cpp", "php"), reason="Telemetry is not implemented yet. ",
    )
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
            "java": {"trace.agent.port": 8126, "telemetry.heartbeat.interval": 2},
        }
        configuration_map = test_configuration[context.library.library]

        def validator(data):
            if data["request"]["content"].get("request_type") == "app-started":
                content = data["request"]["content"]
                configurations = content["payload"]["configuration"]
                configurations_present = []
                for cnf in configurations:
                    if cnf["name"] in configuration_map:
                        configuration_name = cnf["name"]
                        expected_value = str(configuration_map.get(cnf["name"]))
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
                            + "is not present in configuration on app-started event"
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
            content = data["request"]["content"]
            if content.get("request_type") == "app-product-change":
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


@released(python="1.7.0", dotnet="2.12.0", java="0.108.1", nodejs="3.2.0", ruby="1.4.0")
@bug(context.uds_mode and context.library < "nodejs@3.7.0")
@missing_feature(library="cpp")
@missing_feature(library="php")
@missing_feature(weblog_variant="spring-boot-3-native", reason="GraalVM. Tracing support only")
@irrelevant(library="golang", reason="products info is always in app-started for golang")
class Test_ProductsDisabled:
    """Assert that product information are not reported when products are disabled in telemetry"""

    @scenarios.telemetry_app_started_products_disabled
    def test_app_started_product_disabled(self):

        telemetry_data = list(interfaces.library.get_telemetry_data())
        if len(telemetry_data) == 0:
            raise Exception("No telemetry data to validate on")

        for data in telemetry_data:
            if data["request"]["content"].get("request_type") == "app-started":
                content = data["request"]["content"]
                assert (
                    "products" in content["payload"]
                ), "Product information was expected in app-started event, but was missing"
                products = content["payload"]["products"]
                for product, details in products.items():
                    assert (
                        details.get("enabled") is False
                    ), f"Product information expected to indicate {product} is disabled, but found enabled"


@released(cpp="?", dotnet="?", golang="?", java="1.7.0", nodejs="?", php="?", python="?", ruby="1.4.0")
@scenarios.telemetry_dependency_loaded_test_for_dependency_collection_disabled
class Test_DependencyEnable:
    """ Tests on DD_TELEMETRY_DEPENDENCY_COLLECTION_ENABLED flag """

    def setup_app_dependency_loaded_not_sent_dependency_collection_disabled(self):
        weblog.get("/load_dependency")

    def test_app_dependency_loaded_not_sent_dependency_collection_disabled(self):
        """app-dependencies-loaded request should not be sent if DD_TELEMETRY_DEPENDENCY_COLLECTION_ENABLED is false"""

        for data in interfaces.library.get_telemetry_data():
            if data["request"]["content"].get("request_type") == "app-dependencies-loaded":
                raise Exception("request_type app-dependencies-loaded should not be sent by this tracer")


@released(cpp="?", dotnet="?", golang="?", java="?", nodejs="?", php="?", python="?", ruby="?")
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


@released(cpp="?", dotnet="?", golang="?", java="?", nodejs="?", php="?", python="?", ruby="1.4.0")
@scenarios.telemetry_log_generation_disabled
class Test_Log_Generation:
    """Assert that logs are not reported when logs generation is disabled in telemetry"""

    def test_log_generation_disabled(self):

        telemetry_data = list(interfaces.library.get_telemetry_data())
        if len(telemetry_data) == 0:
            raise Exception("No telemetry data to validate on")

        for data in telemetry_data:
            if data["request"]["content"].get("request_type") == "logs":
                content = data["request"]["content"]
                raise Exception(" Logs event is sent when log generation is disabled")


@released(cpp="?", dotnet="?", golang="?", java="?", nodejs="?", php="?", python="?", ruby="1.4.0")
@scenarios.telemetry_metric_generation_disabled
class Test_Metric_Generation:
    """Assert that metrics are not reported when metric generation is disabled in telemetry"""

    def test_metric_generation_disabled(self):

        telemetry_data = list(interfaces.library.get_telemetry_data())
        if len(telemetry_data) == 0:
            raise Exception("No telemetry data to validate on")

        for data in telemetry_data:
            if data["request"]["content"].get("request_type") == "generate-metrics":
                raise Exception("Metric generate event is sent when metric generation is disabled")
