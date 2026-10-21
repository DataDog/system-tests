"""Exercise the activation cutoff through Remote Config, evaluations, and EVP delivery.

Each scenario starts a separate SDK process with its configured mode. Assertions
read final captures after shutdown. These cases complement the shared evaluator
fixtures; they do not implement a second evaluator in the test harness.
"""

from concurrent.futures import ThreadPoolExecutor
import json
from typing import Any

from tests.ffe.utils.evaluation_telemetry import (
    assert_count,
    assert_evaluation_responses,
    assert_setup_succeeded,
    evaluation_count,
    evaluation_setup_error,
)
from tests.ffe.utils.experimentation_opt_out import (
    DEFAULT_VALUE as DEFAULT,
    Evaluation,
    Exposure,
    assert_exposures,
    evaluation_case,
    opt_out_fixture,
    run_evaluation,
)
from utils import context, features, interfaces, remote_config as rc, rfc, scenarios


ATTRIBUTE = "dd_experimentation_opt_out_at"
CUTOFF = "2026-02-01T00:00:00Z"
OLD = "2026-01-01T00:00:00Z"
NEW = "2026-03-01T00:00:00Z"
ON = "on-value"
OFF = "off-value"


@scenarios.feature_flagging_experimentation_opt_out_disabled
@scenarios.feature_flagging_experimentation_opt_out_immediate
@scenarios.feature_flagging_experimentation_opt_out_future
@features.feature_flags_experimentation_opt_out
@rfc("https://docs.google.com/document/d/153tRlj46l-XfBGCA2X_NvxW4vwYObaH8zm2moP_AqMk/edit")
class Test_FFE_Experimentation_Opt_Out:
    def mode_index(self) -> int:
        return {
            scenarios.feature_flagging_experimentation_opt_out_disabled.name: 0,
            scenarios.feature_flagging_experimentation_opt_out_immediate.name: 1,
            scenarios.feature_flagging_experimentation_opt_out_future.name: 2,
        }[context.scenario.name]

    def assert_delivery(self, cases: list[Evaluation]) -> None:
        expected: set[Exposure] = set()
        for case in cases:
            assert_evaluation_responses(case["responses"], expected_count=3, expected_value=case["value"])
            if case["exposure"]:
                expected.add((case["flag"], case["subject"], case["allocation"], "on"))
        assert_exposures(
            interfaces.agent.get_data(path_filters="/api/v2/exposures"),
            flags={case["flag"] for case in cases},
            expected=expected,
        )

    def setup_cutoff_matrix(self) -> None:
        self.cutoff_matrix_setup_error = evaluation_setup_error(self.prepare_cutoff_matrix)

    def prepare_cutoff_matrix(self) -> None:
        # Expected values are explicit: disabled, immediate, future-only.
        rows: list[tuple[str, str | None, dict[str, Any], tuple[str, str, str]]] = [
            ("older", OLD, {ATTRIBUTE: CUTOFF}, (ON, OFF, ON)),
            ("equal", CUTOFF, {ATTRIBUTE: CUTOFF}, (ON, OFF, OFF)),
            ("newer", NEW, {ATTRIBUTE: CUTOFF}, (ON, OFF, OFF)),
            ("missing-activation", None, {ATTRIBUTE: CUTOFF}, (ON, OFF, OFF)),
            ("null-activation", None, {ATTRIBUTE: CUTOFF}, (ON, OFF, OFF)),
            ("missing-preference", NEW, {}, (ON, ON, ON)),
            ("invalid-preference", OLD, {ATTRIBUTE: "not-a-date"}, (ON, DEFAULT, DEFAULT)),
            ("boolean-preference", OLD, {ATTRIBUTE: True}, (ON, DEFAULT, DEFAULT)),
            ("ordinary", NEW, {ATTRIBUTE: CUTOFF}, (ON, ON, ON)),
            ("invalid-ordinary", OLD, {ATTRIBUTE: "not-a-date"}, (ON, DEFAULT, DEFAULT)),
            ("no-fallback", NEW, {ATTRIBUTE: CUTOFF}, (ON, DEFAULT, DEFAULT)),
            ("offset-older", "2026-02-01T00:30:00+01:00", {ATTRIBUTE: CUTOFF}, (ON, OFF, ON)),
            ("offset-equal", "2026-02-01T01:00:00+01:00", {ATTRIBUTE: CUTOFF}, (ON, OFF, OFF)),
            (
                "microsecond-older",
                "2026-02-01T00:00:00.000001Z",
                {ATTRIBUTE: "2026-02-01T00:00:00.000002Z"},
                (ON, OFF, ON),
            ),
            # A future preference is a literal cutoff, not a scheduled change.
            ("future-cutoff", NEW, {ATTRIBUTE: "2100-01-01T00:00:00Z"}, (ON, OFF, ON)),
        ]
        self.matrix: list[Evaluation] = []
        fixture = opt_out_fixture("placeholder")
        fixture["flags"] = {}
        for label, activation, attributes, values in rows:
            flag = f"experiment-opt-out-{label}"
            experiment = label not in {"ordinary", "invalid-ordinary"}
            fixture["flags"].update(
                opt_out_fixture(
                    flag,
                    activation,
                    include_activation=label != "missing-activation",
                    experiment=experiment,
                    fallback=label != "no-fallback",
                )["flags"]
            )
            value = values[self.mode_index()]
            self.matrix.append(
                evaluation_case(flag, f"subject-{label}", attributes, value, exposure=experiment and value == ON)
            )

        # Alternate subjects on one flag to detect leaked per-subject decisions.
        shared = "experiment-opt-out-shared"
        fixture["flags"].update(opt_out_fixture(shared, NEW)["flags"])
        self.matrix.extend(
            [
                evaluation_case(shared, "allowed", {}, ON, exposure=True),
                evaluation_case(
                    shared,
                    "excluded",
                    {ATTRIBUTE: CUTOFF},
                    (ON, OFF, OFF)[self.mode_index()],
                    exposure=self.mode_index() == 0,
                ),
            ]
        )
        rc.tracer_rc_state.reset().set_config("datadog/2/FFE_FLAGS/opt-out-matrix/config", fixture).apply()
        with ThreadPoolExecutor(max_workers=4) as executor:
            for _ in range(3):
                list(executor.map(run_evaluation, self.matrix))

    def test_cutoff_matrix(self) -> None:
        assert_setup_succeeded(self.cutoff_matrix_setup_error)
        self.assert_delivery(self.matrix)

    def setup_configuration_updates(self) -> None:
        self.configuration_updates_setup_error = evaluation_setup_error(self.prepare_configuration_updates)

    def prepare_configuration_updates(self) -> None:
        self.updates: list[Evaluation] = []
        flag = "experiment-opt-out-refresh"
        path = "datadog/2/FFE_FLAGS/opt-out-refresh/config"
        fixture = opt_out_fixture(flag, OLD)
        # startAt and createdAt are deliberately newer than the preference.
        # Neither field establishes when randomization was first activated.
        fixture["flags"][flag]["allocations"][0]["startAt"] = "2026-03-01T00:00:00Z"
        rc.tracer_rc_state.reset()
        for stage, (created_at, activation, allocation, values) in enumerate(
            [
                ("2026-04-01T00:00:00Z", OLD, "experiment", (ON, OFF, ON)),
                ("2026-05-01T00:00:00Z", OLD, "experiment", (ON, OFF, ON)),
                ("2026-06-01T00:00:00Z", NEW, "new-experiment", (ON, OFF, OFF)),
            ]
        ):
            fixture["createdAt"] = created_at
            first = fixture["flags"][flag]["allocations"][0]
            first.update(key=allocation, randomizationActivatedAt=activation)
            if stage == 2:
                first["splits"][0]["serialId"] = 103
            rc.tracer_rc_state.set_config(path, fixture).apply()
            value = values[self.mode_index()]
            cases = [
                evaluation_case(
                    flag, "opted-out", {ATTRIBUTE: CUTOFF}, value, exposure=value == ON, allocation=allocation
                ),
                evaluation_case(flag, "positive-control", {}, ON, exposure=True, allocation=allocation),
            ]
            for _ in range(3):
                for case in cases:
                    run_evaluation(case)
            self.updates.extend(cases)

    def test_configuration_updates(self) -> None:
        assert_setup_succeeded(self.configuration_updates_setup_error)
        self.assert_delivery(self.updates)

    def setup_holdout_assignments(self) -> None:
        self.holdout_assignments_setup_error = evaluation_setup_error(self.prepare_holdout_assignments)

    def prepare_holdout_assignments(self) -> None:
        # The same salt and subject must retain the same 10/90 assignment.
        # Distinct flags keep baseline exposures from hiding opted-out emissions.
        self.holdouts: dict[str, list[Evaluation]] = {}
        fixture = opt_out_fixture("placeholder")
        fixture["flags"] = {}
        for label, activation in [("baseline", OLD), ("older", OLD), ("newer", NEW)]:
            flag = f"experiment-opt-out-holdout-{label}"
            config = opt_out_fixture(flag, activation)["flags"][flag]
            config["variations"]["fallback"] = {"key": "fallback", "value": "fallback-value"}
            holdout, ordinary = config["allocations"]
            holdout["splits"] = [
                {
                    "variationKey": variant,
                    "serialId": serial,
                    "shards": [
                        {"salt": "holdout-opt-out", "totalShards": 10000, "ranges": [{"start": start, "end": end}]}
                    ],
                }
                for variant, serial, start, end in [("on", 201, 0, 1000), ("off", 202, 1000, 10000)]
            ]
            ordinary["splits"][0]["variationKey"] = "fallback"
            fixture["flags"][flag] = config
            attributes = {} if label == "baseline" else {ATTRIBUTE: CUTOFF}
            self.holdouts[label] = [
                evaluation_case(flag, f"holdout-subject-{index}", attributes, "", exposure=False) for index in range(64)
            ]
        rc.tracer_rc_state.reset().set_config("datadog/2/FFE_FLAGS/opt-out-holdouts/config", fixture).apply()
        cases = [case for group in self.holdouts.values() for case in group]
        with ThreadPoolExecutor(max_workers=4) as executor:
            for _ in range(3):
                list(executor.map(run_evaluation, cases))

    def test_holdout_assignments(self) -> None:
        assert_setup_succeeded(self.holdout_assignments_setup_error)
        expected: set[Exposure] = set()
        baseline_values: set[str] = set()
        for index, baseline in enumerate(self.holdouts["baseline"]):
            assert baseline["responses"][0].status_code == 200
            value = json.loads(baseline["responses"][0].text)["value"]
            assert value in {ON, OFF}, f"Baseline did not assign a holdout variant: {value!r}"
            baseline_values.add(value)
            for label, group in self.holdouts.items():
                case = group[index]
                continues = (
                    label == "baseline" or self.mode_index() == 0 or (label == "older" and self.mode_index() == 2)
                )
                assert_evaluation_responses(
                    case["responses"], expected_count=3, expected_value=value if continues else "fallback-value"
                )
                if continues:
                    expected.add((case["flag"], case["subject"], "experiment", "on" if value == ON else "off"))
        assert baseline_values == {ON, OFF}, "Both holdout groups must have positive controls"
        assert_exposures(
            interfaces.agent.get_data(path_filters="/api/v2/exposures"),
            flags={case["flag"] for group in self.holdouts.values() for case in group},
            expected=expected,
        )

    def setup_independent_telemetry_control(self) -> None:
        self.independent_telemetry_setup_error = evaluation_setup_error(self.prepare_independent_telemetry_control)

    def prepare_independent_telemetry_control(self) -> None:
        self.telemetry: list[Evaluation] = []
        fixture = opt_out_fixture("placeholder")
        fixture["flags"] = {}
        for experiment in (False, True):
            for suppress in (False, True):
                flag = f"experiment-opt-out-telemetry-{experiment}-{suppress}"
                fixture["flags"].update(opt_out_fixture(flag, OLD, experiment=experiment)["flags"])
                value = OFF if experiment and self.mode_index() == 1 else ON
                self.telemetry.append(
                    evaluation_case(
                        flag,
                        "subject",
                        {ATTRIBUTE: CUTOFF, "dd_evaluation_telemetry_opt_out": suppress},
                        value,
                        exposure=experiment and value == ON,
                    )
                )
        rc.tracer_rc_state.reset().set_config("datadog/2/FFE_FLAGS/opt-out-telemetry/config", fixture).apply()
        for _ in range(3):
            for case in self.telemetry:
                run_evaluation(case)

    def test_independent_telemetry_control(self) -> None:
        assert_setup_succeeded(self.independent_telemetry_setup_error)
        self.assert_delivery(self.telemetry)
        captures = list(interfaces.agent.get_data(path_filters="/api/v2/flagevaluation"))
        for case in self.telemetry:
            expected = 0 if case["attributes"]["dd_evaluation_telemetry_opt_out"] else 3
            assert_count(evaluation_count(captures, case["flag"]), expected, case["flag"])
