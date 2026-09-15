import pytest

from ddapm_test_agent.trace import Span
from tests.parametric.conftest import APMLibrary, assert_nodejs_telemetry_config
from utils import features, scenario_crash, scenarios
from utils.docker_fixtures import TestAgentAPI
from utils.docker_fixtures.spec.trace import find_only_span


type ResourceAttributes = str | list[str] | dict[str, str]


def _finished_span(test_agent: TestAgentAPI, library: APMLibrary) -> Span:
    with library.dd_start_span(name="otel_resource_attributes"):
        pass
    return find_only_span(test_agent.wait_for_num_traces(1))


def _resource_attributes(test_agent: TestAgentAPI, library: APMLibrary) -> ResourceAttributes:
    if library.lang in ("nodejs", "rust"):
        span = _finished_span(test_agent, library)
        attributes = span["meta"]
        assert isinstance(attributes, dict)
        return attributes

    attributes = library.config()["dd_tags"]
    assert isinstance(attributes, (str, list))
    return attributes


def _assert_resource_attributes(attributes: ResourceAttributes, expected: dict[str, str]) -> None:
    for key, value in expected.items():
        if isinstance(attributes, dict):
            assert attributes.get(key) == value
        else:
            assert f"{key}:{value}" in attributes


def _assert_resource_attribute_absent(attributes: ResourceAttributes, key: str) -> None:
    if isinstance(attributes, dict):
        assert key not in attributes
    else:
        assert f"{key}:" not in attributes


STABLE_VALUES = [
    pytest.param(
        {
            "DD_TAGS": None,
            "DD_TRACE_OTEL_ENABLED": "true",
            "OTEL_RESOURCE_ATTRIBUTES": "resource.test=single",
        },
        {"resource.test": "single"},
        id="single-pair",
    ),
    pytest.param(
        {
            "DD_TAGS": None,
            "DD_TRACE_OTEL_ENABLED": "true",
            "OTEL_RESOURCE_ATTRIBUTES": "resource.test=first,resource.extra=second",
        },
        {"resource.test": "first", "resource.extra": "second"},
        id="multiple-pairs",
    ),
]

UNSET_AND_EMPTY_VALUES = [
    pytest.param(
        {
            "DD_TAGS": None,
            "DD_TRACE_OTEL_ENABLED": "true",
            "OTEL_RESOURCE_ATTRIBUTES": None,
        },
        id="unset",
    ),
    pytest.param(
        {
            "DD_TAGS": None,
            "DD_TRACE_OTEL_ENABLED": "true",
            "OTEL_RESOURCE_ATTRIBUTES": "",
        },
        id="empty",
    ),
]


@scenarios.parametric
@features.otel_resource_attributes
class Test_OTEL_RESOURCE_ATTRIBUTES:
    @pytest.mark.parametrize(("library_env", "expected"), STABLE_VALUES)
    def test_stable_values(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
        *,
        expected: dict[str, str],
    ) -> None:
        with test_library as library:
            attributes = _resource_attributes(test_agent, library)

        _assert_resource_attributes(attributes, expected)

    @pytest.mark.parametrize(
        "library_env",
        [
            pytest.param(
                {
                    "DD_TAGS": None,
                    "DD_TRACE_OTEL_ENABLED": "true",
                    "OTEL_RESOURCE_ATTRIBUTES": "resource.test=comma%2Cequals%3Dvalue",
                },
                id="percent-encoded-separators",
            )
        ],
    )
    def test_percent_encoded_separators(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ) -> None:
        with test_library as library:
            attributes = _resource_attributes(test_agent, library)

        _assert_resource_attributes(
            attributes,
            {"resource.test": "comma,equals=value"},
        )

    @pytest.mark.parametrize("library_env", UNSET_AND_EMPTY_VALUES)
    def test_default_matches_specification(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ) -> None:
        with test_library as library:
            attributes = _resource_attributes(test_agent, library)

        _assert_resource_attribute_absent(attributes, "resource.test")

    @pytest.mark.parametrize(
        "library_env",
        [
            pytest.param(
                {
                    "DD_TAGS": None,
                    "DD_TRACE_OTEL_ENABLED": "true",
                    "OTEL_RESOURCE_ATTRIBUTES": "resource.test=discarded,invalid",
                },
                id="malformed-pair",
            )
        ],
    )
    @scenario_crash
    def test_invalid_value_is_discarded(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ) -> None:
        with test_library as library:
            attributes = _resource_attributes(test_agent, library)

        _assert_resource_attribute_absent(attributes, "resource.test")

    @pytest.mark.parametrize(
        "library_env",
        [
            pytest.param(
                {
                    "DD_ENV": None,
                    "DD_SERVICE": None,
                    "DD_TAGS": None,
                    "DD_TRACE_OTEL_ENABLED": "true",
                    "DD_VERSION": None,
                    "OTEL_RESOURCE_ATTRIBUTES": (
                        "deployment.environment=test1,service.name=test2,service.version=5,foo=bar1,baz=qux1"
                    ),
                    "OTEL_SERVICE_NAME": None,
                },
                id="reserved-attributes",
            )
        ],
    )
    def test_reserved_attributes_are_mapped(
        self,
        test_agent: TestAgentAPI,
        test_library: APMLibrary,
    ) -> None:
        with test_library as library:
            if library.lang in ("nodejs", "rust"):
                if library.lang == "nodejs":
                    assert_nodejs_telemetry_config(
                        test_agent,
                        {"dd_service": "test2", "dd_env": "test1", "dd_version": "5"},
                    )
                span = _finished_span(test_agent, library)
                assert span["service"] == "test2"
                assert span["meta"]["env"] == "test1"
                assert span["meta"]["version"] == "5"
                _assert_resource_attributes(
                    span["meta"],
                    {"foo": "bar1", "baz": "qux1"},
                )
                return

            config = library.config()

        assert config["dd_service"] == "test2"
        assert config["dd_env"] == "test1"
        assert config["dd_version"] == "5"
        tags = config["dd_tags"]
        assert isinstance(tags, (str, list))
        _assert_resource_attributes(tags, {"foo": "bar1", "baz": "qux1"})
