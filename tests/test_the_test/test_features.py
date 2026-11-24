from utils import pytest
from collections.abc import Callable
from utils import scenarios, features, logger
from utils._features import NOT_REPORTED_ID


from .utils import run_system_tests


FILENAME = "tests/test_the_test/test_features.py"


@scenarios.mock_the_test
@features.not_reported
def test_schemas():
    pass


@scenarios.test_the_test
def test_not_reported():
    result = run_system_tests(test_path=FILENAME)

    assert result[f"{FILENAME}::test_schemas"]["features"] == []


@scenarios.test_the_test
def test_all_class_has_feature_decorator(session: pytest.Session, deselected_items: list[pytest.Item]):
    processed_nodes = set()
    shouldfail = False

    for item in session.items + deselected_items:
        reported_node_id = "::".join(item.nodeid.split("::", 2)[0:2])

        if reported_node_id in processed_nodes:
            continue

        processed_nodes.add(reported_node_id)

        if item.nodeid.startswith("tests/test_the_test/"):
            # special use case of test the test folder
            continue
        declared_features = [marker.kwargs["feature_id"] for marker in item.iter_markers("features")]
        if len(declared_features) == 0:
            logger.error(f"Missing feature declaration for {reported_node_id}")
            shouldfail = True

    if shouldfail:
        raise ValueError(
            "Some test classes misses @features decorator. "
            "More info on https://github.com/DataDog/system-tests/blob/main/docs/edit/add-new-test.md"
        )


@scenarios.test_the_test
def test_feature_are_correctly_declared():
    def get_markers(feature: Callable) -> list[pytest.Mark]:
        class TestObject: ...

        result = feature(TestObject)
        assert result is TestObject, f"Feature {feature.__name__} must return the test object"
        assert hasattr(TestObject, "pytestmark"), f"Feature {feature.__name__} must mark the test object"
        return TestObject.pytestmark  # type: ignore[attr-defined]

    for name in dir(features):
        if name.startswith("_"):
            continue

        feature = getattr(features, name)

        markers: list[pytest.Mark] = get_markers(feature)
        kwargs: dict = {}
        for marker in markers:
            kwargs |= marker.kwargs

        assert "feature_id" in kwargs, f"Feature `{name}` must declare a feature_id in its marker"
        assert "owner" in kwargs, f"Feature `{name}` must declare an owner in its marker"
        feature_id = kwargs["feature_id"]

        if feature_id != NOT_REPORTED_ID:
            assert f"https://feature-parity.us1.prod.dog/#/?feature={feature_id}" in feature.__doc__, (
                f"Feature `{name}` must have a link to the feature parity in its docstring"
            )


@scenarios.test_the_test
def test_all_test_the_test_items_declare_test_the_test_scenario(
    session: pytest.Session, deselected_items: list[pytest.Item]
) -> None:
    """Guard for pytest_ignore_collect: every test under tests/test_the_test/ must declare a _TestTheTestScenario."""
    from utils._context._scenarios import scenarios as scenario_registry  # noqa: PLC0415
    from utils._context._scenarios.test_the_test import _TestTheTestScenario  # noqa: PLC0415

    allowed = {
        getattr(scenario_registry, attr).name
        for attr in dir(scenario_registry)
        if isinstance(getattr(scenario_registry, attr), _TestTheTestScenario)
    }

    offenders: list[str] = []
    for item in session.items + deselected_items:
        if not item.nodeid.startswith("tests/test_the_test/"):
            continue
        own_markers = [m for m in item.own_markers if m.name == "scenario"]
        scenario_markers = own_markers if own_markers else list(item.iter_markers("scenario"))
        declared = [m.args[0] for m in scenario_markers] if scenario_markers else ["DEFAULT"]
        if not any(name in allowed for name in declared):
            offenders.append(f"{item.nodeid} -> {declared}")

    assert not offenders, (
        "All tests under tests/test_the_test/ must belong to a _TestTheTestScenario "
        f"(allowed={sorted(allowed)}): {offenders}"
    )
