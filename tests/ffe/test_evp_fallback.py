"""Fault-injection contracts exercised by the installed SDK's two production writers."""

import hashlib
import json
from typing import Any

from tests.ffe.utils.evp import EVP_ORIGINS, assert_agentless_evp_intake_request, register_expected_evp_capture
from utils import context, features, interfaces, scenario_crash, scenarios, weblog
from utils._context._scenarios.agentless_endtoend import FeatureFlaggingEVPFallback, FeatureFlaggingAgentlessAgent


def events_for(data: dict[str, Any], subject: str) -> list[dict[str, Any]]:
    content = data.get("request", {}).get("content", {})
    if not isinstance(content, dict):
        return []
    targeting_keys = {subject, f"sha256_{hashlib.sha256(subject.encode()).hexdigest()}"}
    return [
        event
        for event in content.get("exposures", []) + content.get("flagEvaluations", [])
        if event.get("subject", {}).get("id") == subject or event.get("targeting_key") in targeting_keys
    ]


@scenarios.feature_flagging_evp_404_exposures
@scenarios.feature_flagging_evp_404_flagevaluation
@scenarios.feature_flagging_evp_405_exposures
@scenarios.feature_flagging_evp_405_flagevaluation
@scenarios.feature_flagging_evp_403_exposures
@scenarios.feature_flagging_evp_403_flagevaluation
@scenarios.feature_flagging_evp_ambiguous_exposures
@scenarios.feature_flagging_evp_ambiguous_flagevaluation
@features.feature_flags_exposures
@scenario_crash
class Test_FFE_EVP_Fallback:
    def setup_delivery(self) -> None:
        scenario = context.scenario
        assert isinstance(scenario, FeatureFlaggingEVPFallback)
        self.responses = []
        for subject in ("evp-first", "evp-future"):
            self.responses.append(
                weblog.post(
                    "/ffe",
                    json={
                        "flag": "empty-targeting-key-flag",
                        "variationType": "STRING",
                        "defaultValue": "default",
                        "targetingKey": subject,
                        "attributes": {},
                    },
                )
            )
            if subject == "evp-first":
                local_path = f"{scenario.receiver_prefix}/evp_proxy/v4/api/v2/{scenario.fault_signal}"

                def first_captured(data: dict[str, Any], expected_path: str = local_path) -> bool:
                    return data.get("path") == expected_path and bool(events_for(data, "evp-first"))

                assert interfaces.backend_v2.wait_for(first_captured, timeout=30)
                # Wait for the response to be processed before producing the future batch.
                interfaces.datadog_direct.wait(3)
        for signal in ("exposures", "flagevaluation"):
            register_expected_evp_capture(f"/api/v2/{signal}")

            def future_captured(data: dict[str, Any], expected_signal: str = signal) -> bool:
                return data.get("path") == f"/api/v2/{expected_signal}" and bool(events_for(data, "evp-future"))

            assert interfaces.datadog_direct.wait_for(future_captured, timeout=35)

    def test_delivery(self) -> None:
        scenario = context.scenario
        assert isinstance(scenario, FeatureFlaggingEVPFallback)
        assert all(response.status_code == 200 for response in self.responses)
        assert all(json.loads(response.text)["value"] == "on-value" for response in self.responses)
        local = [
            data
            for data in interfaces.backend_v2.get_data()
            if data.get("path", "").startswith(scenario.receiver_prefix + "/evp_proxy/")
        ]
        direct = [
            data
            for data in interfaces.datadog_direct.get_data()
            if data.get("path") in ("/api/v2/exposures", "/api/v2/flagevaluation")
        ]
        discovery = [
            data for data in interfaces.backend_v2.get_data() if data.get("path") == scenario.receiver_prefix + "/info"
        ]
        assert len(discovery) == 1
        for data in local + discovery:
            headers = {key.lower(): value for key, value in data["request"]["headers"]}
            assert "dd-api-key" not in headers
            assert "x-datadog-trace-id" not in headers
            assert "traceparent" not in headers
            assert headers["dd-evp-origin"] == EVP_ORIGINS[context.library.name]
            assert headers["dd-evp-origin-version"] == context.library.raw_version
            if data in local:
                assert headers["x-datadog-evp-subdomain"] == "event-platform-intake"
        for data in direct:
            assert_agentless_evp_intake_request(
                data,
                route="direct",
                path=data["path"],
                expected_api_key=scenario.dd_api_key,
                library_name=context.library.name,
                library_version=context.library.raw_version,
            )
        for signal in ("exposures", "flagevaluation"):
            future = [data for data in direct if data["path"].endswith(f"/{signal}") and events_for(data, "evp-future")]
            assert len(future) == 1
            assert len(events_for(future[0], "evp-future")) == 1
            if signal == "flagevaluation":
                assert events_for(future[0], "evp-future")[0]["evaluation_count"] == 1
            assert not any(events_for(data, "evp-future") for data in local)
        other_signal = "flagevaluation" if scenario.fault_signal == "exposures" else "exposures"
        other_first = [
            data
            for data in local + direct
            if data["path"].endswith(f"/{other_signal}") and events_for(data, "evp-first")
        ]
        assert len(other_first) == 1
        assert len(events_for(other_first[0], "evp-first")) == 1
        first_local = [
            data
            for data in local
            if data["path"].endswith(f"/{scenario.fault_signal}") and events_for(data, "evp-first")
        ]
        first_direct = [
            data
            for data in direct
            if data["path"].endswith(f"/{scenario.fault_signal}") and events_for(data, "evp-first")
        ]
        assert len(first_local) == 1
        if scenario.fault_mode in ("404", "405"):
            assert len(first_direct) == 1
            assert first_local[0]["request"]["content"] == first_direct[0]["request"]["content"]
        else:
            assert first_direct == []


