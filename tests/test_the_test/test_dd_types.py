from utils import features, scenarios
from utils.dd_types import is_same_boolean


BooleanValue = bool | int | str | None


@scenarios.test_the_test
@features.not_reported
class Test_DDTypes:
    def test_is_same_boolean_accepts_native_and_string_booleans(self) -> None:
        cases: tuple[tuple[BooleanValue, BooleanValue], ...] = (
            (True, "true"),
            ("true", True),
            (False, "false"),
            ("false", False),
        )

        for actual, expected in cases:
            assert is_same_boolean(actual=actual, expected=expected)

    def test_is_same_boolean_rejects_numeric_booleans_by_default(self) -> None:
        cases: tuple[tuple[BooleanValue, BooleanValue], ...] = (
            (1, "true"),
            (1, True),
            (0, "false"),
            (0, False),
            ("true", 1),
            (True, 1),
            ("false", 0),
            (False, 0),
        )

        for actual, expected in cases:
            assert not is_same_boolean(actual=actual, expected=expected)

    def test_is_same_boolean_accepts_numeric_booleans_in_otel_mode(self) -> None:
        cases: tuple[tuple[BooleanValue, BooleanValue], ...] = (
            (1, "true"),
            (1, True),
            (0, "false"),
            (0, False),
            ("true", 1),
            (True, 1),
            ("false", 0),
            (False, 0),
        )

        for actual, expected in cases:
            assert is_same_boolean(actual=actual, expected=expected, is_otel_boolean=True)
