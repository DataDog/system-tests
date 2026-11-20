"""Evaluation telemetry and exposures switch off independently, without changing flag values.

`DD_FEATURE_FLAGS_EVALUATION_TELEMETRY_ENABLED=false` stops flag evaluation EVP events,
the `feature_flag.evaluations` metric, and span enrichment. `DD_FEATURE_FLAGS_EXPOSURES_ENABLED=false`
stops exposures. Each switch has its own scenario, and a third turns both off. Every signal
has its own class so manifests can describe SDK support. Within a scenario, the switch that
stays on is the positive control for the one that is off.

A provider option sets the same switches for one provider. `POST /ffe/inspect` evaluates through
a second OpenFeature client whose provider has both switches off in code. Evaluating a subject
through it, then through the default client, must send exactly one exposure: the inspection
neither sends one nor records the subject in the shared exposure deduplication cache.
"""

import json
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
from tests.ffe.utils.fixtures import make_exposure_ufc_fixture, make_ufc_fixture
from utils import HttpResponse, context, features, interfaces, remote_config as rc, scenarios, weblog


ANNOTATIONS = {"ffe_flags_enc", "ffe_subjects_enc", "ffe_runtime_defaults"}
EVALUATIONS = 3

# Scenario name -> (evaluation telemetry enabled, exposures enabled).
SWITCHES = {
    "FEATURE_FLAGGING_EVALUATION_TELEMETRY_DISABLED": (False, True),
    "FEATURE_FLAGGING_EXPOSURES_DISABLED": (True, False),
    "FEATURE_FLAGGING_EVALUATION_TELEMETRY_AND_EXPOSURES_DISABLED": (False, False),
}


class SwitchCase(TypedDict):
    flag: str
    subject: str
    responses: list[HttpResponse]


def _evaluate(path: str, flag: str, subject: str, default_value: str = "default") -> HttpResponse:
    return weblog.post(
        path,
        json={
            "flag": flag,
            "targetingKey": subject,
            "attributes": {},
            "variationType": "STRING",
            "defaultValue": default_value,
        },
    )


def _exposures(flag: str, subject: str) -> list[dict]:
    captures = interfaces.mocked_backend.get_data(path_filters="/api/v2/exposures")
    return [event for data in captures for event in exposure_events_from_data(data, {flag}, subject)]


def _evaluation_events() -> list[dict]:
    return list(interfaces.mocked_backend.get_data(path_filters="/api/v2/flagevaluation"))


def _metrics() -> list[dict]:
    return [metric for _, metric in interfaces.mocked_backend.get_metrics()]


class _EnvironmentSwitchContract:
    cases: list[SwitchCase]

    @property
    def telemetry_enabled(self) -> bool:
        return SWITCHES[context.scenario.name][0]

    @property
    def exposures_enabled(self) -> bool:
        return SWITCHES[context.scenario.name][1]

    def prepare(self, signal: str) -> None:
        self.cases = []
        self.setup_error = evaluation_setup_error(lambda: self._prepare(signal))

    def _prepare(self, signal: str) -> None:
        # Span enrichment annotates a flag through its split serial id.
        fixture = make_ufc_fixture(f"switches-{signal}-0", serial_id=100)
        fixture["flags"].update(make_ufc_fixture(f"switches-{signal}-1", serial_id=101)["flags"])
        rc.tracer_rc_state.reset().set_config(f"datadog/2/FFE_FLAGS/switches-{signal}/config", fixture).apply()

        self.cases = [
            SwitchCase(flag=flag, subject=f"subject-{flag}", responses=[]) for flag in sorted(fixture["flags"])
        ]
        # Repeated evaluations also exercise EVP aggregation and exposure deduplication.
        for _ in range(EVALUATIONS):
            for case in self.cases:
                case["responses"].append(_evaluate("/ffe", case["flag"], case["subject"]))

    def assert_values_unchanged(self) -> None:
        assert_setup_succeeded(self.setup_error)
        for case in self.cases:
            assert_evaluation_responses(case["responses"], expected_count=EVALUATIONS, expected_value="on-value")


