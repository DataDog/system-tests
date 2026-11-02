"""Per-subject opt-out suppresses evaluation telemetry, not flag results or exposures.

Run the same assertions with support disabled (the default) and
enabled. Each signal has its own class so manifests can describe SDK support.
Validation reads the final captures after the scenario flushes and stops its
containers. Positive controls prevent missing telemetry from passing as opt-out.
"""

from concurrent.futures import ThreadPoolExecutor
from typing import Any, Literal, TypedDict, cast

from tests.ffe.utils.evaluation_telemetry import (
    assert_count,
    assert_evaluation_responses,
    assert_opt_out_exposure_attribute,
    assert_metric_activity,
    assert_setup_succeeded,
    evaluation_count,
    evaluation_setup_error,
)
from tests.ffe.utils.exposures import exposure_events_from_data
from tests.ffe.utils.fixtures import make_ufc_fixture
from utils import HttpResponse, context, features, interfaces, remote_config as rc, rfc, scenarios, weblog


ATTRIBUTE = "dd_evaluation_telemetry_opt_out"
RFC = "https://docs.google.com/document/d/15rai-S0NmGO2sKsMgy6cGf4963Y--9qdEfAj5MiytUg/edit"
ATTRIBUTES: dict[str, dict[str, Any]] = {
    "true": {ATTRIBUTE: True},
    "false": {ATTRIBUTE: False},
    "missing": {},
    "string-true": {ATTRIBUTE: "true"},
    "number-one": {ATTRIBUTE: 1},
    "null": {ATTRIBUTE: None},
    "wrong-case": {"DD_EVALUATION_TELEMETRY_OPT_OUT": True},
    "legacy-name": {"dd_telemetry_opt_out": True},
}
ANNOTATIONS = {"ffe_flags_enc", "ffe_subjects_enc", "ffe_runtime_defaults"}


class EvaluationCase(TypedDict):
    flag: str
    subject: str
    allocation_key: str | None
    attributes: dict[str, Any]
    expected_count: int
    expected_value: str
    expected_exposures: int | None
    responses: list[HttpResponse]