@scenarios.feature_flagging_agentless_agent
@features.feature_flags_exposures
@scenario_crash
class Test_FFE_EVP_Agentless_Agent:
    def setup_delivery(self) -> None:
        self.response = weblog.post(
            "/ffe",
            json={
                "flag": "empty-targeting-key-flag",
                "variationType": "STRING",
                "defaultValue": "default",
                "targetingKey": "evp-agent",
                "attributes": {},
            },
        )
        for signal in ("exposures", "flagevaluation"):
            register_expected_evp_capture(f"/api/v2/{signal}")

    def test_delivery(self) -> None:
        assert self.response.status_code == 200
        assert json.loads(self.response.text)["value"] == "on-value"
        assert isinstance(context.scenario, FeatureFlaggingAgentlessAgent)
        assert context.scenario.include_agent is True
        for signal in ("exposures", "flagevaluation"):
            captures = [
                data
                for data in interfaces.library.get_data()
                if data.get("path") == f"/evp_proxy/v4/api/v2/{signal}" and events_for(data, "evp-agent")
            ]
            assert len(captures) == 1
            assert len(events_for(captures[0], "evp-agent")) == 1
            headers = {key.lower(): value for key, value in captures[0]["request"]["headers"]}
            assert "dd-api-key" not in headers
            assert headers["dd-evp-origin"] == EVP_ORIGINS[context.library.name]
            assert headers["dd-evp-origin-version"] == context.library.raw_version
            assert headers["x-datadog-evp-subdomain"] == "event-platform-intake"
            forwarded = [
                data
                for data in interfaces.agent.get_data()
                if data.get("path") == f"/api/v2/{signal}" and events_for(data, "evp-agent")
            ]
            assert len(forwarded) == 1
            assert forwarded[0]["request"]["content"] == captures[0]["request"]["content"]
            forwarded_headers = {key.lower(): value for key, value in forwarded[0]["request"]["headers"]}
            assert forwarded_headers["dd-evp-origin"] == headers["dd-evp-origin"]
            assert forwarded_headers["dd-evp-origin-version"] == headers["dd-evp-origin-version"]
            assert forwarded_headers["dd-api-key"] in {context.scenario.dd_api_key, "--redacted--"}
        assert not any(events_for(data, "evp-agent") for data in interfaces.datadog_direct.get_data())
