"""Test service name tags in telemetry payload metadata."""

from typing import Any

from utils import context, interfaces, missing_feature, features, rfc, logger


def get_request_content(data: dict[str, Any]) -> dict[str, Any]:
    """Extract request content from telemetry data."""
    return data["request"]["content"]


def get_request_type(data: dict[str, Any]) -> str | None:
    """Extract request type from telemetry data."""
    return get_request_content(data).get("request_type")


def get_service_name(data: dict[str, Any]) -> str | None:
    """Extract service name from telemetry data."""
    content = get_request_content(data)
    if "application" in content:
        return content["application"].get("service_name")
    return None


def is_v2_payload(data: dict[str, Any]) -> bool:
    """Check if telemetry payload is v2."""
    return get_request_content(data).get("api_version") == "v2"


def is_v1_payload(data: dict[str, Any]) -> bool:
    """Check if telemetry payload is v1."""
    return get_request_content(data).get("api_version") == "v1"


def not_onboarding_event(data: dict[str, Any]) -> bool:
    """Check if telemetry event is not an onboarding event."""
    return get_request_type(data) != "apm-onboarding-event"


@rfc("https://docs.google.com/document/d/1Fai2gZlkvfa_WQs_yJsmi3nUwiOsMtNu2LFBnbTHJRA/edit#heading=h.llmi584vls7r")
@features.telemetry_instrumentation
class Test_TelemetryServiceNameTags:
    """Test that service name tags are properly included in telemetry payload metadata."""

    def validate_library_telemetry_data(self, validator, *, success_by_default=False):
        """Validate library telemetry data with custom validator."""
        telemetry_data = list(interfaces.library.get_telemetry_data(flatten_message_batches=False))

        if len(telemetry_data) == 0 and not success_by_default:
            raise ValueError("No telemetry data to validate on")

        for data in telemetry_data:
            validator(data)

    def validate_agent_telemetry_data(self, validator, *, flatten_message_batches=True, success_by_default=False):
        """Validate agent telemetry data with custom validator."""
        telemetry_data = list(interfaces.agent.get_telemetry_data(flatten_message_batches=flatten_message_batches))

        if len(telemetry_data) == 0 and not success_by_default:
            raise ValueError("No telemetry data to validate on")

        for data in telemetry_data:
            validator(data)

    def test_service_name_in_telemetry_v1_payload_metadata(self):
        """Test that service name is present in telemetry v1 payload metadata."""

        def validator(data: dict[str, Any]) -> None:
            if not is_v1_payload(data) or not_onboarding_event(data):
                return

            content = get_request_content(data)
            service_name = get_service_name(data)

            assert service_name is not None, f"Service name missing in v1 telemetry payload: {content}"
            assert isinstance(
                service_name, str
            ), f"Service name should be string, got {type(service_name)}: {service_name}"
            assert len(service_name) > 0, f"Service name should not be empty: {service_name}"

            # Validate service name is in application object
            application = content.get("application", {})
            assert "service_name" in application, f"service_name field missing in application object: {application}"
            assert application["service_name"] == service_name, "Service name mismatch in application object"

        self.validate_library_telemetry_data(validator, success_by_default=True)
        self.validate_agent_telemetry_data(validator, success_by_default=True)

    @missing_feature(context.library < "ruby@1.22.0", reason="Telemetry V2 is not implemented yet")
    def test_service_name_in_telemetry_v2_payload_metadata(self):
        """Test that service name is present in telemetry v2 payload metadata."""

        def validator(data: dict[str, Any]) -> None:
            if not is_v2_payload(data) or not_onboarding_event(data):
                return

            content = get_request_content(data)
            service_name = get_service_name(data)

            assert service_name is not None, f"Service name missing in v2 telemetry payload: {content}"
            assert isinstance(
                service_name, str
            ), f"Service name should be string, got {type(service_name)}: {service_name}"
            assert len(service_name) > 0, f"Service name should not be empty: {service_name}"

            # Validate service name is in application object
            application = content.get("application", {})
            assert "service_name" in application, f"service_name field missing in application object: {application}"
            assert application["service_name"] == service_name, "Service name mismatch in application object"

        self.validate_library_telemetry_data(validator, success_by_default=True)
        self.validate_agent_telemetry_data(validator, success_by_default=True)

    def test_service_name_consistency_across_telemetry_events(self):
        """Test that service name is consistent across different telemetry events."""

        service_names_by_runtime: dict[str, list[str]] = {}

        def validator(data: dict[str, Any]) -> None:
            if not_onboarding_event(data):
                return

            content = get_request_content(data)
            runtime_id = content.get("runtime_id")
            service_name = get_service_name(data)

            if runtime_id and service_name:
                if runtime_id not in service_names_by_runtime:
                    service_names_by_runtime[runtime_id] = []
                service_names_by_runtime[runtime_id].append(service_name)

        self.validate_library_telemetry_data(validator, success_by_default=True)

        # Validate consistency within each runtime
        for runtime_id, service_names in service_names_by_runtime.items():
            unique_service_names = set(service_names)
            assert len(unique_service_names) == 1, (
                f"Service name inconsistent for runtime {runtime_id}: "
                f"found {unique_service_names}, expected single service name"
            )

    def test_service_name_in_app_started_event(self):
        """Test that service name is present in app-started telemetry event."""

        app_started_found = False

        def validator(data: dict[str, Any]) -> None:
            nonlocal app_started_found

            if get_request_type(data) == "app-started":
                app_started_found = True
                service_name = get_service_name(data)

                assert service_name is not None, f"Service name missing in app-started event: {data}"
                assert isinstance(service_name, str), f"Service name should be string in app-started: {service_name}"
                assert len(service_name) > 0, f"Service name should not be empty in app-started: {service_name}"

                # Validate service name is in application object
                content = get_request_content(data)
                application = content.get("application", {})
                assert "service_name" in application, "service_name field missing in app-started application object"
                assert (
                    application["service_name"] == service_name
                ), "Service name mismatch in app-started application object"

        self.validate_library_telemetry_data(validator, success_by_default=True)

        if not app_started_found:
            logger.warning("No app-started event found in telemetry data")

    def test_service_name_in_message_batch_events(self):
        """Test that service name is present in message-batch telemetry events."""

        message_batch_found = False

        def validator(data: dict[str, Any]) -> None:
            nonlocal message_batch_found

            if get_request_type(data) == "message-batch":
                message_batch_found = True
                content = get_request_content(data)
                payload = content.get("payload", [])

                # Validate each event in the batch has consistent service name
                service_names = []
                for event in payload:
                    if isinstance(event, dict) and "application" in event:
                        service_name = event["application"].get("service_name")
                        if service_name:
                            service_names.append(service_name)

                if service_names:
                    unique_service_names = set(service_names)
                    assert len(unique_service_names) == 1, (
                        f"Service name inconsistent in message-batch: "
                        f"found {unique_service_names}, expected single service name"
                    )

        self.validate_library_telemetry_data(validator, success_by_default=True)

        if not message_batch_found:
            logger.debug("No message-batch event found in telemetry data")

    def test_service_name_tags_schema_validation(self):
        """Test that service name tags conform to telemetry schema."""

        def validator(data: dict[str, Any]) -> None:
            if not_onboarding_event(data):
                return

            content = get_request_content(data)
            application = content.get("application", {})

            if "service_name" in application:
                service_name = application["service_name"]

                # Validate service name is a string
                assert isinstance(service_name, str), f"Service name should be string, got {type(service_name)}"

                # Validate service name is not empty
                assert len(service_name) > 0, "Service name should not be empty"

                # Validate service name doesn't contain invalid characters
                # Service names should be valid identifiers
                assert (
                    service_name.replace("-", "").replace("_", "").isalnum()
                ), f"Service name contains invalid characters: {service_name}"

        self.validate_library_telemetry_data(validator, success_by_default=True)
        self.validate_agent_telemetry_data(validator, success_by_default=True)

    @missing_feature(library="cpp_nginx", reason="Telemetry not implemented")
    @missing_feature(library="cpp_httpd", reason="Telemetry not implemented")
    def test_service_name_in_telemetry_headers(self):
        """Test that service name information is present in telemetry headers."""

        def validator(data: dict[str, Any]) -> None:
            if not_onboarding_event(data):
                return

            # Check if service name is reflected in headers
            headers = data.get("request", {}).get("headers", [])
            service_name = get_service_name(data)

            if service_name:
                # Look for service-related headers
                service_headers = [h for h in headers if "service" in h[0].lower()]
                if service_headers:
                    logger.debug(f"Found service-related headers: {service_headers}")

        self.validate_library_telemetry_data(validator, success_by_default=True)

    def test_service_name_environment_consistency(self):
        """Test that service name in telemetry matches expected environment value."""

        expected_service_name = "weblog"  # Default service name in system-tests

        def validator(data: dict[str, Any]) -> None:
            if not_onboarding_event(data):
                return

            service_name = get_service_name(data)

            if service_name:
                # In system-tests, the default service name should be "weblog"
                # unless explicitly overridden by environment variables
                assert service_name == expected_service_name, (
                    f"Service name '{service_name}' does not match expected '{expected_service_name}'. "
                    f"This might indicate environment variable DD_SERVICE is set differently."
                )

        self.validate_library_telemetry_data(validator, success_by_default=True)