class _TelemetryContract:
    cases: list[EvaluationCase]

    def prepare(self, signal: str) -> None:
        self.setup_error = evaluation_setup_error(lambda: self._prepare(signal))

    def _prepare(self, signal: str) -> None:
        enabled = context.scenario == scenarios.feature_flagging_evaluation_telemetry_opt_out
        self.cases = []
        fixture = make_ufc_fixture(f"opt-out-{signal}-true", serial_id=101)
        fixture["flags"] = {}  # Keep only the envelope; flags are added below.
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
                    allocation_key="default-allocation",
                    attributes=attributes,
                    expected_count=0 if enabled and label == "true" else 3,
                    expected_value="on-value",
                    expected_exposures=1,
                    responses=[],
                )
            )

        # Absent flags return the application default without an allocation.
        self.cases.extend(
            EvaluationCase(
                flag=f"opt-out-{signal}-missing-flag-{label}",
                subject=f"subject-{signal}-missing-flag-{label}",
                allocation_key=None,
                attributes={ATTRIBUTE: opted_out},
                expected_count=0 if enabled and opted_out else 3,
                expected_value="default",
                expected_exposures=0,
                responses=[],
            )
            for label, opted_out in [("true", True), ("false", False)]
        )
        independent_cases = list(self.cases)
        shared_flag = f"opt-out-{signal}-shared"
        fixture["flags"].update(make_ufc_fixture(shared_flag)["flags"])
        fixture["flags"][shared_flag]["allocations"] = []
        shared_cases = [
            EvaluationCase(
                flag=shared_flag,
                subject=f"subject-{signal}-shared-{label}",
                allocation_key=f"shared-{label}",
                attributes={ATTRIBUTE: opted_out, "test_subject": f"subject-{signal}-shared-{label}"},
                expected_count=0 if enabled and opted_out else 3,
                expected_value="on-value",
                expected_exposures=1,
                responses=[],
            )
            for label, opted_out in [("true", True), ("false", False)]
        ]
        # Metrics do not contain subject identifiers. Distinct allocations let
        # their existing tags identify each subject without changing the value.
        for index, case in enumerate(shared_cases):
            allocation = make_ufc_fixture(
                shared_flag, allocation_key=cast("str", case["allocation_key"]), serial_id=110 + index
            )["flags"][shared_flag]["allocations"][0]
            allocation["rules"] = [
                {"conditions": [{"attribute": "test_subject", "operator": "ONE_OF", "value": [case["subject"]]}]}
            ]
            fixture["flags"][shared_flag]["allocations"].append(allocation)
        self.cases.extend(shared_cases)

        # The same subject opts out, then removes the attribute. Suppression is
        # per evaluation, not a permanent decision cached for the subject.
        per_evaluation_flag = f"opt-out-{signal}-per-evaluation"
        fixture["flags"].update(
            make_ufc_fixture(per_evaluation_flag, allocation_key="opted-out", serial_id=120)["flags"]
        )
        per_evaluation_allocations = fixture["flags"][per_evaluation_flag]["allocations"]
        per_evaluation_allocations[0]["rules"] = [
            {"conditions": [{"attribute": ATTRIBUTE, "operator": "ONE_OF", "value": ["true"]}]}
        ]
        # Separate allocation tags keep the later positive control from hiding
        # metric leakage during the first phase. Both phases return the same value.
        per_evaluation_allocations.extend(
            make_ufc_fixture(per_evaluation_flag, allocation_key="resumed", serial_id=121)["flags"][
                per_evaluation_flag
            ]["allocations"]
        )
        per_evaluation_cases = [
            EvaluationCase(
                flag=per_evaluation_flag,
                subject=f"subject-{signal}-per-evaluation",
                allocation_key="opted-out" if attributes else "resumed",
                attributes=attributes,
                expected_count=0 if enabled and attributes else 3,
                expected_value="on-value",
                # Exposure deduplication after an attribute change is SDK-defined.
                expected_exposures=None,
                responses=[],
            )
            for attributes in [{ATTRIBUTE: True}, {}]
        ]
        self.cases.extend(per_evaluation_cases)

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

        for case in per_evaluation_cases:
            for _ in range(3):
                evaluate(case)

    def assert_evaluations(self) -> None:
        assert_setup_succeeded(self.setup_error)
        for case in self.cases:
            assert_evaluation_responses(case["responses"], expected_count=3, expected_value=case["expected_value"])

    def expected_totals(self, key: Literal["subject", "allocation_key"]) -> dict[tuple[str, str | None], int]:
        # Sequential evaluations of the same subject share the exported series.
        totals: dict[tuple[str, str | None], int] = {}
        for case in self.cases:
            group = (case["flag"], case[key])
            totals[group] = totals.get(group, 0) + case["expected_count"]
        return totals


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
        for (flag, subject), expected_count in self.expected_totals("subject").items():
            assert subject is not None
            assert_count(
                evaluation_count(captures, flag, subject=subject),
                expected_count,
                f"{flag} ({subject})",
            )


@scenarios.feature_flagging_evaluation_telemetry_opt_out_disabled
@scenarios.feature_flagging_evaluation_telemetry_opt_out
@features.feature_flags_evaluation_telemetry_opt_out
@rfc(RFC)
class Test_FFE_Evaluation_Telemetry_Opt_Out_Metrics(_TelemetryContract):
    def setup_counts(self) -> None:
        self.prepare("metrics")

    def test_counts(self) -> None:
        self.assert_evaluations()
        metrics = [metric for _, metric in interfaces.agent.get_metrics()]
        for (flag, allocation_key), expected_count in self.expected_totals("allocation_key").items():
            assert_metric_activity(
                metrics,
                flag,
                allocation_key=allocation_key,
                suppressed=expected_count == 0,
            )


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
            if case["expected_exposures"] is None:
                continue
            events = [
                event for data in captures for event in exposure_events_from_data(data, {case["flag"]}, case["subject"])
            ]
            assert len(events) == case["expected_exposures"], (
                f"{case['flag']}: expected {case['expected_exposures']} exposures, got {events}"
            )
            if not events:
                continue
            assert events[0]["variant"]["key"] == "on"
            assert events[0]["allocation"]["key"] == case["allocation_key"]
            attributes = events[0]["subject"].get("attributes", {})
            # Some providers also include targetingKey in exposure attributes.
            # Check the customer input without forbidding that existing behavior.
            assert_opt_out_exposure_attribute(attributes, case["attributes"], ATTRIBUTE)


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
