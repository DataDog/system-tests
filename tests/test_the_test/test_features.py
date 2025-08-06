from utils import scenarios, features, logger

from .utils import run_system_tests


FILENAME = "tests/test_the_test/test_features.py"


@scenarios.mock_the_test
@features.not_reported
def test_schemas():
    pass


@scenarios.test_the_test
def test_not_reported():
    result = run_system_tests(test_path=FILENAME)

    assert len(result) == 0


@scenarios.test_the_test
def test_all_class_has_feature_decorator(session, deselected_items):
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
