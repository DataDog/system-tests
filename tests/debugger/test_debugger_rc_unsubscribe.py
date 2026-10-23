# Unless explicitly stated otherwise all files in this repository are licensed under the Apache License Version 2.0.
# This product includes software developed at Datadog (https://www.datadoghq.com/).
# Copyright 2026 Datadog, Inc.

from typing import Any

from utils import features, interfaces, remote_config, scenarios, weblog
from utils.dd_constants import RemoteConfigApplyState


@features.debugger_inproduct_enablement
@scenarios.debugger_inproduct_enablement
class Test_Debugger_RC_Unsubscribe:
    """Test what happens when a remote config enabling DI is deleted.

    With DI disabled locally, enable it through an APM_TRACING config, then
    delete that config. The tracer must stop advertising LIVE_DEBUGGING while
    continuing to advertise APM_TRACING. Cover both deleting the last config
    and deleting the enabling config while an unrelated config remains.
    """

    @staticmethod
    def _wait_for_subscription_state(
        version: int,
        *,
        enabled: bool,
        identity: tuple[str, str] | None = None,
    ) -> dict[str, Any]:
        """Wait for a tracer to advertise the requested LIVE_DEBUGGING state.

        Args:
            version: Exact RC targets version the tracer must report, so polls
                from before the config change cannot satisfy the wait.
            enabled: True waits for LIVE_DEBUGGING to be present; False waits
                for it to be absent. APM_TRACING must remain advertised in both
                cases, proving that the tracer is still polling.
            identity: Optional (client ID, runtime ID) to match. If omitted,
                accept any identified tracer for weblog/system-tests. Supply
                the initial identity to exclude restarted or different tracers.

        Returns:
            The matching request's client object, or an empty dict if no
            matching poll arrives within 30 seconds.

        """
        observed: dict[str, Any] = {}

        def matches(data: dict[str, Any]) -> bool:
            if data["path"] != "/v0.7/config":
                return False
            client = data.get("request", {}).get("content", {}).get("client", {})
            tracer = client.get("client_tracer", {})
            client_identity = (client.get("id"), tracer.get("runtime_id"))
            if not all(client_identity) or (identity is not None and client_identity != identity):
                return False
            if tracer.get("service") != "weblog" or tracer.get("env") != "system-tests":
                return False
            if client.get("state", {}).get("targets_version") != version:
                return False
            products = client.get("products", [])
            if "APM_TRACING" not in products or ("LIVE_DEBUGGING" in products) != enabled:
                return False
            observed.update(client)
            return True

        interfaces.library.wait_for(matches, timeout=30)
        return observed

    @staticmethod
    def _payload(settings: dict[str, Any]) -> dict[str, Any]:
        config = {
            "schema_version": "v1.0.0",
            "action": "enable",
            "service_target": {"service": "weblog", "env": "system-tests"},
            "lib_config": settings,
        }
        if remote_config.library_supports_sdk_configuration():
            return remote_config.to_sdk_config_payload(config)
        return config

    def _exercise_removal(self, *, keep_other_config: bool) -> dict[str, Any]:
        result: dict[str, Any] = {
            "baseline": {},
            "subscribed": {},
            "unsubscribed": {},
            "remaining_ids": ["di-unsubscribe-unrelated"] if keep_other_config else [],
        }
        # Request-driven tracers need traffic to initialize remote configuration.
        result["http_status"] = weblog.get("/").status_code
        if not interfaces.library.wait_for(lambda data: data["path"] == "/v0.7/config", timeout=30):
            return result
        state = remote_config.tracer_rc_state
        # Other tests in this scenario can publish versions outside this singleton.
        state.version = max(
            state.version,
            *(
                data["request"]["content"].get("client", {}).get("state", {}).get("targets_version", 0)
                for data in interfaces.library.get_data(path_filters=["/v0.7/config"])
            ),
        )
        initial = state.reset().apply()
        baseline = self._wait_for_subscription_state(initial.version, enabled=False)
        result["baseline"] = baseline
        if not baseline:
            return result
        identity = (baseline["id"], baseline["client_tracer"]["runtime_id"])

        enablement_path = "datadog/2/APM_TRACING/di-unsubscribe-enablement/config"
        other_path = "datadog/2/APM_TRACING/di-unsubscribe-unrelated/config"
        if keep_other_config:
            state.set_config(other_path, self._payload({"tracing_sampling_rate": 1.0}))
        state.set_config(enablement_path, self._payload({"dynamic_instrumentation_enabled": True}))
        enabled = state.apply()
        subscribed = self._wait_for_subscription_state(enabled.version, enabled=True, identity=identity)
        result["subscribed"] = subscribed

        # Delete the file; sending false would exercise a different code path.
        removed = state.del_config(enablement_path).apply()
        unsubscribed = self._wait_for_subscription_state(removed.version, enabled=False, identity=identity)
        result["unsubscribed"] = unsubscribed
        return result

    @staticmethod
    def _assert_removed(result: dict[str, Any]) -> None:
        assert result["http_status"] == 200
        assert result["baseline"], "Expected a polling tracer with DI disabled before remote enablement"
        assert result["subscribed"], "Expected the same tracer to subscribe to LIVE_DEBUGGING after RC enablement"
        client = result["unsubscribed"]
        assert client, "The enabled tracer did not withdraw LIVE_DEBUGGING after consuming the config deletion"
        states = client["state"].get("config_states", [])
        apm_ids = sorted(config["id"] for config in states if config["product"] == "APM_TRACING")
        assert apm_ids == result["remaining_ids"], states
        assert all(config["apply_state"] == RemoteConfigApplyState.ACKNOWLEDGED for config in states), states

    def setup_remove_last_config(self) -> None:
        self.last_config = self._exercise_removal(keep_other_config=False)

    def test_remove_last_config(self) -> None:
        self._assert_removed(self.last_config)

    def setup_remove_config_with_other_config_remaining(self) -> None:
        """Delete DI enablement while retaining an unrelated sampling config.

        The tracer must unsubscribe from LIVE_DEBUGGING even though an
        APM_TRACING config remains. The sampling config must stay applied,
        and the tracer must continue advertising APM_TRACING.
        """
        self.other_config = self._exercise_removal(keep_other_config=True)

    def test_remove_config_with_other_config_remaining(self) -> None:
        self._assert_removed(self.other_config)
