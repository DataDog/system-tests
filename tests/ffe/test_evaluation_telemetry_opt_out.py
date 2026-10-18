"""Per-subject opt-out suppresses evaluation telemetry, not flag results or exposures.

Run the same assertions with support disabled (the default) and
enabled. Each signal has its own class so manifests can describe SDK support.
Validation reads the final captures after the scenario flushes and stops its
containers. Positive controls prevent missing telemetry from passing as opt-out.
"""

from concurrent.futures import ThreadPoolExecutor
from typing import Any, TypedDict

from tests.ffe.utils.evaluation_telemetry import assert_count, assert_evaluation_responses, evaluation_count
from tests.ffe.utils.exposures import exposure_events_from_data
from tests.ffe.utils.fixtures import make_ufc_fixture
from utils import HttpResponse, context, features, interfaces, remote_config as rc, rfc, scenarios, weblog


ATTRIBUTE = "dd_evaluation_telemetry_opt_out"
RFC = "https://docs.google.com/document/d/153tRlj46l-XfBGCA2X_NvxW4vwYObaH8zm2moP_AqMk/edit"
ATTRIBUTES: dict[str, dict[str, Any]] = {
    "true": {ATTRIBUTE: True},
    "false": {ATTRIBUTE: False},
    "missing": {},
    "string-true": {ATTRIBUTE: "true"},
    "number-one": {ATTRIBUTE: 1},
}
ANNOTATIONS = {"ffe_flags_enc", "ffe_subjects_enc", "ffe_runtime_defaults"}


class EvaluationCase(TypedDict):
    flag: str
    subject: str
    attributes: dict[str, Any]
    expected_count: int
    responses: list[HttpResponse]