@scenarios.feature_flagging_evaluation_telemetry_disabled
@scenarios.feature_flagging_exposures_disabled
@scenarios.feature_flagging_evaluation_telemetry_and_exposures_disabled
@features.feature_flags_evaluation_telemetry_and_exposures_switches
class Test_FFE_Switches_Environment_EVP(_EnvironmentSwitchContract):
    def setup_counts(self) -> None:
        self.prepare("evp")

    def test_counts(self) -> None:
        self.assert_values_unchanged()
        expected = EVALUATIONS if self.telemetry_enabled else 0
        captures = _evaluation_events()
        for case in self.cases:
            assert_count(
                evaluation_count(captures, case["flag"], subject=case["subject"]),
                expected,
                f"{case['flag']} ({case['subject']})",
            )


@scenarios.feature_flagging_evaluation_telemetry_disabled
@scenarios.feature_flagging_exposures_disabled
@scenarios.feature_flagging_evaluation_telemetry_and_exposures_disabled
@features.feature_flags_evaluation_telemetry_and_exposures_switches
class Test_FFE_Switches_Environment_Metrics(_EnvironmentSwitchContract):
    def setup_counts(self) -> None:
        self.prepare("metrics")

    def test_counts(self) -> None:
        self.assert_values_unchanged()
        metrics = _metrics()
        for case in self.cases:
            assert_metric_activity(
                metrics, case["flag"], allocation_key="default-allocation", suppressed=not self.telemetry_enabled
            )


@scenarios.feature_flagging_evaluation_telemetry_disabled
@scenarios.feature_flagging_exposures_disabled
@scenarios.feature_flagging_evaluation_telemetry_and_exposures_disabled
@features.feature_flags_evaluation_telemetry_and_exposures_switches
class Test_FFE_Switches_Environment_Trace_Annotations(_EnvironmentSwitchContract):
    def setup_annotations(self) -> None:
        self.prepare("traces")

    def test_annotations(self) -> None:
        self.assert_values_unchanged()
        for case in self.cases:
            for response in case["responses"]:
                spans = [span for _, _, span in interfaces.library.get_spans(request=response, full_trace=True)]
                assert spans, f"{case['flag']}: application tracing must remain enabled"
                annotated = [span for span in spans if ANNOTATIONS.intersection(span.get("meta", {}))]
                if self.telemetry_enabled:
                    assert annotated, f"{case['flag']}: missing flag annotation with evaluation telemetry on"
                else:
                    assert not annotated, f"{case['flag']}: evaluation telemetry is off but a trace was annotated"


@scenarios.feature_flagging_evaluation_telemetry_disabled
@scenarios.feature_flagging_exposures_disabled
@scenarios.feature_flagging_evaluation_telemetry_and_exposures_disabled
@features.feature_flags_evaluation_telemetry_and_exposures_switches
class Test_FFE_Switches_Environment_Exposures(_EnvironmentSwitchContract):
    def setup_exposures(self) -> None:
        self.prepare("exposures")

    def test_exposures(self) -> None:
        self.assert_values_unchanged()
        for case in self.cases:
            events = _exposures(case["flag"], case["subject"])
            if not self.exposures_enabled:
                assert events == [], f"{case['flag']}: exposures are off but {len(events)} were sent: {events}"
                continue
            # Deduplication sends one exposure for repeated evaluations of an unchanged context.
            assert len(events) == 1, f"{case['flag']}: expected 1 exposure, got {events}"
            assert events[0]["variant"]["key"] == "on"
            assert events[0]["allocation"]["key"] == "default-allocation"


