"""Delayed capability registration through a real Agent, with no UFC republish."""

import base64
import json
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, cast

from utils import context, features, scenarios, weblog
from utils.mocked_backend.rc_capabilities import BASE_PATH, DEPENDENT_PATH, capability_mask
from utils.proxy.ports import ProxyPorts

from .utils.rc_capability_refresh import CachePreloader, acknowledged, configurations, sdk_polls


if TYPE_CHECKING:
    from utils._context._scenarios.feature_flagging import FeatureFlaggingCapabilityRefresh


def wait_until(predicate: Callable[[], bool]) -> bool:
    deadline = time.monotonic() + 40
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.2)
    return False


@scenarios.feature_flagging_capability_refresh
@scenarios.feature_flagging_capability_refresh_preloaded
@features.feature_flags_dynamic_evaluation
class Test_FFE_RC_Capability_Refresh:
    def setup_delayed_provider(self) -> None:
        scenario = cast("FeatureFlaggingCapabilityRefresh", context.scenario)
        backend = scenario.mocked_backend_container.client
        base, dependent = configurations()
        self.published = backend.rc_publish_capability_variants(base, dependent)
        preloader = None
        legacy = None
        self.cache_ready = True
        if scenario is scenarios.feature_flagging_capability_refresh_preloaded:
            port = scenario.proxy_container.runtime_container.attrs["NetworkSettings"]["Ports"][
                f"{ProxyPorts.weblog}/tcp"
            ][0]["HostPort"]
            legacy = CachePreloader(f"http://127.0.0.1:{port}", dependent=False)
            legacy.poll()
            preloader = CachePreloader(f"http://127.0.0.1:{port}")
            self.cache_ready = wait_until(lambda: DEPENDENT_PATH in preloader.poll())
            preloader.poll()  # ACK the companion before Java registers its provider.
        self.preloaded = preloader is not None
        self.base_ready = wait_until(
            lambda: any(
                acknowledged(data["request"]["content"]["client"], BASE_PATH)
                for data in sdk_polls()
                if not data["request"]["content"]["client"]["id"].startswith("cache-preloader-")
            )
        )
        self.before_status = backend.rc_capability_status()
        # Spring's @Lazy Client initializes the Datadog provider on the first /ffe request.
        self.initial = weblog.post(
            "/ffe",
            json={
                "flag": "parent",
                "variationType": "STRING",
                "defaultValue": "caller-default",
                "targetingKey": "test-user",
                "attributes": {},
            },
        )

        def companion_acknowledged() -> bool:
            # Keep both cache clients live throughout the wait. Their expiry must not
            # change the target union and accidentally unstick a stale director.
            for cache_client in (preloader, legacy):
                if cache_client is not None:
                    cache_client.poll()
            return any(
                acknowledged(data["request"]["content"]["client"], DEPENDENT_PATH)
                for data in sdk_polls()
                if not data["request"]["content"]["client"]["id"].startswith("cache-preloader-")
            )

        self.dependent_ready = wait_until(companion_acknowledged)
        # Keep the preloader active, so the preloaded case retains the same union of files.
        if preloader is not None:
            preloader.poll()
        if legacy is not None:
            legacy.poll()
        self.evaluation = weblog.post(
            "/ffe",
            json={
                "flag": "child",
                "variationType": "STRING",
                "defaultValue": "caller-default",
                "targetingKey": "test-user",
                "attributes": {},
            },
        )
        self.after = sdk_polls()
        self.after_status = backend.rc_capability_status()

    def test_delayed_provider(self) -> None:
        assert self.cache_ready, "The second client must cache the companion before provider initialization"
        assert self.base_ready, "Java must ACK the base config before provider initialization"
        assert self.dependent_ready, "Java must ACK the companion after provider initialization"
        polls = [
            data for data in self.after if not data["request"]["content"]["client"]["id"].startswith("cache-preloader-")
        ]
        clients = [data["request"]["content"]["client"] for data in polls]
        assert len({client["id"] for client in clients}) == 1, "Provider startup must retain the RC client identity"
        transition = next(
            index for index, client in enumerate(clients) if capability_mask(client["capabilities"]) & (1 << 50)
        )
        assert transition > 0, "Must observe polls before the provider registers capability 50"
        previous = clients[transition - 1]
        upgraded = clients[transition]
        assert capability_mask(previous["capabilities"]) & (1 << 46)
        assert not capability_mask(previous["capabilities"]) & (1 << 50)
        assert acknowledged(previous, BASE_PATH)
        previous_version = previous["state"]["targets_version"]
        response = polls[transition - 1]["response"].get("content", {})
        if isinstance(response, dict) and response.get("targets"):
            previous_version = json.loads(base64.b64decode(response["targets"]))["signed"]["version"]
        assert upgraded["state"]["targets_version"] == previous_version > 0, (
            "Capabilities must change without resetting SDK state"
        )
        versions = [client["state"]["targets_version"] for client in clients[transition:]]
        assert versions == sorted(versions), "SDK state must not decrease to recover delivery"
        assert all(version > 0 for version in versions), "SDK state must not reset to recover delivery"
        assert any(acknowledged(client, DEPENDENT_PATH) for client in clients[transition:])
        deliveries = [data["response"].get("content", {}) for data in polls[transition:]]
        assert any(
            isinstance(response, dict) and response.get("client_configs") == [DEPENDENT_PATH] for response in deliveries
        )
        assert self.initial.status_code == 200
        assert json.loads(self.initial.text)["value"] == "parent-value"
        assert self.evaluation.status_code == 200
        assert json.loads(self.evaluation.text)["value"] == "dependent-match", (
            "ACK alone does not prove the provider retained the replacement"
        )
        assert self.published["hashes"] == self.after_status["hashes"]
        assert self.after_status["publications"] == self.after_status["config_version"] == 1
        client_id = upgraded["id"]
        before = next(
            entry for entry in reversed(self.before_status["history"]) if entry["selected"].get(client_id) == BASE_PATH
        )
        after = next(
            entry for entry in self.after_status["history"] if entry["selected"].get(client_id) == DEPENDENT_PATH
        )
        assert after["version"] > before["version"]
        if self.preloaded:
            assert set(before["selected"].values()) == set(after["selected"].values()) == {BASE_PATH, DEPENDENT_PATH}
        else:
            assert set(before["selected"].values()) == {BASE_PATH}