class _TelemetryContract:
    cases: list[EvaluationCase]

    def prepare(self, signal: str) -> None:
        enabled = context.scenario == scenarios.feature_flagging_evaluation_telemetry_opt_out
        self.cases = []
        fixture = make_ufc_fixture(f"opt-out-{signal}-true", serial_id=101)
        fixture["flags"] = {}
        for index, (label, attributes) in enumerate(ATTRIBUTES.items()):
            flag = f"opt-out-{signal}-{label}"
            fixture["flags"].update(make_ufc_fixture(flag, serial_id=101 + index)["flags"])
            if label == "true":
                allocations = fixture["flags"][flag]["allocations"]
                allocations[0]["rules"] = [
                    {"conditions": [{"attribute": ATTRIBUTE, "operator": "ONE_OF", "value": ["true"]}]}
                ]
                # Removing the attribute before evaluation selects off-value,
                # even if the original context is retained for exposure logging.
                allocations.extend(
                    make_ufc_fixture(flag, "off", allocation_key="fallback", serial_id=201)["flags"][flag][
                        "allocations"
                    ]
                )
            self.cases.append(
                EvaluationCase(
                    flag=flag,
                    subject=f"subject-{signal}-{label}",
                    attributes=attributes,
                    expected_count=0 if enabled and label == "true" else 3,
                    responses=[],
                )
            )

        independent_cases = list(self.cases)
        shared_flag = f"opt-out-{signal}-shared"
        fixture["flags"].update(make_ufc_fixture(shared_flag, serial_id=106)["flags"])
        shared_cases = [
            EvaluationCase(
                flag=shared_flag,
                subject=f"subject-{signal}-shared-{label}",
                attributes={ATTRIBUTE: opted_out},
                expected_count=0 if enabled and opted_out else 3,
                responses=[],
            )
            for label, opted_out in [("true", True), ("false", False)]
        ]
        self.cases.extend(shared_cases)

        rc.tracer_rc_state.reset().set_config(f"datadog/2/FFE_FLAGS/opt-out-{signal}/config", fixture).apply()

        # Different subjects overlap. Repeated evaluations also exercise aggregation
        # and the ordinary exposure cache without changing the targeting context.
        def evaluate(case: EvaluationCase) -> None:
            response = weblog.post(
                "/ffe",
                json={
                    "flag": case["flag"],
                    "targetingKey": case["subject"],
                    "attributes": case["attributes"],
                    "variationType": "STRING",
                    "defaultValue": "default",
                },
            )
            case["responses"].append(response)

        with ThreadPoolExecutor(max_workers=len(independent_cases)) as executor:
            for _ in range(3):
                list(executor.map(evaluate, independent_cases))

        # Alternate subjects on one flag. A flag-scoped opt-out cache must not
        # suppress the allowed subject or permit the opted-out subject.
        for _ in range(3):
            for case in shared_cases:
                evaluate(case)

    def assert_evaluations(self) -> None:
        for case in self.cases:
            assert_evaluation_responses(case["responses"], expected_count=3, expected_value="on-value")

    def expected_counts(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for case in self.cases:
            counts[case["flag"]] = counts.get(case["flag"], 0) + case["expected_count"]
        return counts


@scenarios.feature_flagging_evaluation_telemetry_opt_out_disabled
@scenarios.feature_flagging_evaluation_telemetry_opt_out
@features.feature_flags_evaluation_telemetry_opt_out
@rfc(RFC)
class Test_FFE_Evaluation_Telemetry_Opt_Out_EVP(_TelemetryContract):
    def setup_counts(self) -> None:
        self.prepare("evp")

    def test_counts(self) -> None:
        self.assert_evaluations()
        captures = list(interfaces.agent.get_data(path_filters="/api/v2/flagevaluation"))
        for flag, expected_count in self.expected_counts().items():
            assert_count(evaluation_count(captures, flag), expected_count, flag)


@scenarios.feature_flagging_evaluation_telemetry_opt_out_disabled
@scenarios.feature_flagging_evaluation_telemetry_opt_out
@features.feature_flags_evaluation_telemetry_opt_out
@rfc(RFC)
class Test_FFE_Evaluation_Telemetry_Opt_Out_Metrics(_TelemetryContract):
    def setup_counts(self) -> None:
        self.prepare("metrics")

    def test_counts(self) -> None:
        self.assert_evaluations()
        for flag, expected_count in self.expected_counts().items():
            total = 0.0
            for _, metric in interfaces.agent.get_metrics():
                if metric.get("metric") != "feature_flag.evaluations":
                    continue
                if f"feature_flag.key:{flag}" not in metric.get("tags", []):
                    continue
                for point in metric.get("points", []):
                    total += float(point["value"] if isinstance(point, dict) else point[1])
            assert_count(total, expected_count, flag)


@scenarios.feature_flagging_evaluation_telemetry_opt_out_disabled
@scenarios.feature_flagging_evaluation_telemetry_opt_out
@features.feature_flags_evaluation_telemetry_opt_out
@rfc(RFC)
class Test_FFE_Evaluation_Telemetry_Opt_Out_Exposures(_TelemetryContract):
    def setup_unchanged(self) -> None:
        self.prepare("exposures")

    def test_unchanged(self) -> None:
        self.assert_evaluations()
        captures = list(interfaces.agent.get_data(path_filters="/api/v2/exposures"))
        for case in self.cases:
            events = [
                event for data in captures for event in exposure_events_from_data(data, {case["flag"]}, case["subject"])
            ]
            assert len(events) == 1, f"{case['flag']}: expected one deduplicated exposure, got {events}"
            assert events[0]["variant"]["key"] == "on"
            attributes = events[0]["subject"].get("attributes", {})
            # Some providers also include targetingKey in exposure attributes.
            # Check the customer input without forbidding that existing behavior.
            if ATTRIBUTE in case["attributes"]:
                expected = case["attributes"][ATTRIBUTE]
                assert attributes[ATTRIBUTE] == expected
                if isinstance(expected, bool):
                    assert isinstance(attributes[ATTRIBUTE], bool)
            else:
                assert ATTRIBUTE not in attributes


@scenarios.feature_flagging_evaluation_telemetry_opt_out_disabled
@scenarios.feature_flagging_evaluation_telemetry_opt_out
@features.feature_flags_evaluation_telemetry_opt_out
@rfc(RFC)
class Test_FFE_Evaluation_Telemetry_Opt_Out_Trace_Annotations(_TelemetryContract):
    def setup_annotations(self) -> None:
        self.prepare("traces")

    def test_annotations(self) -> None:
        self.assert_evaluations()
        for case in self.cases:
            for response in case["responses"]:
                spans = [span for _, _, span in interfaces.library.get_spans(request=response, full_trace=True)]
                assert spans, f"{case['flag']}: unrelated application tracing must remain enabled"
                annotated = [span for span in spans if ANNOTATIONS.intersection(span.get("meta", {}))]
                if case["expected_count"]:
                    assert annotated, f"{case['flag']}: missing positive-control flag annotation"
                else:
                    assert not annotated, f"{case['flag']}: opted-out evaluation annotated a trace"