class _InspectThenDefaultContract:
    """Evaluate through a provider with both switches off in code, then through the default provider.

    `inspected_flag` is evaluated for one subject through the inspection client, then the default
    client. `inspect_only_flag` is evaluated for another subject only through the inspection client,
    and must produce nothing: it rules out an inspection exposure that hides the default one through
    deduplication.
    """

    inspect_only: list[HttpResponse]
    inspected: list[HttpResponse]
    default: list[HttpResponse]

    def prepare(self, signal: str) -> None:
        self.inspected_flag = f"switches-inspect-{signal}"
        self.inspect_only_flag = f"switches-inspect-only-{signal}"
        self.subject = f"subject-{self.inspected_flag}"
        self.inspect_only_subject = f"subject-{self.inspect_only_flag}"
        self.inspect_only, self.inspected, self.default = [], [], []
        self.setup_error = evaluation_setup_error(self._prepare)

    def _prepare(self) -> None:
        fixture = make_exposure_ufc_fixture(self.inspected_flag)
        fixture["flags"].update(make_exposure_ufc_fixture(self.inspect_only_flag, serial_id=101)["flags"])
        rc.tracer_rc_state.reset().set_config(f"datadog/2/FFE_FLAGS/{self.inspected_flag}/config", fixture).apply()

        for _ in range(2):
            self.inspect_only.append(_evaluate("/ffe/inspect", self.inspect_only_flag, self.inspect_only_subject))
        self.inspected.append(_evaluate("/ffe/inspect", self.inspected_flag, self.subject))
        self.default.append(_evaluate("/ffe", self.inspected_flag, self.subject))

    def assert_same_values(self) -> None:
        assert_setup_succeeded(self.setup_error)
        assert_evaluation_responses(self.inspect_only, expected_count=2, expected_value="value-a")
        assert_evaluation_responses(self.inspected, expected_count=1, expected_value="value-a")
        assert_evaluation_responses(self.default, expected_count=1, expected_value="value-a")
        assert json.loads(self.inspected[0].text)["value"] == json.loads(self.default[0].text)["value"]


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_evaluation_telemetry_and_exposures_switches
class Test_FFE_Switches_Inspect_Then_Default_Exposures(_InspectThenDefaultContract):
    def setup_one_exposure(self) -> None:
        self.prepare("exposures")

    def test_one_exposure(self) -> None:
        self.assert_same_values()
        inspect_only = _exposures(self.inspect_only_flag, self.inspect_only_subject)
        assert inspect_only == [], f"The inspection provider sent exposures: {inspect_only}"

        events = _exposures(self.inspected_flag, self.subject)
        assert len(events) == 1, f"Expected one exposure, from the default client, got {events}"
        assert events[0]["variant"]["key"] == "variant-a"
        assert events[0]["allocation"]["key"] == "default-allocation"


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_evaluation_telemetry_and_exposures_switches
class Test_FFE_Switches_Inspect_Then_Default_EVP(_InspectThenDefaultContract):
    def setup_counts(self) -> None:
        self.prepare("evp")

    def test_counts(self) -> None:
        self.assert_same_values()
        captures = _evaluation_events()
        assert_count(
            evaluation_count(captures, self.inspect_only_flag, subject=self.inspect_only_subject),
            0,
            self.inspect_only_flag,
        )
        assert_count(evaluation_count(captures, self.inspected_flag, subject=self.subject), 1, self.inspected_flag)


@scenarios.feature_flagging_and_experimentation
@features.feature_flags_evaluation_telemetry_and_exposures_switches
class Test_FFE_Switches_Inspect_Then_Default_Metrics(_InspectThenDefaultContract):
    def setup_counts(self) -> None:
        self.prepare("metrics")

    def test_counts(self) -> None:
        self.assert_same_values()
        metrics = _metrics()
        assert_metric_activity(metrics, self.inspect_only_flag, allocation_key=None, suppressed=True)
        assert_metric_activity(metrics, self.inspected_flag, allocation_key=None, suppressed=False)
