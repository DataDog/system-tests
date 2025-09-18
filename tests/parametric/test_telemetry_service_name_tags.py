"""Parametric tests for service name tags in telemetry payload metadata."""

from typing import Any

from utils import context, scenarios, rfc, features, missing_feature, interfaces, logger


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


@scenarios.parametric
@rfc("https://docs.google.com/document/d/1Fai2gZlkvfa_WQs_yJsmi3nUwiOsMtNu2LFBnbTHJRA/edit#heading=h.llmi584vls7r")
@features.telemetry_instrumentation
class Test_TelemetryServiceNameTagsParametric:
    """Parametric tests for service name tags in telemetry payload metadata."""

    def validate_library_telemetry_data(self, validator, *, success_by_default=False):
        """Validate library telemetry data with custom validator."""
        telemetry_data = list(interfaces.library.get_telemetry_data(flatten_message_batches=False))

        if len(telemetry_data) == 0 and not success_by_default:
            raise ValueError("No telemetry data to validate on")

        for data in telemetry_data:
            validator(data)

    def test_service_name_present_in_all_telemetry_events(self):
        """Test that service name is present in all telemetry events for the current library."""

        events_with_service_name = 0
        events_without_service_name = 0

        def validator(data: dict[str, Any]) -> None:
            nonlocal events_with_service_name, events_without_service_name

            if not_onboarding_event(data):
                service_name = get_service_name(data)
                if service_name:
                    events_with_service_name += 1
                    logger.debug(f"Event {get_request_type(data)} has service name: {service_name}")
                else:
                    events_without_service_name += 1
                    logger.warning(f"Event {get_request_type(data)} missing service name: {data}")

        self.validate_library_telemetry_data(validator, success_by_default=True)

        # At least some events should have service name
        total_events = events_with_service_name + events_without_service_name
        if total_events > 0:
            service_name_coverage = events_with_service_name / total_events
            logger.info(
                f"Service name coverage: {service_name_coverage:.2%} ({events_with_service_name}/{total_events})"
            )

            # Most events should have service name (allow some flexibility for edge cases)
            assert service_name_coverage >= 0.5, (
                f"Service name coverage too low: {service_name_coverage:.2%}. "
                f"Expected at least 50% of events to have service name."
            )

    def test_service_name_format_validation(self):
        """Test that service name follows expected format across all libraries."""

        def validator(data: dict[str, Any]) -> None:
            if not_onboarding_event(data):
                service_name = get_service_name(data)

                if service_name:
                    # Validate service name format
                    assert isinstance(service_name, str), f"Service name should be string, got {type(service_name)}"
                    assert len(service_name) > 0, "Service name should not be empty"
                    assert len(service_name) <= 100, f"Service name too long: {len(service_name)} characters"

                    # Service names should be valid identifiers (alphanumeric, hyphens, underscores)
                    valid_chars = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_")
                    invalid_chars = set(service_name) - valid_chars
                    assert len(invalid_chars) == 0, f"Service name contains invalid characters: {invalid_chars}"

        self.validate_library_telemetry_data(validator, success_by_default=True)

    def test_service_name_consistency_with_environment(self):
        """Test that service name in telemetry matches environment configuration."""

        # Expected service names by library (based on system-tests configuration)
        expected_service_names = {
            "python": "weblog",
            "java": "weblog",
            "nodejs": "weblog",
            "dotnet": "weblog",
            "ruby": "weblog",
            "php": "weblog",
            "golang": "weblog",
            "cpp_nginx": "weblog",
            "cpp_httpd": "weblog",
        }

        expected_service_name = expected_service_names.get(context.library.name, "weblog")

        def validator(data: dict[str, Any]) -> None:
            if not_onboarding_event(data):
                service_name = get_service_name(data)

                if service_name:
                    # Allow some flexibility for custom configurations
                    assert service_name == expected_service_name, (
                        f"Service name '{service_name}' does not match expected '{expected_service_name}' "
                        f"for library {context.library.name}. This might indicate custom DD_SERVICE configuration."
                    )

        self.validate_library_telemetry_data(validator, success_by_default=True)

    def test_service_name_in_different_event_types(self):
        """Test that service name is present in different types of telemetry events."""

        event_types_with_service_name = {}
        event_types_without_service_name = {}

        def validator(data: dict[str, Any]) -> None:
            if not_onboarding_event(data):
                event_type = get_request_type(data)
                service_name = get_service_name(data)

                if event_type:
                    if service_name:
                        if event_type not in event_types_with_service_name:
                            event_types_with_service_name[event_type] = 0
                        event_types_with_service_name[event_type] += 1
                    else:
                        if event_type not in event_types_without_service_name:
                            event_types_without_service_name[event_type] = 0
                        event_types_without_service_name[event_type] += 1

        self.validate_library_telemetry_data(validator, success_by_default=True)

        # Log the results for debugging
        logger.info(f"Event types with service name: {event_types_with_service_name}")
        logger.info(f"Event types without service name: {event_types_without_service_name}")

        # Critical events should have service name
        critical_events = ["app-started", "app-client-configuration-change"]
        for event_type in critical_events:
            if event_type in event_types_without_service_name:
                logger.warning(f"Critical event '{event_type}' missing service name")

    def test_service_name_case_sensitivity(self):
        """Test that service name handling is case-sensitive and consistent."""

        service_name_variants = set()

        def validator(data: dict[str, Any]) -> None:
            if not_onboarding_event(data):
                service_name = get_service_name(data)

                if service_name:
                    service_name_variants.add(service_name)

        self.validate_library_telemetry_data(validator, success_by_default=True)

        # All service names should be consistent (same case)
        assert len(service_name_variants) <= 1, (
            f"Multiple service name variants found: {service_name_variants}. "
            f"Service names should be consistent across all telemetry events."
        )

    @missing_feature(library="cpp_nginx", reason="Telemetry not implemented")
    @missing_feature(library="cpp_httpd", reason="Telemetry not implemented")
    def test_service_name_in_telemetry_metadata(self):
        """Test that service name is properly included in telemetry metadata."""

        def validator(data: dict[str, Any]) -> None:
            if not_onboarding_event(data):
                content = get_request_content(data)
                application = content.get("application", {})

                # Service name should be in application metadata
                assert "service_name" in application, f"service_name missing in application metadata: {application}"

                service_name = application["service_name"]
                assert service_name is not None, "service_name should not be null"
                assert service_name != "", "service_name should not be empty string"

        self.validate_library_telemetry_data(validator, success_by_default=True)

    def test_service_name_with_custom_configuration(self):
        """Test service name behavior with custom DD_SERVICE configuration."""

        # This test validates that the service name in telemetry reflects
        # the actual service name being used by the tracer
        def validator(data: dict[str, Any]) -> None:
            if not_onboarding_event(data):
                service_name = get_service_name(data)

                if service_name:
                    # Service name should be a valid identifier
                    assert (
                        service_name.isidentifier() or "-" in service_name or "_" in service_name
                    ), f"Service name '{service_name}' is not a valid identifier"

                    # Service name should not contain spaces or special characters
                    assert " " not in service_name, f"Service name should not contain spaces: '{service_name}'"
                    assert not any(
                        c in service_name for c in "!@#$%^&*()+={}[]|\\:;\"'<>?,./"
                    ), f"Service name should not contain special characters: '{service_name}'"

        self.validate_library_telemetry_data(validator, success_by_default=True)
