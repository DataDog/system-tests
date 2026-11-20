"""Provider options turn evaluation telemetry and exposures off for one provider, without changing flag values.

`evaluationTelemetryEnabled(false)` stops flag evaluation EVP events and the `feature_flag.evaluations`
metric for evaluations through that provider. `exposuresEnabled(false)` stops its exposures. The default
provider keeps both on. `POST /ffe/provider-options` evaluates through an OpenFeature domain whose
provider is built with the requested options; `POST /ffe` evaluates through the default domain.

For each combination with a switch off, one subject is evaluated only through the configured provider:
only the switched-off signal may be missing. With exposures off, a second subject is evaluated through
the configured provider, then the default one, and must get exactly one exposure with the same variant.
The configured provider therefore neither sends an exposure nor records the subject in the shared
exposure deduplication cache. Every signal has its own class so manifests can describe SDK support.
"""

from typing import TypedDict

from tests.ffe.utils.evaluation_telemetry import (
    assert_count,
    assert_evaluation_responses,
    assert_metric_activity,
    assert_setup_succeeded,
    evaluation_count,
    evaluation_setup_error,
)
from tests.ffe.utils.exposures import exposure_events_from_data
from tests.ffe.utils.fixtures import make_exposure_ufc_fixture
from utils import HttpResponse, features, interfaces, remote_config as rc, scenarios, weblog


OPTION_EVALUATIONS = 2

# (label, evaluation telemetry enabled, exposures enabled) for the configured provider.
COMBINATIONS = [
    ("telemetry-off", False, True),
    ("exposures-off", True, False),
    ("both-off", False, False),
]


class SwitchCase(TypedDict):
    flag: str
    subject: str
    evaluation_telemetry: bool
    exposures: bool
    then_default: bool
    option_responses: list[HttpResponse]
    default_responses: list[HttpResponse]


def _evaluate(path: str, case: SwitchCase) -> HttpResponse:
    body: dict[str, object] = {
        "flag": case["flag"],
        "targetingKey": case["subject"],
        "attributes": {},
        "variationType": "STRING",
        "defaultValue": "default",
    }
    if path == "/ffe/provider-options":
        body["evaluationTelemetryEnabled"] = case["evaluation_telemetry"]
        body["exposuresEnabled"] = case["exposures"]
    return weblog.post(path, json=body)


def _exposures(case: SwitchCase) -> list[dict]:
    captures = interfaces.mocked_backend.get_data(path_filters="/api/v2/exposures")
    return [event for data in captures for event in exposure_events_from_data(data, {case["flag"]}, case["subject"])]


class _ProviderOptionsContract:
    cases: list[SwitchCase]

    def prepare(self, signal: str) -> None:
        self.cases = []
        self.setup_error = evaluation_setup_error(lambda: self._prepare(signal))

    def _prepare(self, signal: str) -> None:
        for label, evaluation_telemetry, exposures in COMBINATIONS:
            # Whether a default evaluation adds an exposure after one was sent depends on whether
            # providers share their deduplication cache, so check it only when none was sent.
            for then_default in [False] if exposures else [False, True]:
                flag = f"switches-{signal}-{label}" + ("-then-default" if then_default else "")
                self.cases.append(
                    SwitchCase(
                        flag=flag,
                        subject=f"subject-{flag}",
                        evaluation_telemetry=evaluation_telemetry,
                        exposures=exposures,
                        then_default=then_default,
                        option_responses=[],
                        default_responses=[],
                    )
                )

        fixture = make_exposure_ufc_fixture(self.cases[0]["flag"], serial_id=100)
        for index, case in enumerate(self.cases[1:], start=101):
            fixture["flags"].update(make_exposure_ufc_fixture(case["flag"], serial_id=index)["flags"])
        rc.tracer_rc_state.reset().set_config(f"datadog/2/FFE_FLAGS/switches-{signal}/config", fixture).apply()

        for case in self.cases:
            # Repeated evaluations also exercise EVP aggregation and exposure deduplication.
            for _ in range(1 if case["then_default"] else OPTION_EVALUATIONS):
                case["option_responses"].append(_evaluate("/ffe/provider-options", case))
            if case["then_default"]:
                case["default_responses"].append(_evaluate("/ffe", case))

    def assert_values_unchanged(self) -> None:
        assert_setup_succeeded(self.setup_error)
        for case in self.cases:
            # The configured provider and the default one select the same variant.
            assert_evaluation_responses(
                case["option_responses"],
                expected_count=1 if case["then_default"] else OPTION_EVALUATIONS,
                expected_value="value-a",
            )
            assert_evaluation_responses(
                case["default_responses"], expected_count=int(case["then_default"]), expected_value="value-a"
            )


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_evaluation_telemetry_and_exposures_switches
class Test_FFE_Provider_Options_Exposures(_ProviderOptionsContract):
    def setup_exposures(self) -> None:
        self.prepare("exposures")

    def test_exposures(self) -> None:
        self.assert_values_unchanged()
        for case in self.cases:
            events = _exposures(case)
            if case["then_default"]:
                assert len(events) == 1, f"{case['flag']}: expected one exposure, from the default client, got {events}"
            elif case["exposures"]:
                assert len(events) == 1, f"{case['flag']}: expected one deduplicated exposure, got {events}"
            else:
                assert events == [], f"{case['flag']}: exposures are off but {len(events)} were sent: {events}"
                continue
            assert events[0]["variant"]["key"] == "variant-a"
            assert events[0]["allocation"]["key"] == "default-allocation"


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_evaluation_telemetry_and_exposures_switches
class Test_FFE_Provider_Options_EVP(_ProviderOptionsContract):
    def setup_counts(self) -> None:
        self.prepare("evp")

    def test_counts(self) -> None:
        self.assert_values_unchanged()
        captures = list(interfaces.mocked_backend.get_data(path_filters="/api/v2/flagevaluation"))
        for case in self.cases:
            expected = len(case["option_responses"]) if case["evaluation_telemetry"] else 0
            expected += len(case["default_responses"])
            assert_count(
                evaluation_count(captures, case["flag"], subject=case["subject"]),
                expected,
                f"{case['flag']} ({case['subject']})",
            )


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_evaluation_telemetry_and_exposures_switches
class Test_FFE_Provider_Options_Metrics(_ProviderOptionsContract):
    def setup_counts(self) -> None:
        self.prepare("metrics")

    def test_counts(self) -> None:
        self.assert_values_unchanged()
        metrics = [metric for _, metric in interfaces.mocked_backend.get_metrics()]
        for case in self.cases:
            # Metrics carry no subject, so a default evaluation of the same flag is a positive control,
            # and only flags evaluated through the configured provider alone can show suppression.
            suppressed = not case["evaluation_telemetry"] and not case["then_default"]
            assert_metric_activity(metrics, case["flag"], allocation_key=None, suppressed=suppressed)
